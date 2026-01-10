import json
import time
import multiprocessing
import os
import sys

from app.core.config import settings
from app.core.database import redis_client, get_task_lock, get_mysql_conn
from app.core.utils import update_task_status, call_api_with_retry
from app.models.task import update_verify_task_status
from app.core.archive_client import ArchiveClient
from app.models.user import get_user

# settings import
# force add project root to Python path (outermost task_scheduler)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
archive_client = ArchiveClient()

# verify user region
def verify_user_region(task_id, user_id, ip_address):

    update_verify_task_status(task_id)
    user = get_user(user_id)
    # call region verify API
    try:
       start_resp, status_code = archive_client.start_watch_history(user.latest_sec_user_id, limit=1, max_pages=1, cursor=None)
    except Exception as e:
        return "timeout" if "timeout" in str(e) else "failed", {}, str(e)

    # call finalize watch history API
    try:
        result = archive_client.finalize_watch_history(data_job_id=start_resp.get("data_job_id"), include_rows=True, return_limit=1)
        user.is_watch_history_available = "yes"
    except Exception as e:
        return "timeout" if "timeout" in str(e) else "failed", {}, str(e)
    return "success", result

# process verify task  
def process_verify_task(task_data):
    task_id = task_data["task_id"]
    user_id = task_data["user_id"]
    ip_address = task_data["ip_address"]

    # get distributed lock
    lock = get_task_lock(task_id)
    if not lock.acquire(blocking=False):
        print(f"任务{task_id}已被处理，跳过")
        return
    conn = None
    try:
        # check task status
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("SELECT status FROM tasks WHERE task_id = %s", (task_id,))
            task_status = cursor.fetchone()["status"]
        
        if task_status in ["paused", "cancelled"]:
            print(f"任务{task_id}状态为{task_status}，终止")
            return

        # execute region verification
        region_status, region_result, region_error = verify_user_region(task_id, user_id, ip_address)
        if region_status != "success":
            update_task_status(
                task_id, "failed",
                region_verify_status=region_status,
                error_msg=f"region verify error: {region_error}"
            )
            print(f"task{task_id} verify error: {region_error}")
            return

        # check region availability
        is_compliant = region_result.get("is_compliant", False)
        if not is_compliant:
            update_task_status(
                task_id, "rejected",
                region_verify_status="success",
                region_verify_result=region_result,
                error_msg=f"region: {region_result.get('country')}is not compliant"
            )
            print(f"task:{task_id} region: {region_result.get('country')} is not compliant, task rejected")
            return

        # update task status to collecting
        update_task_status(
            task_id, "collecting",
            region_verify_status="success",
            region_verify_result=region_result
        )
        redis_client.lpush(settings.TASK_QUEUE_COLLECT, json.dumps({
            "task_id": task_id, "user_id": user_id
        }))
        print(f"task {task_id} region verification successful, added to collection queue")
    except Exception as e:
        update_task_status(task_id, "failed", error_msg=f"verification exception: {e}")
        print(f"task {task_id} verification exception: {e}")
    finally:
        lock.release()
        if conn:
            conn.close()
    

# verify worker main loop
def verify_worker(worker_id):
    print(f"region verify worker {worker_id} started")
    verify_queue = settings.TASK_QUEUE_VERIFY
    retry_queue = settings.TASK_QUEUE_RETRY
    conn = None
    while True:
        try:
            # wait for verify or retry task
            task_data_str = redis_client.brpop([retry_queue, verify_queue], timeout=5)
            print(task_data_str)
            if not task_data_str:
                continue

            queue_name, task_data_str = task_data_str
            task_data = json.loads(task_data_str)

            # if from retry queue and retry_type is verify, get user_id and ip_address from DB
            if queue_name == retry_queue and task_data.get("retry_type") == "verify":
                conn = get_mysql_conn()
                with conn.cursor() as cursor:
                    cursor.execute("SELECT user_id, ip_address FROM tasks WHERE task_id = %s", (task_data["task_id"],))
                    task_detail = cursor.fetchone()
                task_data["user_id"] = task_detail["user_id"]
                task_data["ip_address"] = task_detail["ip_address"]

            # process verify task
            process_verify_task(task_data)
        except Exception as e:
            print(f"verify worker {worker_id} exception: {e}")
            time.sleep(0.1)
        finally:
            if conn:
                conn.close()


if __name__ == "__main__":
    # start multiple verify workers
    worker_num = settings.WORKER_VERIFY_NUM
    processes = []
    for i in range(worker_num):
        p = multiprocessing.Process(target=verify_worker, args=(i+1,))
        p.start()
        processes.append(p)

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n停止验证Worker...")
        for p in processes:
            p.terminate()