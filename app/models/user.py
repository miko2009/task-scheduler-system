import json
from app.core.database import get_mysql_conn

# get user info
def get_user(app_user_id: str):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM users WHERE app_user_id = %s
            """, (app_user_id,))
            user = cursor.fetchone()
    except Exception as e:
        print(f"get user info failed: {e}")
        raise e
    finally:        
        if conn:    
            conn.close()
    return user

def create_user(user_id: str, email: str) -> str:
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO users (app_user_id, email)
                VALUES (%s, %s)
            """, (user_id, ))
        conn.commit()
    except Exception as e:
        print(f"create user failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()

    return user_id
def update_user_email(app_user_id: str, email: str):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE users SET email = %s WHERE app_user_id = %s
            """, (email, app_user_id))
        conn.commit()
    except Exception as e:
        print(f"update user email failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()
def update_user_available(app_user_id: str, is_available: str):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE users SET is_watch_history_available = %s WHERE app_user_id = %s
            """, (is_available, app_user_id))
        conn.commit()
    except Exception as e:
        print(f"update user available failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()
def update_user(app_user_id: str, time_zone: str, ):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE users SET time_zone = %s WHERE app_user_id = %s
            """, (time_zone, app_user_id))
        conn.commit()
    except Exception as e:
        print(f"update user failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()    
def update_user(app_user_id,archive_user_id: str, provider_unique_id: str, platform_username: str, time_zone: str, anchor_token: str, is_watch_history_available: str):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE users SET 
                    archive_user_id = %s,
                    latest_sec_user_id = %s,
                    platform_username = %s,
                    time_zone = %s,
                    latest_anchor_token = %s,
                    is_watch_history_available = %s
                WHERE app_user_id = %s
            """, (
                archive_user_id,
                provider_unique_id,
                platform_username,
                time_zone,
                anchor_token,
                is_watch_history_available,
                app_user_id
            ))
        conn.commit()
    except Exception as e:
        print(f"update user failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()

def update_user_waitlist(app_user_id: str, waitlist_opt_in: bool, waitlist_opt_in_at):
    conn = None
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE users SET 
                    waitlist_opt_in = %s,
                    waitlist_opt_in_at = %s
                WHERE app_user_id = %s
            """, (
                waitlist_opt_in,
                waitlist_opt_in_at,
                app_user_id
            ))
        conn.commit()
    except Exception as e:
        print(f"update user waitlist failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()