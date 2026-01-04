import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.core.config import settings
from app.core.database import redis_client
from app.models.task import create_task, get_task_status, get_task_user
from app.models.api_log import get_task_api_logs
from app.core.utils import update_task_status, get_retry_strategy
from app.api.auth import get_current_user

router = APIRouter()

# task request models
class TaskCreateRequest(BaseModel):
    user_id: str
    ip_address: str

class TaskInterveneRequest(BaseModel):
    task_id: str
    action: str  # pause/cancel/retry_verify/retry_collect/retry_analyze/rerun

# create task
@router.post("/create")
async def create_task_api(request: TaskCreateRequest):
    try:
        task_id = create_task(request.user_id, request.ip_address)
        print(f"task created: {task_id}")
        # add task to verify queue
        task_data = {
            "task_id": task_id,
            "user_id": request.user_id,
            "ip_address": request.ip_address
        }
        redis_client.lpush(settings.TASK_QUEUE_VERIFY, json.dumps(task_data))

        # initialize task status in Redis
        redis_key = settings.TASK_STATUS_KEY.format(task_id=task_id)
        redis_client.hset(redis_key, mapping={
            "task_id": task_id,
            "user_id": request.user_id,
            "status": "pending",
            "region_retry_count": 0,
            "collect_total": 0,
            "collect_completed": 0,
            "collect_page": 0,
            "collect_progress": "0%",
            "collect_status": "not_started",
            "analysis_status": "not_executed"
        })
        return {"code": 200, "msg": "task created successfully", "data": {"task_id": task_id}}
    except Exception as e:
        print(f"failed to create task: {e}")
        raise HTTPException(status_code=500, detail=f"failed to create task: {e}")

# get task status
@router.get("/status/{task_id}")
async def get_task_status_api(task_id: str):
    try:
        # Check Redis first
        redis_key = settings.TASK_STATUS_KEY.format(task_id=task_id)
        task_status = redis_client.hgetall(redis_key)
        if task_status:
            return {"code": 200, "msg": "success", "data": task_status}
        
        # Fallback to MySQL
        task = get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        
        # Sync to Redis
        redis_client.hset(redis_key, mapping=task)
        return {"code": 200, "msg": "success", "data": task}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to get task status: {e}")

# intervene task
@router.post("/intervene")
async def intervene_task_api(request: TaskInterveneRequest):
    try:
        action = request.action.lower()
        task_id = request.task_id
        valid_actions = ["pause", "cancel", "retry_verify", "retry_collect", "retry_analyze", "rerun"]
        
        if action not in valid_actions:
            raise HTTPException(status_code=400, detail=f"action not supported {valid_actions}")
        
        task = get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        
        if action == "pause":
            update_task_status(task_id, "paused")
            msg = "task paused"
        elif action == "cancel":
            update_task_status(task_id, "cancelled", error_msg="user manually cancelled")
            msg = "task cancelled"
        elif action == "retry_verify":
            region_strategy = get_retry_strategy("region_verify")
            if task["region_verify_status"] not in ["failed", "timeout"]:
                raise HTTPException(status_code=400, detail="only region verification failed/timeout can be retried")
            if task["region_retry_count"] >= region_strategy["max_retry_count"]:
                raise HTTPException(status_code=400, detail=f"已达最大重试次数({region_strategy['max_retry_count']}次)")
            
            redis_client.lpush(settings.TASK_QUEUE_RETRY, json.dumps({
                "task_id": task_id, "retry_type": "verify"
            }))
            update_task_status(task_id, "pending", region_retry_count=task["region_retry_count"] + 1)
            msg = "region verification task added to retry queue"
        elif action == "retry_collect":
            if task["collect_status"] not in ["failed"]:
                raise HTTPException(status_code=400, detail="only collection failed can be retried")
            if task["region_verify_status"] != "success":
                raise HTTPException(status_code=400, detail="region verification not successful, cannot retry collection")
            
            redis_client.lpush(settings.TASK_QUEUE_RETRY, json.dumps({
                "task_id": task_id, "retry_type": "collect"
            }))
            update_task_status(task_id, "pending")
            msg = "collection task added to retry queue"
        elif action == "retry_analyze":
            if task["analysis_status"] not in ["failed", "timeout"]:
                raise HTTPException(status_code=400, detail="only analysis failed/timeout can be retried")
            if task["collect_status"] != "completed":
                raise HTTPException(status_code=400, detail="collection not completed, cannot retry analysis")
            
            redis_client.lpush(settings.TASK_QUEUE_RETRY, json.dumps({
                "task_id": task_id, "retry_type": "analyze"
            }))
            update_task_status(task_id, "pending")
            msg = "analysis task added to retry queue"
        elif action == "rerun":
            task_user = get_task_user(task_id)
            task_data = {
                "task_id": task_id,
                "user_id": task_user["user_id"],
                "ip_address": task_user["ip_address"]
            }
            redis_client.lpush(settings.TASK_QUEUE_VERIFY, json.dumps(task_data))
            update_task_status(task_id, "pending", region_retry_count=0, error_msg="")
            msg = "task rerunned from verification queue"
        
        return {"code": 200, "msg": msg, "data": {"task_id": task_id}}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"intervene failed: {e}")

# 查询任务日志
@router.get("/logs/{task_id}")
async def get_task_logs_api(task_id: str):
    try:
        logs = get_task_api_logs(task_id)
        return {"code": 200, "msg": "查询成功", "data": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询日志失败: {e}")
    
# test
@router.get("/test")
async def test_api():
    return {"code": 200, "msg": "test successful"}