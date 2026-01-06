import json
from app.core.database import get_mysql_conn
from app.core.utils import generate_task_id

# create task
def create_task(archive_job_id:str, device_id:str="") -> str:
    conn = None
    try:
        conn = get_mysql_conn()
        # print(f"create user (if not exists): user_id={user_id}, ip_address={ip_address}")
        # print(conn)
        # with conn.cursor() as cursor:
        #     cursor.execute("INSERT IGNORE INTO users (user_id, ip_address) VALUES (%s, %s)",
        #                 (user_id, ip_address))
        
        # generate task ID
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO tasks (task_id, device_id, status)
                VALUES (%s, %s, 'pending')
            """, (archive_job_id, device_id))
        conn.commit()
    except Exception as e:
        print(f"create task failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()

    return archive_job_id

# query task status
def get_task_status(task_id):
    conn = None
    try: 
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT *
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
def update_task_status_user_id(task_id: str, status: str, app_user_id: str = ""):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            sql = "UPDATE tasks SET status = %s, app_user_id = %s WHERE task_id = %s"
            params = [status, app_user_id, task_id]
            cursor.execute(sql, tuple(params))
        conn.commit()
    except Exception as e:
        print(f"update task failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()


def update_task_email_status(task_id: str, status: str):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            sql = "UPDATE tasks SET email_status = %s WHERE task_id = %s"
            params = [status, task_id]
            cursor.execute(sql, tuple(params))
        conn.commit()
    except Exception as e:
        print(f"update task email status failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()

def get_task_by_user_id(app_user_id: str):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM tasks WHERE app_user_id = %s ORDER BY create_time DESC
            """, (app_user_id,))
            task = cursor.fetchone()
    except Exception as e:
        print(f"get tasks by user id failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()
    return task