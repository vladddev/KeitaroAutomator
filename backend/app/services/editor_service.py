from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Campaign, Stream, StreamOffer
from app.schemas import StreamOfferOut, StreamOut
from app.services.auth_service import utcnow
from app.services.keitaro_client import KeitaroClient
from app.services.weights import is_stream_dirty, recalculate_weights, validate_stream_for_push

_READONLY_STREAM_KEYS = {"id", "created_at", "updated_at", "state_changed_at"}


def serialize_stream(stream: Stream) -> StreamOut:
    sorted_offers = sorted(stream.offers, key=lambda o: (o.sort_order, o.id or 0))
    dirty = is_stream_dirty(sorted_offers) if stream.has_offers else False
    can_push, total_active_share, errors = (
        validate_stream_for_push(sorted_offers) if stream.has_offers else (False, 0, [])
    )

    return StreamOut(
        id=stream.id,
        keitaro_id=stream.keitaro_id,
        campaign_keitaro_id=stream.campaign_keitaro_id,
        name=stream.name,
        position=stream.position,
        stream_type=stream.stream_type,
        schema_name=stream.schema,
        has_offers=stream.has_offers,
        is_dirty=dirty,
        can_push=can_push,
        total_active_share=total_active_share,
        validation_errors=errors,
        synced_at=stream.synced_at,
        offers=[
            StreamOfferOut(
                id=o.id,
                offer_keitaro_id=o.offer_keitaro_id,
                offer_name=o.offer_name,
                sort_order=o.sort_order,
                published_status=o.published_status,
                published_share=o.published_share,
                published_is_pinned=o.published_is_pinned,
                draft_status=o.draft_status,
                draft_share=o.draft_share,
                draft_is_pinned=o.draft_is_pinned,
            )
            for o in sorted_offers
        ],
    )


async def _load_stream(db: AsyncSession, stream_id: int) -> Stream:
    stmt = (
        select(Stream)
        .where(Stream.id == stream_id)
        .options(selectinload(Stream.offers))
        .execution_options(populate_existing=True)
    )
    stream = (await db.execute(stmt)).scalar_one_or_none()
    if stream is None:
        raise HTTPException(status_code=404, detail=f"Поток #{stream_id} не найден")
    return stream


def _find_offer(stream: Stream, offer_keitaro_id: int) -> StreamOffer:
    for offer in stream.offers:
        if offer.offer_keitaro_id == offer_keitaro_id:
            return offer
    raise HTTPException(
        status_code=404,
        detail=f"Оффер #{offer_keitaro_id} не найден в потоке #{stream.id}",
    )


def _require_offers_stream(stream: Stream) -> None:
    if not stream.has_offers:
        raise HTTPException(
            status_code=422,
            detail="Этот поток работает без офферов (заглушка фильтра/редиректа) и не редактируется",
        )


async def get_campaign_streams(db: AsyncSession, campaign_keitaro_id: int) -> list[StreamOut]:
    stmt = (
        select(Stream)
        .where(Stream.campaign_keitaro_id == campaign_keitaro_id)
        .options(selectinload(Stream.offers))
        .order_by(Stream.position, Stream.id)
    )
    streams = (await db.execute(stmt)).scalars().all()
    return [serialize_stream(st) for st in streams]


async def fetch_streams(
    db: AsyncSession, keitaro: KeitaroClient, campaign_keitaro_id: int
) -> list[StreamOut]:
    raw_campaign = await keitaro.get_campaign(campaign_keitaro_id)
    raw_streams = await keitaro.get_campaign_streams(campaign_keitaro_id)
    offers_list = await keitaro.get_offers(refresh=True)
    offer_names = {int(o["id"]): str(o.get("name") or f"Offer #{o['id']}") for o in offers_list}

    campaign = (
        await db.execute(select(Campaign).where(Campaign.keitaro_id == campaign_keitaro_id))
    ).scalar_one_or_none()
    if campaign is None:
        campaign = Campaign(
            keitaro_id=campaign_keitaro_id,
            name=str(raw_campaign.get("name") or f"Campaign #{campaign_keitaro_id}"),
            alias=raw_campaign.get("alias"),
            domain_id=raw_campaign.get("domain_id"),
            group_id=raw_campaign.get("group_id"),
            traffic_source_id=raw_campaign.get("traffic_source_id"),
            created_via_wrapper=False,
        )
        db.add(campaign)
    else:
        campaign.name = str(raw_campaign.get("name") or campaign.name)
        campaign.alias = raw_campaign.get("alias")
        campaign.domain_id = raw_campaign.get("domain_id")
        campaign.group_id = raw_campaign.get("group_id")
        campaign.traffic_source_id = raw_campaign.get("traffic_source_id")

    local_streams = (
        await db.execute(
            select(Stream)
            .where(Stream.campaign_keitaro_id == campaign_keitaro_id)
            .options(selectinload(Stream.offers))
        )
    ).scalars().all()
    local_by_kt_id = {st.keitaro_id: st for st in local_streams}
    remote_kt_ids = {int(rs["id"]) for rs in raw_streams}

    for kt_id, local_st in local_by_kt_id.items():
        if kt_id not in remote_kt_ids:
            await db.delete(local_st)

    now = utcnow()
    sorted_raw_streams = sorted(
        raw_streams, key=lambda s: (int(s.get("position") or 0), int(s["id"]))
    )

    for raw_st in sorted_raw_streams:
        st_kt_id = int(raw_st["id"])
        raw_offers = raw_st.get("offers") or []
        schema_name = str(raw_st.get("schema") or "")
        has_offers = schema_name in ("landings", "offers", "landings_and_offers") or bool(raw_offers)

        stream = local_by_kt_id.get(st_kt_id)
        if stream is None:
            stream = Stream(
                keitaro_id=st_kt_id,
                campaign_keitaro_id=campaign_keitaro_id,
                name=str(raw_st.get("name") or f"Stream #{st_kt_id}"),
                position=int(raw_st.get("position") or 0),
                stream_type=str(raw_st.get("type") or "regular"),
                schema=schema_name,
                has_offers=has_offers,
                raw_payload=raw_st,
                synced_at=now,
            )
            db.add(stream)
        else:
            stream.name = str(raw_st.get("name") or stream.name)
            stream.position = int(raw_st.get("position") or 0)
            stream.stream_type = str(raw_st.get("type") or "regular")
            stream.schema = schema_name
            stream.has_offers = has_offers
            stream.raw_payload = raw_st
            stream.synced_at = now

        if not has_offers:
            stream.offers.clear()
            continue

        for unpublished in [o for o in stream.offers if o.published_status is None]:
            stream.offers.remove(unpublished)

        existing_by_offer_id = {o.offer_keitaro_id: o for o in stream.offers}
        next_sort_order = max((o.sort_order for o in stream.offers), default=-1) + 1
        seen_remote_offer_ids: set[int] = set()

        for raw_offer in raw_offers:
            oid = int(raw_offer["offer_id"])
            seen_remote_offer_ids.add(oid)
            share = int(raw_offer.get("share") or 0)
            oname = offer_names.get(oid) or str(raw_offer.get("offer_name") or f"Offer #{oid}")

            existing = existing_by_offer_id.get(oid)
            if existing is not None:
                existing.offer_name = oname
                existing.published_status = "active"
                existing.published_share = share
                existing.draft_status = "active"
                existing.draft_share = share
                existing.published_is_pinned = existing.draft_is_pinned
            else:
                stream.offers.append(
                    StreamOffer(
                        offer_keitaro_id=oid,
                        offer_name=oname,
                        sort_order=next_sort_order,
                        published_status="active",
                        published_share=share,
                        published_is_pinned=False,
                        draft_status="active",
                        draft_share=share,
                        draft_is_pinned=False,
                    )
                )
                next_sort_order += 1

        for oid, existing in existing_by_offer_id.items():
            if oid not in seen_remote_offer_ids:
                existing.published_status = "removed"
                existing.published_share = 0
                existing.published_is_pinned = False
                existing.draft_status = "removed"
                existing.draft_share = 0
                existing.draft_is_pinned = False

        pinned_sum = sum(
            o.draft_share for o in stream.offers if o.draft_status == "active" and o.draft_is_pinned
        )
        if pinned_sum > 100:
            for o in stream.offers:
                o.draft_is_pinned = False
                o.published_is_pinned = False

    await db.commit()
    return await get_campaign_streams(db, campaign_keitaro_id)


async def add_offer(
    db: AsyncSession, keitaro: KeitaroClient, stream_id: int, offer_id: int
) -> StreamOut:
    stream = await _load_stream(db, stream_id)
    _require_offers_stream(stream)

    existing = next((o for o in stream.offers if o.offer_keitaro_id == offer_id), None)
    if existing is not None:
        if existing.draft_status == "active":
            raise HTTPException(
                status_code=422, detail=f"Оффер #{offer_id} уже активен в этом потоке"
            )
        existing.draft_status = "active"
        existing.draft_is_pinned = False
    else:
        offers_list = await keitaro.get_offers()
        offer_match = next((o for o in offers_list if int(o["id"]) == offer_id), None)
        if offer_match is None:
            offers_list = await keitaro.get_offers(refresh=True)
            offer_match = next((o for o in offers_list if int(o["id"]) == offer_id), None)
        if offer_match is None:
            raise HTTPException(status_code=422, detail=f"Оффер #{offer_id} не найден в Keitaro")

        next_order = max((o.sort_order for o in stream.offers), default=-1) + 1
        stream.offers.append(
            StreamOffer(
                offer_keitaro_id=offer_id,
                offer_name=str(offer_match.get("name") or f"Offer #{offer_id}"),
                sort_order=next_order,
                published_status=None,
                published_share=None,
                published_is_pinned=False,
                draft_status="active",
                draft_share=0,
                draft_is_pinned=False,
            )
        )

    recalculate_weights(stream.offers)
    await db.commit()
    stream = await _load_stream(db, stream_id)
    return serialize_stream(stream)


async def remove_offer(db: AsyncSession, stream_id: int, offer_keitaro_id: int) -> StreamOut:
    stream = await _load_stream(db, stream_id)
    _require_offers_stream(stream)
    offer = _find_offer(stream, offer_keitaro_id)

    offer.draft_status = "removed"
    offer.draft_share = 0
    offer.draft_is_pinned = False

    recalculate_weights(stream.offers)
    await db.commit()
    stream = await _load_stream(db, stream_id)
    return serialize_stream(stream)


async def bring_back_offer(db: AsyncSession, stream_id: int, offer_keitaro_id: int) -> StreamOut:
    stream = await _load_stream(db, stream_id)
    _require_offers_stream(stream)
    offer = _find_offer(stream, offer_keitaro_id)

    if offer.draft_status == "active":
        raise HTTPException(
            status_code=422, detail=f"Оффер #{offer_keitaro_id} уже находится в активном списке"
        )

    offer.draft_status = "active"
    offer.draft_is_pinned = False

    recalculate_weights(stream.offers)
    await db.commit()
    stream = await _load_stream(db, stream_id)
    return serialize_stream(stream)


async def pin_offer(
    db: AsyncSession,
    stream_id: int,
    offer_keitaro_id: int,
    is_pinned: bool,
    share: int | None,
) -> StreamOut:
    stream = await _load_stream(db, stream_id)
    _require_offers_stream(stream)
    offer = _find_offer(stream, offer_keitaro_id)

    if offer.draft_status != "active":
        raise HTTPException(
            status_code=422, detail="Нельзя закрепить вес у удаленного (архивного) оффера"
        )

    if is_pinned:
        target_share = offer.draft_share if share is None else share
        if target_share < 0 or target_share > 100:
            raise HTTPException(status_code=422, detail="Вес должен быть в диапазоне от 0 до 100%")
        other_pinned_sum = sum(
            o.draft_share
            for o in stream.offers
            if o.draft_status == "active"
            and o.draft_is_pinned
            and o.offer_keitaro_id != offer_keitaro_id
        )
        if other_pinned_sum + target_share > 100:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Сумма закрепленных весов ({other_pinned_sum + target_share}%) превышает 100%"
                ),
            )
        offer.draft_is_pinned = True
        offer.draft_share = target_share
    else:
        offer.draft_is_pinned = False

    recalculate_weights(stream.offers)

    if not is_stream_dirty(stream.offers):
        for item in stream.offers:
            item.published_is_pinned = item.draft_is_pinned

    await db.commit()
    stream = await _load_stream(db, stream_id)
    return serialize_stream(stream)


async def push_stream(db: AsyncSession, keitaro: KeitaroClient, stream_id: int) -> StreamOut:
    stream = await _load_stream(db, stream_id)
    _require_offers_stream(stream)

    can_push, _, errors = validate_stream_for_push(stream.offers)
    if not can_push:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    sorted_active = sorted(
        (o for o in stream.offers if o.draft_status == "active"),
        key=lambda o: (o.sort_order, o.id or 0),
    )

    payload: dict[str, Any] = {
        k: v for k, v in (stream.raw_payload or {}).items() if k not in _READONLY_STREAM_KEYS
    }
    payload.setdefault("campaign_id", stream.campaign_keitaro_id)
    payload.setdefault("name", stream.name)
    payload.setdefault("type", stream.stream_type or "regular")
    payload.setdefault("position", stream.position)
    payload.setdefault("schema", stream.schema or "landings")
    payload.setdefault("action_type", "http")
    payload.setdefault("state", "active")
    payload["offers"] = [
        {
            "offer_id": o.offer_keitaro_id,
            "share": o.draft_share,
            "state": "active",
        }
        for o in sorted_active
    ]

    updated_raw = await keitaro.update_stream(stream.keitaro_id, payload)
    stream.raw_payload = updated_raw or payload
    stream.synced_at = utcnow()

    for obsolete in [
        o for o in stream.offers if o.published_status is None and o.draft_status == "removed"
    ]:
        stream.offers.remove(obsolete)

    for offer in stream.offers:
        offer.published_status = offer.draft_status
        offer.published_share = offer.draft_share
        offer.published_is_pinned = offer.draft_is_pinned

    await db.commit()
    stream = await _load_stream(db, stream_id)
    return serialize_stream(stream)


async def cancel_stream(db: AsyncSession, stream_id: int) -> StreamOut:
    stream = await _load_stream(db, stream_id)
    _require_offers_stream(stream)

    for unpublished in [o for o in stream.offers if o.published_status is None]:
        stream.offers.remove(unpublished)

    for offer in stream.offers:
        offer.draft_status = offer.published_status or "active"
        offer.draft_share = offer.published_share if offer.published_share is not None else 0
        offer.draft_is_pinned = offer.published_is_pinned

    await db.commit()
    stream = await _load_stream(db, stream_id)
    return serialize_stream(stream)
