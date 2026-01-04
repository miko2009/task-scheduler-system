import uuid
import time
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryCallState
from app.core.config import settings
from app.core.database import get_mysql_conn, redis_client

# generate unique task ID
def generate_task_id():
    return f"task_{uuid.uuid4().hex[:16]}"

# get retry strategy from DB
def get_retry_strategy(api_type):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT max_retry_count, initial_delay, max_delay, multiplier 
                FROM retry_strategies WHERE api_type = %s
            """, (api_type,))
            strategy = cursor.fetchone()
        return strategy or {
            "max_retry_count": 3,
            "initial_delay": 1.0,
            "max_delay": 10.0,
            "multiplier": 2.0
        }
    except Exception as e:
        print(f"failed to get retry strategy: {e}")
        return {"max_retry_count":3, "initial_delay":1.0, "max_delay":10.0, "multiplier":2.0}
    finally:
        if conn:
            conn.close()  

# log API call details
def log_api_call(task_id, api_type, request_url, request_params, request_headers, 
                 response_code, response_data, cost_time, status, error_detail="", retry_count=0):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO api_call_logs 
                (task_id, api_type, request_url, request_params, request_headers, 
                 response_code, response_data, cost_time, status, error_detail, retry_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                task_id, api_type, request_url, json.dumps(request_params), json.dumps(request_headers),
                response_code, json.dumps(response_data), cost_time, status, error_detail, retry_count
            ))
        conn.commit()
    except Exception as e:
        print(f"record API call log failed: {e}")
    finally:
        if conn:
            conn.close()

# callback to update retry count in DB and Redis
def region_verify_retry_callback(retry_state: RetryCallState):
    conn = None
    task_id = retry_state.kwargs.get("task_id")
    if task_id:
        try:
            conn = get_mysql_conn()
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE tasks SET region_retry_count = region_retry_count + 1,
                                   update_time = CURRENT_TIMESTAMP
                    WHERE task_id = %s
                """, (task_id,))
            conn.commit()
            redis_key = settings.TASK_STATUS_KEY.format(task_id=task_id)
            redis_client.hincrby(redis_key, "region_retry_count", 1)
        except Exception as e:
            print(f"failed toupdate retry count: {e}")
        finally:
            if conn:
                conn.close()

# call external API with retry logic
def call_api_with_retry(api_type, task_id, url, params, headers=None, timeout=None):
    strategy = get_retry_strategy(api_type)
    max_retry = strategy["max_retry_count"]
    initial_delay = strategy["initial_delay"]
    max_delay = strategy["max_delay"]
    multiplier = strategy["multiplier"]

    timeout = timeout or settings.API_TIMEOUT
    headers = headers or {"Authorization": f"Bearer {settings.API_TOKEN}"}
    start_time = time.time()
    response_data = {}
    response_code = None
    error_detail = ""
    status = "success"
    retry_count = 0

    @retry(
        stop=stop_after_attempt(max_retry),
        wait=wait_exponential(multiplier=multiplier, min=initial_delay, max=max_delay),
        retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError)),
        reraise=True,
        before_sleep=region_verify_retry_callback if api_type == "region_verify" else None
    )
    def _call_api():
        nonlocal retry_count
        retry_count += 1
        try:
            response = requests.post(url, json=params, headers=headers, timeout=timeout)
            response_code = response.status_code
            response_data = response.json() if response.status_code == 200 else {}
            
            if response.status_code != 200:
                status = "failed"
                error_detail = f"status code: {response.status_code}, content: {response.text}"
                raise Exception(error_detail)
            return response_data
        except requests.exceptions.Timeout:
            status = "timeout"
            error_detail = f"timeout ({timeout} seconds)"
            raise
        except requests.exceptions.ConnectionError:
            status = "failed"
            error_detail = "connection error"
            raise
        except Exception as e:
            status = "failed"
            error_detail = str(e)
            raise

    try:
        response_data = _call_api()
    except Exception as e:
        error_detail = str(e)
        raise
    finally:
        cost_time = round(time.time() - start_time, 2)
        log_api_call(
            task_id, api_type, url, params, headers,
            response_code, response_data, cost_time, status, error_detail, retry_count-1
        )

    return response_data

# update task status in DB and Redis
def update_task_status(task_id, status, **kwargs):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            update_fields = ["status = %s", "update_time = CURRENT_TIMESTAMP"]
            update_values = [status]

            for key, value in kwargs.items():
                if key == "region_verify_status":
                    update_fields.append("region_verify_status = %s")
                    update_values.append(value)
                elif key == "region_verify_result":
                    update_fields.append("region_verify_result = %s")
                    update_values.append(json.dumps(value))
                elif key == "collect_status":
                    update_fields.append("collect_status = %s")
                    update_values.append(value)
                elif key == "collect_total":
                    update_fields.append("collect_total = %s")
                    update_values.append(value)
                elif key == "collect_completed":
                    update_fields.append("collect_completed = %s")
                    update_values.append(value)
                elif key == "collect_page":
                    update_fields.append("collect_page = %s")
                    update_values.append(value)
                elif key == "analysis_status":
                    update_fields.append("analysis_status = %s")
                    update_values.append(value)
                elif key == "analysis_result":
                    update_fields.append("analysis_result = %s")
                    update_values.append(json.dumps(value))
                elif key == "error_msg":
                    update_fields.append("error_msg = %s")
                    update_values.append(value)
                elif key == "region_retry_count":
                    update_fields.append("region_retry_count = %s")
                    update_values.append(value)

            update_sql = f"UPDATE tasks SET {', '.join(update_fields)} WHERE task_id = %s"
            update_values.append(task_id)
            cursor.execute(update_sql, tuple(update_values))
        conn.commit()
    except Exception as e:
        print(f"failed to update task status: {e}")
    finally:
        if conn:
            conn.close()

    # update Redis cache
    redis_key = settings.TASK_STATUS_KEY.format(task_id=task_id)
    redis_client.hset(redis_key, mapping={
        "status": status,
        "update_time": str(time.time()),
        **kwargs
    })

# update collection progress
def update_collect_progress(task_id, page, collected_count):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            # update collected count and page
            cursor.execute("""
                UPDATE tasks SET collect_page = %s, collect_completed = collect_completed + %s,
                            update_time = CURRENT_TIMESTAMP
                WHERE task_id = %s
            """, (page, collected_count, task_id))
            
            # check if collection is completed
            cursor.execute("""
                SELECT collect_total, collect_completed FROM tasks WHERE task_id = %s
            """, (task_id,))
            progress = cursor.fetchone()
            is_completed = progress["collect_completed"] >= progress["collect_total"]
            
            if is_completed:
                cursor.execute("""
                    UPDATE tasks SET collect_status = 'completed', update_time = CURRENT_TIMESTAMP
                    WHERE task_id = %s
                """, (task_id,))
        conn.commit()

        # update Redis cache
        redis_key = settings.TASK_STATUS_KEY.format(task_id=task_id)
        redis_client.hincrby(redis_key, "collect_completed", collected_count)
        redis_client.hset(redis_key, "collect_page", page)
        
        if progress["collect_total"] > 0:
            progress_percent = round(progress["collect_completed"]/progress["collect_total"]*100, 2)
            redis_client.hset(redis_key, "collect_progress", f"{progress_percent}%")
        
        if is_completed:
            redis_client.hset(redis_key, "collect_status", "completed")
            # enqueue analysis task
            redis_client.lpush(settings.TASK_QUEUE_ANALYZE, json.dumps({"task_id": task_id}))
        
        return is_completed
    except Exception as e:
        print(f"failed to update collection progress: {e}")
        raise e
    finally:
        if conn:
            conn.close()