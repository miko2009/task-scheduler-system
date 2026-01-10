import json
import time
import os
import sys
import multiprocessing
import asyncio
import httpx
import re
from typing import Any, Dict, List, Optional
import logging
# settings import
# force add project root to Python path (outermost task_scheduler)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from app.core.config import settings
from app.core.database import redis_client, get_task_lock, get_mysql_conn
from app.models.task import get_task_status
from app.models.task_payload import get_task_payload
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
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("analyz_worker")
async def _call_llm(prompt: str, sample_texts: List[str]) -> str:
    api_key = settings.OPENROUTER_API_KEY
    model =settings.OPENROUTER_MODEL
    api_url = settings.OPENROUTER_URL
    if not api_key or not model:
        return ""
    async with httpx.AsyncClient(timeout=20.0) as client:
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "\n".join(sample_texts[:20])},
        ]
        backoff = 1.0
        for _ in range(3):
            try:
                resp = await client.post(
                    api_url,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": model, "messages": messages, "temperature": 0.7},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"].strip()
            except Exception:
                pass
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 4.0)
    return ""
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
        content = await _call_llm(prompt, sample_texts)
        if task_name == "llm_brainrot":
            try:
                payload[field] = max(0, min(100, int(float(content.strip().split()[0]))))
            except Exception as e:
                logging.error(f"llm_brainrot error", e)
                return "failed", payload, ""
        elif task_name == "llm_niche_journey":
            parsed = []
            try:
                pattern = r'^```json\s*(.*?)\s*```$'
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    pure_json_str = match.group(1)
                    parsed = json.loads(pure_json_str)
                else:
                    parsed = json.loads(content)
             
                if not isinstance(parsed, list):
                    return "failed", payload, "not list"
            except Exception as e:
                logging.error(f"llm_niche_journey error", e)
                return "failed", payload, ""
            payload[field] = parsed[:5]
        elif task_name == "llm_top_niche_percentile":
            try:
                pattern = r'^```json\s*(.*?)\s*```$'
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    pure_json_str = match.group(1)
                    parsed = json.loads(pure_json_str)
                else:
                    parsed = json.loads(content)
                if isinstance(parsed, dict):
                    tn = parsed.get("top_niches")
                    if not isinstance(tn, list):
                        return False
                    payload["top_niches"] = [str(x).strip() for x in tn if str(x).strip()]
                    pct = parsed.get("top_niche_percentile")
                    if not pct:
                        return False
                    payload["top_niche_percentile"] = str(pct).strip()
                else:
                    logging.error(f"llm_top_niche_percentile error", e)
                    return "failed", payload, ""
            except Exception as e:
                logging.error(f"llm_top_niche_percentile error", e)
                return "failed", payload, ""
        elif task_name == "llm_personality":
            if not content:
                logging.error(f"llm_personality not content error")
                return "failed", payload, ""
            payload[field] = content.strip().split()[0].lower().replace(" ", "_")
        elif task_name == "llm_keyword_2026":
            if not content:
                logging.error(f"llm_keyword_2026 not content error")
                return "failed", payload, ""
            payload[field] = content.strip().splitlines()[0]
        else:
            payload[field] = content
    return "success", payload, ""

# process analyze task
async def process_analyze_task(task_data):
    task_id = task_data["task_id"]
    user_id = task_data.get("user_id")

    # check task status
    task = get_task_status(task_id)
    task_payload = get_task_payload(task_id)
    if not task or not task_payload:
        print(f"task:{task_id} is not exist, skip")
        return 

    payload = task_payload['payload']
    sample_texts = payload['_sample_texts']
    # get distributed lock
    lock = get_task_lock(task_id)
    if not lock.acquire(blocking=False):
        print(f"task:{task_id} is already being processed, skip")
        return

    try:
        # check task status
        task = get_task_status(task_id)

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
        analysis_status, analysis_result, analysis_error = await analyze_browse_records(task_id, user_id, sample_texts)
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
            analysis_result=json.dumps(analysis_result)
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
async def analyze_worker():
    print(f"analyze Worker  started")
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
            await process_analyze_task(task_data)
        except Exception as e:
            print(f"analyze Worker error: {e}")
        time.sleep(0.1)

if __name__ == "__main__":
    # start multiple analyze workers
    worker_num = settings.WORKER_ANALYZE_NUM
    processes = []
    asyncio.run( analyze_worker())
    # for i in range(worker_num):
    #     p = multiprocessing.Process(target=analyze_worker, args=(i+1,))
    #     p.start()
    #     processes.append(p)

    # try:
    #     for p in processes:
    #         p.join()
    # except KeyboardInterrupt:
    #     print("\nstop analyze workers...")
    #     for p in processes:
    #         p.terminate()