import json
import time
import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from app.core.config import settings
from app.core.database import redis_client, get_task_lock, get_mysql_conn
from app.core.utils import call_api_with_retry, update_task_status, update_collect_progress
from app.models.user import get_user
from app.models.task_payload import update_or_create_task_payload
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from app.core.emailer import Emailer
from app.core.archive_client import ArchiveClient
import asyncio
from collections import Counter, defaultdict
from app.core import accessories
import logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("collect_worker")
# settings import
# force add project root to Python path (outermost task_scheduler)

# browse records collect worker
archive_client = ArchiveClient()

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

def summarize_rows(rows: List[Dict[str, Any]], time_zone: Optional[str]) -> Dict[str, Any]:
    tz = _safe_zone(time_zone)
    total_videos = len(rows)
    total_hours = 0.0
    night_seconds = 0.0
    hour_buckets: Dict[int, float] = defaultdict(float)
    music_counter: Counter = Counter()
    creator_counter: Counter = Counter()
    sample_texts: List[str] = []
    source_spans: List[Dict[str, Any]] = []

    for row in rows:
        dur_ms = row.get("duration_ms") or 0
        approx_times = row.get("approx_times_watched") or 1
        watched_at_dt = _to_dt(row.get("watched_at"))
        seconds = (dur_ms / 1000.0) * approx_times
        total_hours += seconds / 3600.0
        if watched_at_dt:
            local = watched_at_dt.astimezone(tz)
            hour_buckets[local.hour] += seconds
            if local.hour >= 22 or local.hour < 4:
                night_seconds += seconds
        music = row.get("music") or row.get("sound_title") or ""
        if music:
            music_title = music.get('title')
            music_counter[music_title] += 1
        author = row.get("author") or row.get("author_id") or ""
        if author:
            creator_counter[author] += 1
        txt_parts = [
            str(row.get("title") or ""),
            str(row.get("description") or ""),
            " ".join(row.get("hashtags") or []),
            str(music.get("title")),
            str(author),
        ]
        sample = " ".join([p for p in txt_parts if p]).strip()
        if sample:
            sample_texts.append(sample[:300])
        source_spans.append({"video_id": row.get("video_id"), "reason": "aggregate"})

    night_pct = (night_seconds / (total_hours * 3600) * 100) if total_hours > 0 else 0.0
    peak_hour = max(hour_buckets.items(), key=lambda x: x[1])[0] if hour_buckets else None
    top_music = {}
    if music_counter:
        music, count = music_counter.most_common(1)[0]
        top_music = {"name": music, "count": count}
    top_creators = [c for c, _ in creator_counter.most_common(5)]

    return {
        "total_videos": total_videos,
        "total_hours": total_hours,
        "night_pct": night_pct,
        "peak_hour": peak_hour,
        "top_music": top_music,
        "top_creators": top_creators,
        "sample_texts": sample_texts[:50],
        "source_spans": source_spans[:200],
    }
async def _fetch_month(sec_user_id: str, month_start_ms: int, month_end_ms: int) -> List[Dict[str, Any]]:
        cursor = str(month_start_ms)
        rows: List[Dict[str, Any]] = []
        start_resp, status_code = await archive_client.start_watch_history(
            sec_user_id=sec_user_id, limit=900, max_pages=50, cursor=cursor
        )
        if not start_resp:
            return rows
        data_job_id = start_resp.get("data_job_id")
        if not data_job_id:
            return rows
        backoff_fin = 1.0
        success_fin = False
        for _ in range(10):
            resp, status_code = await archive_client.finalize_watch_history(
                data_job_id=data_job_id, include_rows=False, return_limit=0
            )
            if status_code == 202:
                await asyncio.sleep(1)
                continue
            if status_code == 200:
                success_fin = True
                break
            if status_code in (410, 424):
                return rows
            await asyncio.sleep(backoff_fin)
            backoff_fin = min(backoff_fin * 2, 8.0)
        if not success_fin:
            return rows
        before = None
        while True:
            resp, status_code = await archive_client.get_watch_history(sec_user_id=sec_user_id, limit=900, before=before)
            if not resp or "rows" not in resp:
                break
            batch = resp.get("rows") or []
            if not batch:
                break
            for item in batch:
                watched_at = _to_dt(item.get("watched_at"))
                if watched_at:
                    ts_ms = int(watched_at.timestamp() * 1000)
                    if ts_ms >= month_end_ms:
                        print("ts_ms > month_end_ms", ts_ms, month_end_ms)
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
            task_id = None
            # wait for collect or retry task
            task_data_str = redis_client.brpop([retry_queue, collect_queue], timeout=5)
            if not task_data_str:
                logging.warning(f"collection task:{task_id} and {task_data_str} not found, skip")
                continue

            queue_name, task_data_str = task_data_str
            task_data = json.loads(task_data_str)
            task_id = task_data.get("task_id")
            user_id = task_data.get("user_id")
            
            # if from retry queue and retry_type is collect, get user_id from DB if not provided
            if not user_id:
                logging.warning(f"collection task:{task_id} and {user_id} not found, skip")
                continue
            
            user = get_user(user_id)  # ensure user exists
            latest_sec_user_id = user.get('latest_sec_user_id')
            if not user or latest_sec_user_id is None:
                logging.warning(f"collection task:{task_id} user {user_id} not found, skip")
                continue
            # get distributed lock
            lock = get_task_lock(task_id)
            if not lock.acquire(blocking=False):
                logging.warning(f"collection task:{task_id}is already being processed, skip")
                continue

            try:
                # check task status
                conn = get_mysql_conn()
                with conn.cursor() as cursor:
                    cursor.execute("SELECT status FROM tasks WHERE task_id = %s", (task_id))
                    task_status = cursor.fetchone()["status"]

                if task_status in ["paused", "cancelled"]:
                    logging.warning(f"collection task:{task_id} status is {task_status}, stop collection")
                    continue

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
                        coros.append(_fetch_month(latest_sec_user_id, start_ms, end_ms))
                    # launch bounded concurrent fetches within the batch
                    batch_rows = await asyncio.gather(*coros)
                    for r in batch_rows:
                        rows.extend(r)
                    idx += len(batch)
                    await asyncio.sleep(1)  # 1 start/sec pacing between batches

                if not rows:
                    logging.warning(f"collection task:{task_id} not rows, skip")
                    continue
                summary = summarize_rows(rows, user.get("time_zone"))
                payload = {
                    "total_hours": summary["total_hours"],
                    "total_videos": summary["total_videos"],
                    "night_pct": summary["night_pct"],
                    "peak_hour": summary["peak_hour"],
                    "top_music": summary["top_music"],
                    "top_creators": summary["top_creators"],
                    "platform_username": user.get("platform_username"),
                    "email": user.get("email"),
                    "source_spans": summary["source_spans"],
                    "data_jobs": {"watch_history": {"id": task_id, "status": "succeeded"}},
                    "_sample_texts": summary["sample_texts"],
                  #  "accessory_set": accessories.select_accessory_set(),
                }
                redis_client.lpush(settings.TASK_QUEUE_ANALYZE, json.dumps({
                    "task_id": task_id, "user_id": user_id
                }))
                
                update_task_status(task_id, "analyzing", collect_status="completed")
                update_or_create_task_payload(task_id, json.dumps(payload), user_id)
            except Exception as e:
                update_task_status(task_id, "failed", collect_status="failed", error_msg=f"collection exception: {e}")
                logging.error(f"collection task {task_id} error", e)
            finally:
                lock.release()
                if conn:
                    conn.close()
        except Exception as e:
            logging.error(f"collection task {task_id} worker error", e)

        time.sleep(0.01)

if __name__ == "__main__":
     asyncio.run( collect_worker())