import re
import secrets
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Campaign, Stream, StreamOffer
from app.schemas import CampaignCreateIn, CampaignCreateOut
from app.services.auth_service import utcnow
from app.services.editor_service import serialize_stream
from app.services.keitaro_client import KeitaroClient


def _build_alias(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
    base = slug or "campaign"
    return f"{base}-{secrets.token_hex(3)}"


async def _resolve_ref_id(
    explicit_id: int | None,
    default_id: int | None,
    fetcher: Any,
) -> int | None:
    if explicit_id is not None:
        return explicit_id
    if default_id is not None:
        return default_id
    items = await fetcher()
    if items:
        return int(items[0]["id"])
    return None


def _stream_from_keitaro(
    raw: dict[str, Any],
    campaign_keitaro_id: int,
    fallback_name: str,
    fallback_position: int,
    fallback_schema: str,
    has_offers: bool,
) -> Stream:
    return Stream(
        keitaro_id=int(raw["id"]),
        campaign_keitaro_id=campaign_keitaro_id,
        name=str(raw.get("name") or fallback_name),
        position=int(raw.get("position") or fallback_position),
        stream_type=str(raw.get("type") or "regular"),
        schema=str(raw.get("schema") or fallback_schema),
        has_offers=has_offers,
        raw_payload=raw,
        synced_at=utcnow(),
    )


async def create_campaign_with_streams(
    db: AsyncSession,
    keitaro: KeitaroClient,
    settings: Settings,
    data: CampaignCreateIn,
) -> CampaignCreateOut:
    offers = await keitaro.get_offers()
    offer_match = next((o for o in offers if int(o["id"]) == data.offer_id), None)
    if offer_match is None:
        raise HTTPException(
            status_code=422,
            detail=f"Оффер с ID {data.offer_id} не найден в Keitaro",
        )
    offer_name = str(offer_match.get("name") or f"Offer #{data.offer_id}")

    domain_id = await _resolve_ref_id(
        data.domain_id, settings.default_domain_id, keitaro.get_domains
    )
    group_id = await _resolve_ref_id(
        data.group_id, settings.default_group_id, keitaro.get_campaign_groups
    )
    traffic_source_id = await _resolve_ref_id(
        data.traffic_source_id, settings.default_traffic_source_id, keitaro.get_traffic_sources
    )

    alias = _build_alias(data.name)
    campaign_payload: dict[str, Any] = {
        "name": data.name,
        "alias": alias,
        "type": "position",
        "state": "active",
    }
    if domain_id is not None:
        campaign_payload["domain_id"] = domain_id
    if group_id is not None:
        campaign_payload["group_id"] = group_id
    if traffic_source_id is not None:
        campaign_payload["traffic_source_id"] = traffic_source_id

    raw_campaign = await keitaro.create_campaign(campaign_payload)
    keitaro_campaign_id = int(raw_campaign["id"])

    existing_campaign = (
        await db.execute(select(Campaign).where(Campaign.keitaro_id == keitaro_campaign_id))
    ).scalar_one_or_none()
    if existing_campaign is None:
        campaign = Campaign(
            keitaro_id=keitaro_campaign_id,
            name=str(raw_campaign.get("name") or data.name),
            alias=raw_campaign.get("alias") or alias,
            domain_id=raw_campaign.get("domain_id") or domain_id,
            group_id=raw_campaign.get("group_id") or group_id,
            traffic_source_id=raw_campaign.get("traffic_source_id") or traffic_source_id,
            created_via_wrapper=True,
        )
        db.add(campaign)
    else:
        campaign = existing_campaign
        campaign.name = str(raw_campaign.get("name") or data.name)
        campaign.alias = raw_campaign.get("alias") or alias
        campaign.domain_id = raw_campaign.get("domain_id") or domain_id
        campaign.group_id = raw_campaign.get("group_id") or group_id
        campaign.traffic_source_id = raw_campaign.get("traffic_source_id") or traffic_source_id
        campaign.created_via_wrapper = True

    created_streams: list[Stream] = []

    geo_label = (
        ", ".join(data.countries)
        if len(data.countries) <= 5
        else f"{', '.join(data.countries[:5])} (+{len(data.countries) - 5})"
    )

    stream1_payload = {
        "campaign_id": keitaro_campaign_id,
        "type": "regular",
        "name": f"Geo {geo_label} -> Google",
        "state": "active",
        "position": 1,
        "schema": "redirect",
        "action_type": "http",
        "action_payload": "https://www.google.com",
        "collect_clicks": True,
        "filter_or": False,
        "filters": [
            {
                "name": "country",
                "mode": "accept",
                "payload": data.countries,
            }
        ],
    }

    try:
        raw_stream1 = await keitaro.create_stream(stream1_payload)
        stream1 = _stream_from_keitaro(
            raw_stream1,
            keitaro_campaign_id,
            stream1_payload["name"],
            1,
            "redirect",
            has_offers=False,
        )
        db.add(stream1)
        created_streams.append(stream1)
    except Exception as exc:
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail=(
                f"Кампания #{keitaro_campaign_id} создана в Keitaro, "
                f"но не удалось создать Поток 1 (редирект на Google): {exc}"
            ),
        ) from exc

    stream2_payload = {
        "campaign_id": keitaro_campaign_id,
        "type": "regular",
        "name": f"Fallback -> {offer_name}",
        "state": "active",
        "position": 2,
        "schema": "landings",
        "action_type": "http",
        "collect_clicks": True,
        "filter_or": False,
        "filters": [],
        "landings": [],
        "offers": [
            {
                "offer_id": data.offer_id,
                "share": 100,
                "state": "active",
            }
        ],
    }

    try:
        raw_stream2 = await keitaro.create_stream(stream2_payload)
        stream2 = _stream_from_keitaro(
            raw_stream2,
            keitaro_campaign_id,
            stream2_payload["name"],
            2,
            "landings",
            has_offers=True,
        )
        stream2.offers.append(
            StreamOffer(
                offer_keitaro_id=data.offer_id,
                offer_name=offer_name,
                sort_order=0,
                published_status="active",
                published_share=100,
                published_is_pinned=False,
                draft_status="active",
                draft_share=100,
                draft_is_pinned=False,
            )
        )
        db.add(stream2)
        created_streams.append(stream2)
    except Exception as exc:
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail=(
                f"Кампания #{keitaro_campaign_id} и Поток 1 созданы в Keitaro, "
                f"но не удалось создать Поток 2 (оффер #{data.offer_id}): {exc}"
            ),
        ) from exc

    await db.commit()
    await db.refresh(campaign)
    for st in created_streams:
        await db.refresh(st, attribute_names=["offers"])

    return CampaignCreateOut(
        id=campaign.id,
        keitaro_id=campaign.keitaro_id,
        name=campaign.name,
        alias=campaign.alias,
        domain_id=campaign.domain_id,
        group_id=campaign.group_id,
        traffic_source_id=campaign.traffic_source_id,
        streams=[serialize_stream(st) for st in created_streams],
    )
