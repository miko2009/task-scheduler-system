import json
from fastapi import APIRouter, HTTPException, Depends, Header, Request, Response
from pydantic import BaseModel
from app.core.config import settings
from app.core.database import redis_client
from app.models.task import create_task, get_task_status
from app.core.schema import LinkStartResponse, ErrorResponse, RedirectResponse, CodeResponse, FinalizeResponse, FinalizeRequest, VerifyRegionResponse, WrappedRequest, WaitlistRequest,WrappedStatusResponse, WrappedEnqueueResponse
from app.core.archive_client import ArchiveClient
from app.models.user import get_user
from uuid import uuid4
from app.core.verify import verify_user_region
from app.models.task import update_task_status_user_id, get_task_by_user_id
from app.models.user import update_user,update_user_waitlist
from app.models.app_session import create_or_rotate,parse_bearer, validate
import datetime


router = APIRouter()
archive_client = ArchiveClient()

def require_session(
    authorization: str = Header(..., alias="Authorization"),
    device_id: str = Header(..., alias="X-Device-Id"),
    platform: str = Header(..., alias="X-Platform"),
    app_version: str = Header(..., alias="X-App-Version"),
    os_version: str = Header(..., alias="X-OS-Version"),
):
    token = parse_bearer(authorization)
    rec = validate(token, device_id=device_id)
    return rec

def require_device(
    device_id: str = Header(..., alias="X-Device-Id"),
    platform: str = Header(..., alias="X-Platform"),
    app_version: str = Header(..., alias="X-App-Version"),
    os_version: str = Header(..., alias="X-OS-Version"),
):
    return {
        "device_id": device_id,
        "platform": platform,
        "app_version": app_version,
        "os_version": os_version,
    }
@router.post("/start")
async def link_tiktok_start(device=Depends(require_device)) -> LinkStartResponse:
    resp, status_code= await archive_client.start_xordi_auth(anchor_token=None)
    device_id = device.get('device_id')
    task_id = create_task(resp.get("archive_job_id"), device_id)
    # add task to verify queue
    task_data = {
        "task_id": task_id,
        "device_id": device_id
    }
    redis_client.lpush(settings.TASK_QUEUE_VERIFY, json.dumps(task_data))

    # initialize task status in Redis
    redis_key = settings.TASK_STATUS_KEY.format(task_id=task_id)
    redis_client.hset(redis_key, mapping={
        "task_id": task_id,
        "status": "pending",
        "region_retry_count": 0,
        "collect_total": 0,
        "collect_completed": 0,
        "collect_page": 0,
        "collect_progress": "0%",
        "collect_status": "not_started",
        "analysis_status": "not_executed"
    })

    return LinkStartResponse(
        archive_job_id=resp.get("archive_job_id", ""),
        expires_at=resp.get("expires_at"),
        queue_position=resp.get("queue_position"),
    )

@router.get(
    "/redirect",
    response_model=RedirectResponse,
    responses={401: {"model": ErrorResponse}},
)
async def link_tiktok_redirect(job_id: str, device=Depends(require_device)) -> RedirectResponse:
    job = get_task_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    if job.get('device_id') and job.get('device_id') != device.get("device_id"):
        raise HTTPException(status_code=401, detail="invalid_device")
    resp, status_code = await archive_client.get_redirect(job_id)
    if status_code == 200:
        return RedirectResponse(
            status="ready",
            redirect_url=resp.get("redirect_url"),
            queue_position=resp.get("queue_position"),
            qr_data=resp.get("qr_data"),
        )
    if status_code == 202:
        return RedirectResponse(
            status="pending",
            queue_position=resp.get("queue_position"),
            qr_data=resp.get("qr_data"),
        )
    if resp.status_code == 410:
        return RedirectResponse(status="expired")
    raise HTTPException(status_code=resp.status_code, detail=resp.text)


@router.get(
    "/code",
    response_model=CodeResponse,
    responses={401: {"model": ErrorResponse}},
)
async def link_tiktok_code(job_id: str, device=Depends(require_device)) -> CodeResponse:
    device_id = device.get('device_id')
    job = get_task_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    if job.get('device_id') and job.get('device_id') != device_id:
        raise HTTPException(status_code=401, detail="invalid_device")
    resp,status_code = await archive_client.get_authorization_code(job_id)
    if status_code == 200:
        return CodeResponse(
            status="ready",
            authorization_code=resp.get("authorization_code"),
            expires_at=resp.get("expires_at"),
        )
    if status_code == 202:
        return CodeResponse(
            status="pending",
            queue_position=resp.get("queue_position"),
        )
    if status_code == 410:
        return CodeResponse(status="expired")
    raise HTTPException(status_code=status_code, detail=resp)


@router.post(
    "/finalize",
    response_model=FinalizeResponse,
    responses={401: {"model": ErrorResponse}},
)
async def link_tiktok_finalize(
    payload: FinalizeRequest, device=Depends(require_device)
) -> FinalizeResponse:
    job = get_task_status(payload.archive_job_id)
    device_id = job.get('device_id')
    app_user_id = job.get('app_user_id')
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    if device_id and device_id != device.get('device_id'):
        raise HTTPException(status_code=401, detail="invalid_device")
    anchor_token = None
    if app_user_id:
        existing_user = get_user(app_user_id)
        anchor_token = existing_user.get('latest_anchor_token') if existing_user else None
    data, status_code = await archive_client.finalize_xordi(
        archive_job_id=payload.archive_job_id,
        authorization_code=payload.authorization_code,
        anchor_token=anchor_token,
    )
    print('data',data)
    # Bind to canonical app_user_id derived from archive_user_id
    final_app_user_id = data.get("archive_user_id") or (job.get('app_user_id') or str(uuid4()))
    canonical_user = get_user(final_app_user_id)
    if not canonical_user:
        canonical_user = get_user(job.get("app_user_id"))
    previous_sec_user_id = canonical_user.get('latest_sec_user_id')

    # archive_user_id
    canonical_user['archive_user_id'] = data.get("archive_user_id")
    # lastest_sec_user_id
    canonical_user['latest_sec_user_id'] = data.get("provider_unique_id")
    platform_username = data.get("platform_username")

    if platform_username:
        canonical_user['platform_username'] = platform_username
    canonical_user['time_zone'] = payload.time_zone or canonical_user['time_zone']
    new_anchor = data.get("anchor_token")
    if new_anchor or anchor_token:
        canonical_user['latest_anchor_token'] = new_anchor or anchor_token
    if previous_sec_user_id != canonical_user['latest_sec_user_id']:
        canonical_user['is_watch_history_available'] = "unknown"
    update_user(canonical_user.get('app_user_id'), data.get("archive_user_id"), data.get("provider_unique_id"), platform_username, payload.time_zone, canonical_user['latest_anchor_token'], canonical_user['is_watch_history_available'])


    # Rebind auth job to canonical user if it exists
    if job:
        update_task_status_user_id(job.get('task_id'), "finalized", canonical_user.get('app_user_id'))

    token, expires_at = create_or_rotate(
        app_user_id=canonical_user.get('app_user_id'),
        device_id=device.get("device_id"),
        platform=device.get("platform"),
        app_version=device.get("app_version"),
        os_version=device.get("os_version"),
    )
    # Auto-run availability check and enqueue wrapped pipeline on success
    await verify_user_region(canonical_user, payload.archive_job_id, auto_enqueue=True)
    return FinalizeResponse(
        archive_user_id=data.get("archive_user_id", ""),
        sec_user_id=data.get("provider_unique_id", ""),
        anchor_token=canonical_user.get('latest_anchor_token'),
        app_user_id=canonical_user.get('app_user_id'),
        token=token,
        expires_at=expires_at,
        platform_username=canonical_user.get('platform_username'),
    )


@router.post(
    "/verify-region",
    response_model=VerifyRegionResponse,
    responses={401: {"model": ErrorResponse}},
)
async def link_tiktok_verify_region(session=Depends(require_session)) -> VerifyRegionResponse:
    user = get_user(session.get("app_user_id"))
    if not user:
        raise HTTPException(status_code=400, detail="user_not_found")
    status_value, attempts, last_error = await verify_user_region(user, auto_enqueue=True)
    return VerifyRegionResponse(is_watch_history_available=status_value, attempts=attempts, last_error=last_error)

# test
@router.get("/test")
async def test_api(request: Request):
    redis_client.lpush(settings.TASK_QUEUE_EMAIL_SEND, json.dumps({
        "task_id": "aj_3Rsh8RWqU29KPgIm84HFzQ", "user_id": "abc"
    }))
    return {"code": 200, "msg": "test successful"}


@router.post("/waitlist", status_code=204)
async def join_waitlist(payload: WaitlistRequest) -> Response:
    user = get_user(payload.app_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="not_found")
    new_waitlist_opt_in = not bool(user.get('waitlist_opt_in'))
    new_waitlist_opt_in_at = datetime.utcnow() if user.get('waitlist_opt_in') else None
    update_user_waitlist(payload.app_user_id, waitlist_opt_in=new_waitlist_opt_in,waitlist_opt_in_at=new_waitlist_opt_in_at)
    return Response(status_code=204)

@router.get(
    "/wrapped/{app_user_id}",
    response_model=WrappedStatusResponse,
)
async def wrapped_status(
    app_user_id: str
) -> WrappedStatusResponse:
    task = get_task_by_user_id(app_user_id)
 
    if not task:
        raise HTTPException(status_code=404, detail="not_found")
    if task.get('status') != "ready" or not task.payload:
        return WrappedStatusResponse(
            status="pending",
            wrapped_run_id=task.get('task_id'),
            wrapped=None,
            queue_position=None,
            queue_eta_seconds=None,
            queue_status="pending",
        )
    return WrappedStatusResponse(status="ready", wrapped_run_id=task.get('task_id'), wrapped=task)


@router.post(
    "/wrapped-request",
    response_model=WrappedEnqueueResponse,
    responses={401: {"model": ErrorResponse}},
)
async def wrapped_request(
    payload: WrappedRequest, session=Depends(require_session)
) -> WrappedEnqueueResponse:
    
    app_user_id = session.get("app_user_id")
    user = get_user(app_user_id)
    if not user or not user.get('latest_sec_user_id'):
        raise HTTPException(status_code=400, detail="sec_user_id_required")
    user['time_zone'] = payload.time_zone

    is_watch_history_available = user.get('is_watch_history_available')
    # Enforce availability gating with cached value or a fresh check.
    if is_watch_history_available == "unknown":
        availability, _, _ = await verify_user_region(user, None, auto_enqueue=True)
    else:
        availability = is_watch_history_available
    if availability == "no":
        raise HTTPException(status_code=400, detail="watch_history_unavailable")
    if availability == "unknown":
        raise HTTPException(status_code=400, detail="watch_history_unknown")


    task = get_task_by_user_id(app_user_id)
    redis_client.lpush(settings.TASK_QUEUE_RETRY, json.dumps({
        "task_id": task.get('task_id'), "retry_type": "collect"
    }))

    if task.get('status') == "ready":
        return WrappedEnqueueResponse(
            status="ready",
            wrapped_run_id=task.task_id,
            existing_run_id=task.task_id,
            wrapped=task,
            queue_position=0,
            queue_eta_seconds=0,
            queue_status="ready",
        )

    return WrappedEnqueueResponse(
        status="pending",
        wrapped_run_id=task.get('task_id'),
        email_delivery="queued",
        queue_position=None,
        queue_eta_seconds=None,
        queue_status="pending",
    )