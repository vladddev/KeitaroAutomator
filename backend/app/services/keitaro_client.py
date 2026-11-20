import hashlib
import time
from typing import Any

import httpx


class KeitaroError(Exception):
    """Base error raised when Keitaro Admin API returns an error or fails."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class KeitaroAuthError(KeitaroError):
    """Raised when Keitaro rejects the provided API key."""


class KeitaroUnavailableError(KeitaroError):
    """Raised when Keitaro API is unreachable or times out."""


_OFFERS_CACHE: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}
_OFFERS_TTL_SECONDS = 60.0


def clear_offers_cache() -> None:
    _OFFERS_CACHE.clear()


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text or f"Keitaro API вернул HTTP {response.status_code}"

    if isinstance(payload, dict):
        for key in ("error", "message", "detail"):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
            if isinstance(val, dict):
                return str(val)
        return str(payload)
    if isinstance(payload, list) and payload:
        return "; ".join(str(item) for item in payload)
    return f"Keitaro API вернул HTTP {response.status_code}"


class KeitaroClient:
    """Async HTTP client wrapper around Keitaro Admin API v1."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "KeitaroClient":
        self._client = self._build_client()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Api-Key": self.api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def _cache_key(self) -> tuple[str, str]:
        digest = hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()[:16]
        return (self.base_url, digest)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        owns_client = self._client is None
        client = self._client if self._client is not None else self._build_client()
        try:
            response = await client.request(method, path, params=params, json=json)
        except httpx.RequestError as exc:
            raise KeitaroUnavailableError(
                502, f"Не удалось подключиться к Keitaro API: {exc}"
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        if response.status_code in (401, 403):
            raise KeitaroAuthError(401, "Неверный или неактивный API ключ Keitaro")

        if response.status_code >= 400:
            detail = _extract_error_detail(response)
            mapped_status = response.status_code if response.status_code in (400, 404, 422) else 502
            raise KeitaroError(mapped_status, f"Ошибка Keitaro API ({response.status_code}): {detail}")

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    async def validate_api_key(self) -> None:
        await self.get_domains()

    async def get_domains(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/domains")
        return list(data) if isinstance(data, list) else []

    async def get_campaign_groups(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/groups", params={"type": "campaigns"})
        return list(data) if isinstance(data, list) else []

    async def get_traffic_sources(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/traffic_sources")
        return list(data) if isinstance(data, list) else []

    async def get_offers(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        key = self._cache_key()
        now = time.monotonic()
        if not refresh and key in _OFFERS_CACHE:
            expires_at, cached = _OFFERS_CACHE[key]
            if now < expires_at:
                return list(cached)

        data = await self._request("GET", "/offers")
        offers = list(data) if isinstance(data, list) else []
        _OFFERS_CACHE[key] = (now + _OFFERS_TTL_SECONDS, offers)
        return list(offers)

    async def get_campaigns(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/campaigns")
        return list(data) if isinstance(data, list) else []

    async def get_campaign(self, campaign_id: int) -> dict[str, Any]:
        data = await self._request("GET", f"/campaigns/{campaign_id}")
        if not isinstance(data, dict):
            raise KeitaroError(502, "Некорректный ответ Keitaro при получении кампании")
        return data

    async def create_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = await self._request("POST", "/campaigns", json=payload)
        if not isinstance(data, dict):
            raise KeitaroError(502, "Некорректный ответ Keitaro при создании кампании")
        return data

    async def get_campaign_streams(self, campaign_id: int) -> list[dict[str, Any]]:
        data = await self._request("GET", f"/campaigns/{campaign_id}/streams")
        return list(data) if isinstance(data, list) else []

    async def create_stream(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = await self._request("POST", "/streams", json=payload)
        if not isinstance(data, dict):
            raise KeitaroError(502, "Некорректный ответ Keitaro при создании потока")
        return data

    async def update_stream(self, stream_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        data = await self._request("PUT", f"/streams/{stream_id}", json=payload)
        if not isinstance(data, dict):
            raise KeitaroError(502, "Некорректный ответ Keitaro при обновлении потока")
        return data
