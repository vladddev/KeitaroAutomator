import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Campaign, Stream
from tests.conftest import FakeKeitaroStore


async def test_create_campaign_with_two_streams_defaults(
    auth_client: httpx.AsyncClient,
    fake_store: FakeKeitaroStore,
    db_session: AsyncSession,
) -> None:
    resp = await auth_client.post(
        "/api/campaigns",
        json={
            "name": "test_lukashov_campaign1",
            "country": "de",
            "offer_id": 101,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    cid = data["keitaro_id"]

    assert data["name"] == "test_lukashov_campaign1"
    assert data["domain_id"] == 10
    assert data["group_id"] == 20
    assert data["traffic_source_id"] == 30
    assert len(data["streams"]) == 2

    s1, s2 = data["streams"]
    assert s1["position"] == 1
    assert s1["has_offers"] is False
    assert s2["position"] == 2
    assert s2["has_offers"] is True
    assert len(s2["offers"]) == 1
    assert s2["offers"][0]["offer_keitaro_id"] == 101
    assert s2["offers"][0]["draft_share"] == 100

    kt_streams = [s for s in fake_store.streams.values() if s["campaign_id"] == cid]
    assert len(kt_streams) == 2
    kt_s1 = next(s for s in kt_streams if s["position"] == 1)
    assert kt_s1["schema"] == "redirect"
    assert kt_s1["action_payload"] == "https://www.google.com"
    assert kt_s1["filters"] == [{"name": "country", "mode": "accept", "payload": ["DE"]}]

    kt_s2 = next(s for s in kt_streams if s["position"] == 2)
    assert kt_s2["action_type"] == "http"
    assert kt_s2["filters"] == []
    assert kt_s2["offers"] == [{"offer_id": 101, "share": 100, "state": "active"}]

    db_campaign = (
        await db_session.execute(select(Campaign).where(Campaign.keitaro_id == cid))
    ).scalar_one()
    assert db_campaign.created_via_wrapper is True


async def test_create_campaign_explicit_refs_and_missing_offer(
    auth_client: httpx.AsyncClient,
) -> None:
    bad_resp = await auth_client.post(
        "/api/campaigns",
        json={
            "name": "test_lukashov_bad",
            "country": "US",
            "offer_id": 9999,
        },
    )
    assert bad_resp.status_code == 422

    ok_resp = await auth_client.post(
        "/api/campaigns",
        json={
            "name": "test_lukashov_explicit",
            "country": "US",
            "offer_id": 102,
            "domain_id": 11,
            "group_id": 21,
            "traffic_source_id": 31,
        },
    )
    assert ok_resp.status_code == 201
    data = ok_resp.json()
    assert data["domain_id"] == 11
    assert data["group_id"] == 21
    assert data["traffic_source_id"] == 31


async def test_create_campaign_partial_stream_failure(
    auth_client: httpx.AsyncClient,
    fake_store: FakeKeitaroStore,
    db_session: AsyncSession,
) -> None:
    fake_store.fail_on_stream_number = 2
    resp = await auth_client.post(
        "/api/campaigns",
        json={
            "name": "test_lukashov_partial",
            "country": "RU",
            "offer_id": 101,
        },
    )
    assert resp.status_code == 502
    assert "Кампания #" in resp.json()["detail"]

    campaigns = (await db_session.execute(select(Campaign))).scalars().all()
    streams = (await db_session.execute(select(Stream))).scalars().all()
    assert len(campaigns) == 1
    assert len(streams) == 1


async def test_create_campaign_multiple_geos(
    auth_client: httpx.AsyncClient,
    fake_store: FakeKeitaroStore,
) -> None:
    resp = await auth_client.post(
        "/api/campaigns",
        json={
            "name": "test_lukashov_multigeo",
            "country": "us, de, ru, de",
            "offer_id": 101,
        },
    )
    assert resp.status_code == 201
    cid = resp.json()["keitaro_id"]
    kt_s1 = next(
        s for s in fake_store.streams.values() if s["campaign_id"] == cid and s["position"] == 1
    )
    assert kt_s1["name"] == "Geo US, DE, RU -> Google"
    assert kt_s1["filters"] == [
        {"name": "country", "mode": "accept", "payload": ["US", "DE", "RU"]}
    ]

    for bad_country in ("US, 123", ", ,"):
        bad = await auth_client.post(
            "/api/campaigns",
            json={
                "name": "test_lukashov_bad_geo",
                "country": bad_country,
                "offer_id": 101,
            },
        )
        assert bad.status_code == 422
