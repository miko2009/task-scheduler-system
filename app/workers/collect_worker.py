import json
import time
import os
import sys
from app.core.config import settings
from app.core.database import redis_client, get_task_lock, get_mysql_conn
from app.core.utils import call_api_with_retry, update_task_status, update_collect_progress
from app.models.browse_record import batch_insert_browse_records
from app.models.user import get_user
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from app.core.emailer import Emailer
from app.core.archive_client import ArchiveClient
# settings import
# force add project root to Python path (outermost task_scheduler)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
# browse records collect worker
import asyncio
archive_client = ArchiveClient()

def _get_emailer() -> Emailer:
    global _emailer
    if _emailer is None:
        _emailer = Emailer()
    return _emailer


def _safe_zone(tz_name: Optional[str]) -> ZoneInfo:
    if not tz_name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _to_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except Exception:
        return None
async def _fetch_month(sec_user_id: str, month_start_ms: int, month_end_ms: int) -> List[Dict[str, Any]]:
        cursor = str(month_start_ms)
        rows: List[Dict[str, Any]] = []
        start_resp = await archive_client.start_watch_history(
            sec_user_id=sec_user_id, limit=900, max_pages=50, cursor=cursor
        )
        if not start_resp:
            return rows
        data_job_id = start_resp.get("data_job_id")
        if not data_job_id:
            return rows
        finalize_resp = await archive_client.finalize_watch_history(
            data_job_id=data_job_id, include_rows=True, return_limit=1)
        if not finalize_resp:
            return rows
        before = None
        while True:
            resp = await archive_client.get_watch_history(sec_user_id=sec_user_id, limit=900, before=before)
            if not resp or "items" not in resp:
                break
            batch = resp.get("items") or []
            if not batch:
                break
            for item in batch:
                watched_at = _to_dt(item.get("watched_at"))
                if watched_at:
                    ts_ms = int(watched_at.timestamp() * 1000)
                    if ts_ms >= month_end_ms:
                        continue
                    if ts_ms < month_start_ms:
                        return rows
                rows.append(item)
            before = resp.get("next_before")
            if not before:
                break
        return rows


async def collect_worker():
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
                continue
            
            user = get_user(user_id)  # ensure user exists
            if not user or user.latest_sec_user_id is None:
                print(f"collection task:{task_id} user {user_id} not found, skip")
                continue
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
                    print(f"collection task:{task_id} status is {task_status}, stop collection")
                    continue
                sec_user_id = user.latest_sec_user_id
                rows: List[Dict[str, Any]] = []
                month_starts = [(2025, m, 1) for m in range(1, 13)]
                idx = 0
                while idx < len(month_starts):
                    batch = month_starts[idx : idx + 10]  # cap to Archive per-account queue limit
                    coros = []
                    for year, month, day in batch:
                        start_dt = datetime(year, month, day)
                        end_dt = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
                        start_ms = int(start_dt.timestamp() * 1000)
                        end_ms = int(end_dt.timestamp() * 1000)
                        await coros.append(_fetch_month(sec_user_id, start_ms, end_ms))
                    # launch bounded concurrent fetches within the batch
                    batch_rows = await asyncio.gather(*coros)
                    for r in batch_rows:
                        rows.extend(r)
                    idx += len(batch)
                    await asyncio.sleep(1)  # 1 start/sec pacing between batches

                redis_client.lpush(settings.TASK_QUEUE_ANALYZE, json.dumps({
                    "task_id": task_id, "user_id": user_id
                }))
            except Exception as e:
                update_task_status(task_id, "failed", collect_status="failed", error_msg=f"collection exception: {e}")
                print(f"collection task {task_id} exception: {e}")
            finally:
                lock.release()
        except Exception as e:
            print(f"collection worker exception: {e}")
        time.sleep(0.01)

if __name__ == "__main__":
      asyncio.run(collect_worker())