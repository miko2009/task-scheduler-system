import json
from app.core.database import get_mysql_conn
from app.core.utils import generate_task_id

# create task
def create_task(user_id, ip_address):
    conn = None
    try:
        conn = get_mysql_conn()
        print(f"create user (if not exists): user_id={user_id}, ip_address={ip_address}")
        print(conn)
        with conn.cursor() as cursor:
            cursor.execute("INSERT IGNORE INTO users (user_id, ip_address) VALUES (%s, %s)",
                        (user_id, ip_address))
        
        # generate task ID
        task_id = generate_task_id()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO tasks (task_id, user_id, status)
                VALUES (%s, %s, 'pending')
            """, (task_id, user_id))
        conn.commit()
    except Exception as e:
        print(f"create task failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()

    return task_id

# query task status
def get_task_status(task_id):
    conn = None
    try: 
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT task_id, user_id, status, region_verify_status, region_verify_result,
                    region_retry_count, collect_total, collect_completed, collect_page,
                    collect_status, analysis_status, analysis_result, error_msg,
                    create_time, update_time
                FROM tasks WHERE task_id = %s
            """, (task_id,))
            task = cursor.fetchone()
        
        if task:
            # parse JSON fields
            if task.get("region_verify_result"):
                task["region_verify_result"] = json.loads(task["region_verify_result"])
            if task.get("analysis_result"):
                task["analysis_result"] = json.loads(task["analysis_result"])
            # calculate collection progress
            if task["collect_total"] > 0:
                task["collect_progress"] = f"{round(task['collect_completed']/task['collect_total']*100, 2)}%"
            else:
                task["collect_progress"] = "0%"
        return task
    except Exception as e:
        print(f"query task status failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()

# get task user info
def get_task_user(task_id):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT user_id, ip_address FROM tasks WHERE task_id = %s
            """, (task_id,))
            task = cursor.fetchone()
    except Exception as e:
        print(f"get task user info failed: {e}")
        raise e
    finally:        
        if conn:    
            conn.close()
    return task

def update_verify_task_status(task_id):
    conn = None
    try:
        # update task status based on retry count
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT region_retry_count FROM tasks WHERE task_id = %s
            """, (task_id,))
            current_retry = cursor.fetchone()["region_retry_count"]
            new_status = "retrying" if current_retry > 0 else "verifying"
            cursor.execute("""
                UPDATE tasks SET region_verify_status = %s, status = %s, update_time = CURRENT_TIMESTAMP
                WHERE task_id = %s
            """, (new_status, new_status, task_id))
        conn.commit()
    except Exception as e:
        print(f"update task status failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()
    return new_status