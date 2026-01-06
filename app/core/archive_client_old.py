from typing import Any, Dict, Optional

import httpx

from app.core.settings import Settings

JSONDict = Dict[str, Any]


class ArchiveClient:
    def __init__(self, settings: Settings) -> None:
        base_url = str(settings.archive_base_url).rstrip("/")
        self.base = base_url
        self.api_key = settings.archive_api_key.get_secret_value()
        self._client = httpx.AsyncClient(base_url=self.base, timeout=30.0)

    async def _headers(self) -> Dict[str, str]:
        return {"X-Archive-API-Key": self.api_key, "Content-Type": "application/json"}

    async def start_xordi_auth(self, anchor_token: Optional[str] = None) -> JSONDict:
        body: JSONDict = {}
        if anchor_token:
            body["anchor_token"] = anchor_token
        resp = await self._client.post("/archive/xordi/start-auth", json=body, headers=await self._headers())
        resp.raise_for_status()
        return resp.json()

    async def get_redirect(self, archive_job_id: str) -> httpx.Response:
        return await self._client.get(
            "/archive/xordi/get-redirect",
            params={"archive_job_id": archive_job_id},
            headers=await self._headers(),
        )

    async def get_authorization_code(self, archive_job_id: str) -> httpx.Response:
        return await self._client.get(
            "/archive/xordi/get-authorization-code",
            params={"archive_job_id": archive_job_id},
            headers=await self._headers(),
        )

    async def finalize_xordi(self, archive_job_id: str, authorization_code: str, anchor_token: Optional[str]) -> JSONDict:
        body: JSONDict = {"archive_job_id": archive_job_id, "authorization_code": authorization_code}
        if anchor_token:
            body["anchor_token"] = anchor_token
        resp = await self._client.post("/archive/xordi/finalize", json=body, headers=await self._headers())
        resp.raise_for_status()
        return resp.json()

    async def get_watch_history(self, sec_user_id: str, limit: int = 200, before: Optional[str] = None) -> JSONDict:
        params: Dict[str, Any] = {"sec_user_id": sec_user_id, "limit": limit}
        if before:
            params["before"] = before
        resp = await self._client.get("/archive/xordi/watch-history", params=params, headers=await self._headers())
        resp.raise_for_status()
        return resp.json()

    async def start_watch_history(self, sec_user_id: str, limit: int = 200, max_pages: int = 1, cursor: Optional[str] = None) -> httpx.Response:
        body: JSONDict = {"sec_user_id": sec_user_id, "limit": limit, "max_pages": max_pages, "cursor": cursor}
        return await self._client.post("/archive/xordi/watch-history/start", json=body, headers=await self._headers())

    async def finalize_watch_history(
        self, data_job_id: str, include_rows: bool = True, return_limit: Optional[int] = None
    ) -> httpx.Response:
        body: JSONDict = {"data_job_id": data_job_id, "include_rows": include_rows}
        if return_limit is not None:
            body["return_limit"] = return_limit
        return await self._client.post("/archive/xordi/watch-history/finalize", json=body, headers=await self._headers())
