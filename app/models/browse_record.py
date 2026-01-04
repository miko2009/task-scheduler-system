from app.core.database import get_mysql_conn

# batch insert browse records
def batch_insert_browse_records(task_id, user_id, records):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO browse_records (task_id, user_id, url, browse_time, stay_duration)
                VALUES (%s, %s, %s, %s, %s)
            """
            data = [
                (task_id, user_id, r["url"], r["browse_time"], r["stay_duration"])
                for r in records
            ]
            cursor.executemany(sql, data)
        conn.commit()
    except Exception as e:
        print(f"batch insert browse records failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()