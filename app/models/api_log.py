from app.core.database import get_mysql_conn

# query task API call logs
def get_task_api_logs(task_id):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT log_id, api_type, request_url, request_params, response_data,
                    cost_time, status, error_detail, retry_count, call_time
                FROM api_call_logs WHERE task_id = %s ORDER BY call_time DESC
            """, (task_id,))
            logs = cursor.fetchall()
    except Exception as e:
        print(f"query task API logs failed: {e}")
        logs = []
        raise e
    finally:
        if conn:
            conn.close()
    return logs