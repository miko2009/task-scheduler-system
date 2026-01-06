import json
import time
import os
import sys
import multiprocessing
from app.core.config import settings
from app.core.database import redis_client, get_task_lock, get_mysql_conn
from app.core.utils import call_api_with_retry, update_task_status
from app.core.prompt import (
    PERSONALITY_PROMPT,
    PERSONALITY_EXPLANATION_PROMPT,
    NICHE_JOURNEY_PROMPT,
    TOP_NICHES_PROMPT,
    BRAINROT_SCORE_PROMPT,
    BRAINROT_EXPLANATION_PROMPT,
    KEYWORD_2026_PROMPT,
    ROAST_THUMB_PROMPT
)

# settings import
# force add project root to Python path (outermost task_scheduler)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)



def request_llm_api(task_id, prompt, sample_texts): 
    api_url = settings.BROWSE_ANALYSIS_API_URL
    api_key = settings.OPENROUTER_API_KEY
    model = settings.OPENROUTER_MODEL

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "\n".join(sample_texts[:20])},
    ]
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    body={"model": model, "messages": messages, "temperature": 0.7},
    try:
        result = call_api_with_retry("browse_analysis", task_id, api_url, body, headers)
        return "success", result, ""
    except Exception as e:
        return "timeout" if "timeout" in str(e) else "failed", {}, str(e)
# analyze browse records
async def analyze_browse_records(task_id, user_id, sample_texts):
    api_url = settings.BROWSE_ANALYSIS_API_URL
    api_key = settings.OPENROUTER_API_KEY
    model = settings.OPENROUTER_MODEL

    prompts = [
        ("personality_type", PERSONALITY_PROMPT, "llm_personality"),
        ("personality_explanation", PERSONALITY_EXPLANATION_PROMPT, "llm_personality_explanation"),
        ("niche_journey", NICHE_JOURNEY_PROMPT, "llm_niche_journey"),
        ("top_niche_percentile", TOP_NICHES_PROMPT, "llm_top_niche_percentile"),
        ("brain_rot_score", BRAINROT_SCORE_PROMPT, "llm_brainrot"),
        ("brain_rot_explanation", BRAINROT_EXPLANATION_PROMPT, "llm_brainrot_explanation"),
        ("keyword_2026", KEYWORD_2026_PROMPT, "llm_keyword_2026"),
        ("thumb_roast", ROAST_THUMB_PROMPT, "llm_thumb_roast"),
    ]
    payload = {}
    for field, prompt, task_name in prompts:
        result = await request_llm_api(task_id, prompt, sample_texts)
        if task_name == "llm_brainrot":
            try:
                payload[field] = max(0, min(100, int(float(result.strip().split()[0]))))
            except Exception:
                return False
        elif task_name == "llm_niche_journey":
            parsed = []
            try:
                import json

                parsed = json.loads(result)
                if not isinstance(parsed, list):
                    return False
            except Exception:
                return False
            payload[field] = parsed[:5]
        elif task_name == "llm_top_niche_percentile":
            try:
                import json

                data = json.loads(result)
                if isinstance(data, dict):
                    tn = data.get("top_niches")
                    if not isinstance(tn, list):
                        return False
                    payload["top_niches"] = [str(x).strip() for x in tn if str(x).strip()]
                    pct = data.get("top_niche_percentile")
                    if not pct:
                        return False
                    payload["top_niche_percentile"] = str(pct).strip()
                else:
                    return False
            except Exception:
                return False
        elif task_name == "llm_personality":
            if not result:
                return False
            payload[field] = result.strip().split()[0].lower().replace(" ", "_")
        elif task_name == "llm_keyword_2026":
            if not result:
                return False
            payload[field] = result.strip().splitlines()[0]
        else:
            payload[field] = result
    return "success", payload, ""

# process analyze task
def process_analyze_task(task_data):
    task_id = task_data["task_id"]
    sample_texts = task_data.get("sample_texts", [])
    user_id = task_data.get("user_id")

    # get distributed lock
    lock = get_task_lock(task_id)
    if not lock.acquire(blocking=False):
        print(f"task:{task_id} is already being processed, skip")
        return

    try:
        # check task status
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT status, user_id, collect_status FROM tasks WHERE task_id = %s
            """, (task_id,))
            task = cursor.fetchone()
        conn.close()

        if task["status"] in ["paused", "cancelled"]:
            print(f"task:{task_id}status is {task['status']}, stop analysis")
            return
        
        if task["collect_status"] != "completed":
            print(f"task:{task_id} collection not completed, cannot analyze")
            update_task_status(
                task_id, "failed",
                error_msg="Collection not completed, cannot analyze"
            )
            return

        # set task status to analyzing
        update_task_status(task_id, "analyzing")

        api_url = settings.BROWSE_ANALYSIS_API_URL
        api_key = settings.OPENROUTER_API_KEY
        model = settings.OPENROUTER_MODEL
        if not api_key or not model or not api_url:
            update_task_status(
                task_id, "failed",
                analysis_status=analysis_status,
                error_msg=f"analyze fail: {'API key/model/api_url not configured'}"
            )
            return

        # analyze browse records
        analysis_status, analysis_result, analysis_error = analyze_browse_records(task_id, task["user_id"], sample_texts)
        if analysis_status != "success":
            update_task_status(
                task_id, "failed",
                analysis_status=analysis_status,
                error_msg=f"analyze fail: {analysis_error}"
            )
            print(f"task:{task_id} error: {analysis_error}")
            return

        # update task status to completed
        update_task_status(
            task_id, "completed",
            analysis_status="success",
            analysis_result=analysis_result
        )
        redis_client.lpush(settings.TASK_QUEUE_EMAIL_SEND, json.dumps({
                "task_id": task_id, "user_id": user_id
        }))
        print(f"task {task_id} analysis completed")
    except Exception as e:
        update_task_status(task_id, "failed", error_msg=f" analyze failed: {e}")
        print(f"task {task_id} analyze failed: {e}")
    finally:
        lock.release()

# analyze worker main loop
def analyze_worker(worker_id):
    print(f"analyze Worker {worker_id} started")
    analyze_queue = settings.TASK_QUEUE_ANALYZE
    retry_queue = settings.TASK_QUEUE_RETRY

    while True:
        try:
            # wait for analyze or retry task
            task_data_str = redis_client.brpop([retry_queue, analyze_queue], timeout=5)
            if not task_data_str:
                continue

            queue_name, task_data_str = task_data_str
            task_data = json.loads(task_data_str)

            # if from retry queue and retry_type is analyze, only task_id is needed
            if queue_name == retry_queue and task_data.get("retry_type") == "analyze":
                task_data = {"task_id": task_data["task_id"]}

            # process analyze task
            process_analyze_task(task_data)
        except Exception as e:
            print(f"analyze Worker {worker_id} 异常: {e}")
        time.sleep(0.1)

if __name__ == "__main__":
    # start multiple analyze workers
    worker_num = settings.WORKER_ANALYZE_NUM
    processes = []
    for i in range(worker_num):
        p = multiprocessing.Process(target=analyze_worker, args=(i+1,))
        p.start()
        processes.append(p)

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\nstop analyze workers...")
        for p in processes:
            p.terminate()