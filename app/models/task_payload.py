
from app.core.database import get_mysql_conn
import json

def update_or_create_task_payload(tasK_id: str, payload: str, app_user_id: str):
    conn = None
    print(payload)
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                select task_id from task_payload WHERE task_id = %s
            """, (tasK_id))
            task_payload = cursor.fetchone()
            if not task_payload:
                print("task_id",tasK_id)
                print("payload", payload)
                cursor.execute("""
                    INSERT INTO task_payload (task_id, app_user_id, payload)
                    VALUES (%s, %s, %s)
                """, (tasK_id, app_user_id, payload))
            else:
                cursor.execute("""
                    UPDATE task_payload SET payload = %s WHERE task_id = %s
                """, (payload,  tasK_id))
        conn.commit()
    except Exception as e:
        print(f"update task payload failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()

# query task status
def get_task_payload(task_id):
    conn = None
    try: 
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT *
                FROM task_payload WHERE task_id = %s
            """, (task_id,))
            task_payload = cursor.fetchone()
        
        if task_payload:
            # parse JSON fields
            if task_payload.get("payload"):
                task_payload["payload"] = json.loads(task_payload["payload"])
        return task_payload
    except Exception as e:
        print(f"query task status failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()