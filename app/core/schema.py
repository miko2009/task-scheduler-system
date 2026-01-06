from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class ErrorResponse(BaseModel):
    error: str
    message: Optional[str] = None


class LinkStartResponse(BaseModel):
    archive_job_id: str
    expires_at: Optional[datetime] = None
    queue_position: Optional[int] = None


class RedirectResponse(BaseModel):
    redirect_url: Optional[str] = None
    status: Literal["pending", "ready", "expired"] = "pending"
    queue_position: Optional[int] = None
    qr_data: Optional[Dict[str, Any]] = None


class CodeResponse(BaseModel):
    authorization_code: Optional[str] = None
    status: Literal["pending", "ready", "expired"] = "pending"
    expires_at: Optional[datetime] = None
    queue_position: Optional[int] = None


class FinalizeRequest(BaseModel):
    archive_job_id: str
    authorization_code: str
    time_zone: Optional[str] = None


class FinalizeResponse(BaseModel):
    archive_user_id: str
    sec_user_id: str
    anchor_token: Optional[str] = None
    app_user_id: str
    token: str
    expires_at: datetime
    platform_username: Optional[str] = None


class VerifyRegionResponse(BaseModel):
    is_watch_history_available: Literal["unknown", "yes", "no"]
    attempts: int
    last_error: Optional[str] = None


class WrappedRequest(BaseModel):
    email: EmailStr
    time_zone: str


class RegisterEmailRequest(BaseModel):
    email: EmailStr


class WaitlistRequest(BaseModel):
    app_user_id: str


class DataJobRef(BaseModel):
    id: str
    status: Literal["pending", "running", "succeeded", "failed", "unknown"] = "pending"


class AccessoryItem(BaseModel):
    item_id: str
    display_name: str
    set_series: str
    quality: str
    reason: str


class AccessorySet(BaseModel):
    head: AccessoryItem
    body: AccessoryItem
    other: AccessoryItem


class WrappedPayload(BaseModel):
    total_hours: float
    total_videos: int
    night_pct: float
    peak_hour: Optional[int] = None
    top_music: Dict[str, Any]
    top_creators: List[str]
    personality_type: str
    personality_explanation: Optional[str] = None
    niche_journey: List[str]
    top_niches: List[str]
    top_niche_percentile: Optional[str] = None
    brain_rot_score: int
    brain_rot_explanation: Optional[str] = None
    keyword_2026: str
    thumb_roast: Optional[str] = None
    platform_username: Optional[str] = None
    email: Optional[str] = None
    source_spans: List[Dict[str, Any]] = []
    data_jobs: Dict[str, DataJobRef]
    accessory_set: AccessorySet


class WrappedEnqueueResponse(BaseModel):
    status: Literal["pending", "ready"]
    wrapped_run_id: Optional[str] = None
    existing_run_id: Optional[str] = None
    email_delivery: Optional[str] = None
    wrapped: Optional[WrappedPayload] = None
    queue_position: Optional[int] = None
    queue_eta_seconds: Optional[int] = None
    queue_status: Optional[str] = None


class WrappedStatusResponse(BaseModel):
    status: Literal["pending", "ready"]
    wrapped_run_id: str
    wrapped: Optional[WrappedPayload] = None
    queue_position: Optional[int] = None
    queue_eta_seconds: Optional[int] = None
    queue_status: Optional[str] = None
