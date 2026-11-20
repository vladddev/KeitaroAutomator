import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StreamOffer
from tests.conftest import FakeKeitaroStore


async def test_fetch_add_cancel_lifecycle(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    fetch_resp = await auth_client.post("/api/campaigns/500/fetch-streams")
    assert fetch_resp.status_code == 200
    streams = fetch_resp.json()
    assert len(streams) == 2

    stub, main_stream = streams
    assert stub["has_offers"] is False
    assert stub["offers"] == []
    assert main_stream["has_offers"] is True
    assert main_stream["is_dirty"] is False
    assert [o["draft_share"] for o in main_stream["offers"]] == [50, 50]

    add_resp = await auth_client.post(
        f"/api/streams/{main_stream['id']}/offers",
        json={"offer_id": 103},
    )
    assert add_resp.status_code == 200
    updated = add_resp.json()
    assert updated["is_dirty"] is True
    assert [o["draft_share"] for o in updated["offers"]] == [34, 33, 33]

    cancel_resp = await auth_client.post(f"/api/streams/{main_stream['id']}/cancel")
    assert cancel_resp.status_code == 200
    reverted = cancel_resp.json()
    assert reverted["is_dirty"] is False
    assert [o["offer_keitaro_id"] for o in reverted["offers"]] == [101, 102]
    assert [o["draft_share"] for o in reverted["offers"]] == [50, 50]

    db_offers = (await db_session.execute(select(StreamOffer))).scalars().all()
    assert len(db_offers) == 2


async def test_pin_remove_push_bring_back_and_external_delete(
    auth_client: httpx.AsyncClient,
    fake_store: FakeKeitaroStore,
) -> None:
    streams = (await auth_client.post("/api/campaigns/500/fetch-streams")).json()
    stream_id = streams[1]["id"]

    # Add 103 and 104 -> 4 offers (25 each), then push them so all 4 exist in Keitaro
    await auth_client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 103})
    s = (await auth_client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 104})).json()
    assert [o["draft_share"] for o in s["offers"]] == [25, 25, 25, 25]
    pushed_init = (await auth_client.post(f"/api/streams/{stream_id}/push")).json()
    assert pushed_init["is_dirty"] is False

    # Pin 101 to 40% -> remaining 60% split across 102, 103, 104 (20 each)
    s = (
        await auth_client.patch(
            f"/api/streams/{stream_id}/offers/101/pin",
            json={"is_pinned": True, "share": 40},
        )
    ).json()
    assert [o["draft_share"] for o in s["offers"]] == [40, 20, 20, 20]

    # Remove 104 -> soft deleted (0%), remaining 60% split across 102, 103 (30 each), 101 stays 40%
    s = (await auth_client.post(f"/api/streams/{stream_id}/offers/104/remove")).json()
    by_id = {o["offer_keitaro_id"]: o for o in s["offers"]}
    assert by_id[104]["draft_status"] == "removed"
    assert by_id[104]["draft_share"] == 0
    assert by_id[101]["draft_share"] == 40
    assert by_id[102]["draft_share"] == 30
    assert by_id[103]["draft_share"] == 30
    assert s["is_dirty"] is True
    assert s["can_push"] is True

    # Push to Keitaro -> Keitaro gets only active offers, 104 remains archived in wrapper
    pushed = (await auth_client.post(f"/api/streams/{stream_id}/push")).json()
    assert pushed["is_dirty"] is False
    kt_offers = fake_store.streams[5002]["offers"]
    assert [o["offer_id"] for o in kt_offers] == [101, 102, 103]
    assert sum(o["share"] for o in kt_offers) == 100

    pushed_by_id = {o["offer_keitaro_id"]: o for o in pushed["offers"]}
    assert pushed_by_id[104]["published_status"] == "removed"
    assert pushed_by_id[104]["draft_status"] == "removed"

    # Bring Back 104 -> active again, 101 stays pinned 40%, 102/103/104 get 20 each
    brought_back = (
        await auth_client.post(f"/api/streams/{stream_id}/offers/104/bring-back")
    ).json()
    assert brought_back["is_dirty"] is True
    bb_by_id = {o["offer_keitaro_id"]: o for o in brought_back["offers"]}
    assert bb_by_id[104]["draft_status"] == "active"
    assert bb_by_id[101]["draft_share"] == 40
    assert [bb_by_id[i]["draft_share"] for i in (102, 103, 104)] == [20, 20, 20]

    # Push Bring Back
    await auth_client.post(f"/api/streams/{stream_id}/push")

    # Simulate external removal of offer 103 directly inside Keitaro
    fake_store.streams[5002]["offers"] = [
        {"offer_id": 101, "share": 50, "state": "active"},
        {"offer_id": 102, "share": 50, "state": "active"},
    ]
    resynced = (await auth_client.post("/api/campaigns/500/fetch-streams")).json()
    resynced_by_id = {o["offer_keitaro_id"]: o for o in resynced[1]["offers"]}
    assert resynced[1]["is_dirty"] is False
    assert resynced_by_id[103]["published_status"] == "removed"
    assert resynced_by_id[103]["draft_status"] == "removed"
    assert resynced_by_id[103]["draft_share"] == 0
    assert resynced_by_id[104]["draft_status"] == "removed"
