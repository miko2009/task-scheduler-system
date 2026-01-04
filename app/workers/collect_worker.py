import json
import time
import os
import sys
from app.core.config import settings
from app.core.database import redis_client, get_task_lock, get_mysql_conn
from app.core.utils import call_api_with_retry, update_task_status, update_collect_progress
from app.models.browse_record import batch_insert_browse_records

# settings import
# force add project root to Python path (outermost task_scheduler)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
# browse records collect worker
def collect_worker():
    print("collect Worker started")
    collect_queue = settings.TASK_QUEUE_COLLECT
    retry_queue = settings.TASK_QUEUE_RETRY

    while True:
        try:
            # wait for collect or retry task
            task_data_str = redis_client.brpop([retry_queue, collect_queue], timeout=5)
            if not task_data_str:
                continue

            queue_name, task_data_str = task_data_str
            task_data = json.loads(task_data_str)
            task_id = task_data["task_id"]
            user_id = task_data.get("user_id")

            # if from retry queue and retry_type is collect, get user_id from DB if not provided
            if not user_id:
                conn = get_mysql_conn()
                with conn.cursor() as cursor:
                    cursor.execute("SELECT user_id FROM tasks WHERE task_id = %s", (task_id,))
                    user_id = cursor.fetchone()["user_id"]
                conn.close()

            # get distributed lock
            lock = get_task_lock(task_id)
            if not lock.acquire(blocking=False):
                print(f"collection task:{task_id}is already being processed, skip")
                continue

            try:
                # check task status
                conn = get_mysql_conn()
                with conn.cursor() as cursor:
                    cursor.execute("SELECT status FROM tasks WHERE task_id = %s", (task_id,))
                    task_status = cursor.fetchone()["status"]
                conn.close()
                
                if task_status in ["paused", "cancelled"]:
                    print(f"collection task {task_id} status is {task_status}, stop")
                    return

                # step 1: get total count
                api_url = settings.BROWSE_COLLECT_API_URL
                params = {"task_id": task_id, "user_id": user_id, "action": "get_total"}
                try:
                    total_result = call_api_with_retry("browse_collect", task_id, api_url, params)
                    total_count = total_result.get("total_count", 0)
                    if total_count == 0:
                        update_collect_progress(task_id, 0, 0)
                        update_task_status(task_id, "completed", collect_status="completed")
                        print(f"task {task_id} no records to collect, marked as completed")
                        return
                    
                    # set task status to collecting
                    update_task_status(task_id, "collecting", collect_total=total_count, collect_status="collecting")
                except Exception as e:
                    update_task_status(task_id, "failed", collect_status="failed", error_msg=f"get total count failed: {e}")
                    print(f"collection task:{task_id}: error: {e}")
                    return

                # step 2: paginated collect browse records
                page = 1
                while True:
                    # check task status before each page
                    conn = get_mysql_conn()
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT status FROM tasks WHERE task_id = %s", (task_id,))
                        current_status = cursor.fetchone()["status"]
                    conn.close()
                    
                    if current_status in ["paused", "cancelled"]:
                        print(f"task:{task_id} status is {current_status}, stop paginated collect")
                        break

                    # collect one page
                    params = {
                        "task_id": task_id,
                        "user_id": user_id,
                        "action": "collect",
                        "page": page,
                        "page_size": settings.COLLECT_PAGE_SIZE
                    }
                    try:
                        collect_result = call_api_with_retry("browse_collect", task_id, api_url, params)
                        records = collect_result.get("records", [])
                        if not records:
                            break

                        # batch insert browse records
                        batch_insert_browse_records(task_id, user_id, records)

                        # update collect progress
                        collected_count = len(records)
                        is_completed = update_collect_progress(task_id, page, collected_count)

                        print(f"collection task {task_id} page {page} completed, total {collected_count} records")

                        if is_completed:
                            break
                        
                        page += 1
                        time.sleep(0.1)  # avoid hitting API rate limits
                    except Exception as e:
                        update_task_status(task_id, "failed", collect_status="failed", error_msg=f"paginated collect failed: {e}")
                        print(f"collection task {task_id} paginated collect failed: {e}")
                        break
            except Exception as e:
                update_task_status(task_id, "failed", collect_status="failed", error_msg=f"collection exception: {e}")
                print(f"collection task {task_id} exception: {e}")
            finally:
                lock.release()
        except Exception as e:
            print(f"collection worker exception: {e}")
        time.sleep(0.01)

if __name__ == "__main__":
    collect_worker()