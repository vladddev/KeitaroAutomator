from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.deps import get_keitaro_client_factory
from app.main import app
from app.services.keitaro_client import KeitaroAuthError, KeitaroError


class FakeKeitaroStore:
    """In-memory mock state simulating Keitaro Admin API resources."""

    def __init__(self) -> None:
        self.valid_keys: set[str] = {"default-test-key", "custom-valid-key"}
        self.fail_on_stream_number: int | None = None
        self.domains: list[dict[str, Any]] = [
            {"id": 10, "name": "track.example.com"},
            {"id": 11, "name": "alt.example.com"},
        ]
        self.groups: list[dict[str, Any]] = [
            {"id": 20, "name": "Test Group"},
            {"id": 21, "name": "Second Group"},
        ]
        self.traffic_sources: list[dict[str, Any]] = [
            {"id": 30, "name": "Google Ads"},
            {"id": 31, "name": "Facebook"},
        ]
        self.offers: list[dict[str, Any]] = [
            {"id": 101, "name": "Offer Alpha", "state": "active"},
            {"id": 102, "name": "Offer Beta", "state": "active"},
            {"id": 103, "name": "Offer Gamma", "state": "active"},
            {"id": 104, "name": "Offer Delta", "state": "active"},
        ]
        self.campaigns: dict[int, dict[str, Any]] = {
            500: {
                "id": 500,
                "name": "test_lukashov_existing",
                "alias": "existing-500",
                "domain_id": 10,
                "group_id": 20,
                "traffic_source_id": 30,
                "state": "active",
            }
        }
        self.streams: dict[int, dict[str, Any]] = {
            5001: {
                "id": 5001,
                "campaign_id": 500,
                "type": "regular",
                "name": "Geo US -> Google",
                "position": 1,
                "state": "active",
                "schema": "redirect",
                "action_type": "http",
                "action_payload": "https://www.google.com",
                "filters": [{"name": "country", "mode": "accept", "payload": ["US"]}],
                "offers": [],
            },
            5002: {
                "id": 5002,
                "campaign_id": 500,
                "type": "regular",
                "name": "Main Offers",
                "position": 2,
                "state": "active",
                "schema": "landings",
                "filters": [],
                "landings": [],
                "offers": [
                    {"offer_id": 101, "share": 50, "state": "active"},
                    {"offer_id": 102, "share": 50, "state": "active"},
                ],
            },
        }
        self._next_campaign_id = 501
        self._next_stream_id = 5003
        self.used_api_keys: list[str] = []


class FakeKeitaroClient:
    """Drop-in async replacement for KeitaroClient backed by FakeKeitaroStore."""

    def __init__(self, store: FakeKeitaroStore, api_key: str) -> None:
        self.store = store
        self.api_key = api_key
        self._stream_create_attempts = 0

    async def __aenter__(self) -> "FakeKeitaroClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def _check_auth(self) -> None:
        self.store.used_api_keys.append(self.api_key)
        if self.api_key not in self.store.valid_keys:
            raise KeitaroAuthError(401, "Неверный или неактивный API ключ Keitaro")

    async def validate_api_key(self) -> None:
        self._check_auth()

    async def get_domains(self) -> list[dict[str, Any]]:
        self._check_auth()
        return deepcopy(self.store.domains)

    async def get_campaign_groups(self) -> list[dict[str, Any]]:
        self._check_auth()
        return deepcopy(self.store.groups)

    async def get_traffic_sources(self) -> list[dict[str, Any]]:
        self._check_auth()
        return deepcopy(self.store.traffic_sources)

    async def get_offers(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        self._check_auth()
        return deepcopy(self.store.offers)

    async def get_campaigns(self) -> list[dict[str, Any]]:
        self._check_auth()
        return deepcopy(list(self.store.campaigns.values()))

    async def get_campaign(self, campaign_id: int) -> dict[str, Any]:
        self._check_auth()
        if campaign_id not in self.store.campaigns:
            raise KeitaroError(404, f"Campaign {campaign_id} not found")
        return deepcopy(self.store.campaigns[campaign_id])

    async def create_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._check_auth()
        cid = self.store._next_campaign_id
        self.store._next_campaign_id += 1
        record = {"id": cid, **deepcopy(payload)}
        self.store.campaigns[cid] = record
        return deepcopy(record)

    async def get_campaign_streams(self, campaign_id: int) -> list[dict[str, Any]]:
        self._check_auth()
        return [
            deepcopy(st)
            for st in self.store.streams.values()
            if st["campaign_id"] == campaign_id
        ]

    async def create_stream(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._check_auth()
        self._stream_create_attempts += 1
        if (
            self.store.fail_on_stream_number is not None
            and self._stream_create_attempts == self.store.fail_on_stream_number
        ):
            raise KeitaroError(422, "Simulated stream creation failure")
        sid = self.store._next_stream_id
        self.store._next_stream_id += 1
        record = {"id": sid, **deepcopy(payload)}
        self.store.streams[sid] = record
        return deepcopy(record)

    async def update_stream(self, stream_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        self._check_auth()
        if stream_id not in self.store.streams:
            raise KeitaroError(404, f"Stream {stream_id} not found")
        updated = {"id": stream_id, **deepcopy(payload)}
        self.store.streams[stream_id] = updated
        return deepcopy(updated)


@pytest.fixture
def fake_store() -> FakeKeitaroStore:
    return FakeKeitaroStore()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite:///:memory:",
        keitaro_api_url="https://fake-keitaro.local/admin_api/v1",
        keitaro_default_api_key="default-test-key",
        default_campaign_prefix="test_lukashov_",
        default_domain_id=None,
        default_group_id=None,
        default_traffic_source_id=None,
        cookie_secure=False,
        session_ttl_hours=24,
    )


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(
    db_session: AsyncSession,
    fake_store: FakeKeitaroStore,
    test_settings: Settings,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    def override_get_settings() -> Settings:
        return test_settings

    def override_client_factory() -> Any:
        def _factory(_base_url: str, api_key: str) -> FakeKeitaroClient:
            return FakeKeitaroClient(fake_store, api_key)

        return _factory

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_keitaro_client_factory] = override_client_factory

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest.fixture
async def auth_client(client: httpx.AsyncClient) -> httpx.AsyncClient:
    resp = await client.post("/api/auth/login", json={})
    assert resp.status_code == 200
    return client
