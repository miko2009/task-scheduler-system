import json
import time
import multiprocessing
import os
import sys

from app.core.config import settings
from app.core.database import redis_client, get_task_lock, get_mysql_conn
from app.core.utils import update_task_status, call_api_with_retry
from app.models.task import update_verify_task_status
from app.models.user import update_user_available
from app.core.archive_client import ArchiveClient

archive_client = ArchiveClient()
def verify_user_region(user, auto_enqueue, task_id):

    try:
       start_resp = archive_client.start_watch_history(user.latest_sec_user_id, limit=1, max_pages=1, cursor=None)
    except Exception as e:
        return "timeout" if "timeout" in str(e) else "failed", {}, str(e)

    # call finalize watch history API
    try:
        result = archive_client.finalize_watch_history(data_job_id=start_resp.get("data_job_id"), include_rows=True, return_limit=1)
        user.is_watch_history_available = "yes"
    except Exception as e:
        return "timeout" if "timeout" in str(e) else "failed", {}, str(e)
    redis_client.lpush(settings.TASK_QUEUE_COLLECT, json.dumps({
        "app_user_id": user.app_user_id,
        "sec_user_id": user.latest_sec_user_id,
        "time_zone": user.time_zone,
        "platform_username": user.platform_username,
    }))
    if user.is_watch_history_available != "yes" and auto_enqueue:
        user.is_watch_history_available = "no"    
    update_user_available(user.app_user_id, user.is_watch_history_available)
    if task_id:
        update_verify_task_status(task_id)
    return user.is_watch_history_available, result, ""
