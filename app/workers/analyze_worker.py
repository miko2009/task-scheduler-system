import json
import time
import os
import sys
import multiprocessing
from app.core.config import settings
from app.core.database import redis_client, get_task_lock, get_mysql_conn
from app.core.utils import call_api_with_retry, update_task_status

# settings import
# force add project root to Python path (outermost task_scheduler)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# analyze browse records
def analyze_browse_records(task_id, user_id):
    api_url = settings.BROWSE_ANALYSIS_API_URL
    params = {"task_id": task_id, "user_id": user_id}
    try:
        result = call_api_with_retry("browse_analysis", task_id, api_url, params)
        return "success", result, ""
    except Exception as e:
        return "timeout" if "超时" in str(e) else "failed", {}, str(e)

# process analyze task
def process_analyze_task(task_data):
    task_id = task_data["task_id"]

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

        # analyze browse records
        analysis_status, analysis_result, analysis_error = analyze_browse_records(task_id, task["user_id"])
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