from typing import Any, Dict, Optional

import httpx
import os
import sys
from app.core.config import Settings
from app.core.utils import call_api_with_retry
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import json

JSONDict = Dict[str, Any]

class ArchiveClient:
    def __init__(self ) -> None:
        base_url = str(Settings.ARCHIVE_BASE_URL).rstrip("/")
        self.base = base_url
        self.api_key = Settings.ARCHIVE_API_KEY

    def _headers(self) -> Dict[str, str]:
        return {"X-Archive-API-Key": self.api_key}
    async def start_xordi_auth(self, anchor_token: Optional[str] = None) -> JSONDict:
        api_url = self.base + Settings.ARCHIVE_AUTH_START_PATH
        body: JSONDict = {}
        if anchor_token:
            body["anchor_token"] = anchor_token
        return call_api_with_retry("auth_start", "", api_url, body, headers=self._headers())
    
    async def get_redirect(self, archive_job_id: str) -> httpx.Response:
        api_url = self.base + Settings.ARCHIVE_REDIRECT_PATH
        body: JSONDict = {"archive_job_id": archive_job_id}
        return call_api_with_retry("get_redirect", "", api_url, body, headers=self._headers())
    async def get_authorization_code(self, archive_job_id: str) -> httpx.Response:
        return {
            "archive_job_id": "abc",
            "expires_at": "2026-01-10 20:00:01",
            "queue_position": 56,
        }

        api_url = self.base + Settings.ARCHIVE_AUTHENTICATE_PATH
        body: JSONDict = {"archive_job_id": archive_job_id}
        return call_api_with_retry("get_authorization_code", "", api_url, body, headers=self._headers())
    async def finalize_xordi(self, archive_job_id: str, authorization_code: str, anchor_token: Optional[str]) -> JSONDict:
        api_url = self.base + Settings.ARCHIVE_FINALIZE_PATH
        body: JSONDict = {"archive_job_id": archive_job_id, "authorization_code": authorization_code}
        if anchor_token:
            body["anchor_token"] = anchor_token
        return call_api_with_retry("finalize_auth", "", api_url, body, headers=self._headers())
    async def get_watch_history(self, sec_user_id: str, limit: int = 200, before: Optional[str] = None) -> JSONDict:
        api_url = self.base + Settings.ARCHIVE_WATCH_HISTORY_PATH
        params: Dict[str, Any] = {"sec_user_id": sec_user_id, "limit": limit}
        if before:
            params["before"] = before
        return call_api_with_retry("get_watch_history", "", api_url, params, headers=self._headers())
    async def start_watch_history(self, sec_user_id: str, limit: int = 200, max_pages: int = 1, cursor: Optional[str] = None) -> httpx.Response:
        api_url = self.base + Settings.ARCHIVE_WATCH_HISTORY_START_PATH
        body: JSONDict = {"sec_user_id": sec_user_id, "limit": limit, "max_pages": max_pages, "cursor": cursor}
        return call_api_with_retry("start_watch_history", "", api_url, body, headers=self._headers())
    async def finalize_watch_history(self, data_job_id: str, include_rows: bool = True, return_limit: int = 1) -> JSONDict:
        api_url = self.base + Settings.ARCHIVE_WATCH_HISTORY_FINALIZE_PATH
        body: JSONDict = {"data_job_id": data_job_id, "include_rows": include_rows, "return_limit": return_limit}
        return call_api_with_retry("finalize_watch_history", "", api_url, body, headers=self._headers())