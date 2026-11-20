import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import AuthSession
from tests.conftest import FakeKeitaroStore


async def test_auth_me_unauthenticated_and_protected_route(client: httpx.AsyncClient) -> None:
    me_resp = await client.get("/api/auth/me")
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["authenticated"] is False
    assert data["default_key_configured"] is True

    protected = await client.get("/api/references")
    assert protected.status_code == 401


async def test_login_with_empty_key_uses_default(
    client: httpx.AsyncClient,
    fake_store: FakeKeitaroStore,
) -> None:
    resp = await client.post("/api/auth/login", json={"api_key": ""})
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is True
    assert body["mode"] == "default"
    assert "kt_session" in client.cookies

    refs = await client.get("/api/references")
    assert refs.status_code == 200
    assert "default-test-key" in fake_store.used_api_keys


async def test_login_with_custom_key_and_logout(
    client: httpx.AsyncClient,
    fake_store: FakeKeitaroStore,
    db_session: AsyncSession,
) -> None:
    resp = await client.post("/api/auth/login", json={"api_key": "custom-valid-key"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is True
    assert body["mode"] == "custom"

    refs = await client.get("/api/references")
    assert refs.status_code == 200
    assert "custom-valid-key" in fake_store.used_api_keys

    logout_resp = await client.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    sessions = (await db_session.execute(select(AuthSession))).scalars().all()
    assert len(sessions) == 0

    me_after = await client.get("/api/auth/me")
    assert me_after.json()["authenticated"] is False


async def test_login_invalid_key_rejected(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/auth/login", json={"api_key": "wrong-key"})
    assert resp.status_code == 401


async def test_login_default_missing_returns_503(
    client: httpx.AsyncClient,
    test_settings: Settings,
) -> None:
    test_settings.keitaro_default_api_key = ""
    resp = await client.post("/api/auth/login", json={})
    assert resp.status_code == 503
