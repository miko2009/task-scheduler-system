
from app.core.database import get_mysql_conn
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Tuple

from fastapi import HTTPException, status

from app.core.crypto import encrypt
from app.core.config import Settings

def parse_bearer(auth_header: str) -> str:
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer")
    return auth_header.split(" ", 1)[1]

def create_or_rotate(app_user_id: str, device_id: str, platform: str, app_version: str, os_version: str) -> tuple[str, str]:
    conn = None
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = now + timedelta(days=Settings.SESSION_TTL_DAYS)
    token_encrypted = encrypt(token, Settings.SECRET_KEY)
    try:
        conn = get_mysql_conn()

        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM app_sessions WHERE app_user_id = %s AND device_id = %s AND revoked_at IS NULL
            """, (app_user_id, device_id))
            session = cursor.fetchone()
            if not session:
                session_id = secrets.token_urlsafe(16)
                cursor.execute("""
                    INSERT INTO app_sessions (session_id, app_user_id, device_id, platform, app_version, os_version, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (session_id, app_user_id, device_id, platform, app_version, os_version, expires_at))
            else:
                session_id = session["session_id"]
                cursor.execute("""
                    UPDATE app_sessions
                    SET token_hash = %s, token_encrypted = %s, issued_at = %s, expires_at = %s, platform = %s, app_version = %s, os_version = %s
                    WHERE session_id = %s
                """, (token_hash, token_encrypted, now,  expires_at, platform, app_version, os_version, session_id))
        conn.commit()
      
    except Exception as e:
        print(f"create or rotate session failed: {e}")
        raise e
    finally:
        if conn:
            conn.close()
    return session_id, expires_at

def validate(token: str, device_id: str) -> dict:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM app_sessions WHERE token_hash = %s AND device_id = %s AND revoked_at IS NULL AND expires_at > %s
            """, (token_hash, device_id, datetime.now(timezone.utc)))
            rec = cursor.fetchone()
            if not rec:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_session")

            # sliding TTL
            rec['expires_at'] = datetime.now(timezone.utc) + timedelta(days=Settings.SESSION_TTL_DAYS)
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE app_sessions
                    SET expires_at = %s
                    WHERE session_id = %s
                """, (rec['expires_at'], rec["session_id"]))
        conn.commit()
    except Exception as e:
        print(f"validate session failed: {e}")
        raise e
    finally:
        if conn:    
            conn.close()
    return rec