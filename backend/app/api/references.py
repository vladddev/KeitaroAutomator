import asyncio

from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.deps import get_keitaro_client
from app.schemas import CampaignSummary, OfferItem, ReferenceItem, ReferencesOut
from app.services.keitaro_client import KeitaroClient

router = APIRouter(prefix="/api", tags=["references"])


@router.get("/references", response_model=ReferencesOut)
async def get_references(
    keitaro: KeitaroClient = Depends(get_keitaro_client),
    settings: Settings = Depends(get_settings),
) -> ReferencesOut:
    domains_raw, groups_raw, sources_raw = await asyncio.gather(
        keitaro.get_domains(),
        keitaro.get_campaign_groups(),
        keitaro.get_traffic_sources(),
    )

    domains = [ReferenceItem(id=int(d["id"]), name=str(d.get("name") or d["id"])) for d in domains_raw]
    groups = [ReferenceItem(id=int(g["id"]), name=str(g.get("name") or g["id"])) for g in groups_raw]
    sources = [
        ReferenceItem(id=int(s["id"]), name=str(s.get("name") or s["id"])) for s in sources_raw
    ]

    return ReferencesOut(
        domains=domains,
        groups=groups,
        traffic_sources=sources,
        defaults={
            "domain_id": settings.default_domain_id or (domains[0].id if domains else None),
            "group_id": settings.default_group_id or (groups[0].id if groups else None),
            "traffic_source_id": (
                settings.default_traffic_source_id or (sources[0].id if sources else None)
            ),
        },
    )


@router.get("/offers", response_model=list[OfferItem])
async def search_offers(
    q: str = Query(default=""),
    refresh: bool = Query(default=False),
    keitaro: KeitaroClient = Depends(get_keitaro_client),
) -> list[OfferItem]:
    raw_offers = await keitaro.get_offers(refresh=refresh)
    query = q.strip().lower()

    results: list[OfferItem] = []
    for item in raw_offers:
        oid = int(item["id"])
        name = str(item.get("name") or f"Offer #{oid}")
        if query and query not in str(oid) and query not in name.lower():
            continue
        results.append(OfferItem(id=oid, name=name, state=item.get("state")))

    results.sort(key=lambda o: (0 if query and str(o.id) == query else 1, o.id))
    return results[:50]


@router.get("/campaigns", response_model=list[CampaignSummary])
async def list_campaigns(
    q: str = Query(default=""),
    keitaro: KeitaroClient = Depends(get_keitaro_client),
) -> list[CampaignSummary]:
    raw_campaigns = await keitaro.get_campaigns()
    query = q.strip().lower()

    results: list[CampaignSummary] = []
    for item in raw_campaigns:
        cid = int(item["id"])
        name = str(item.get("name") or f"Campaign #{cid}")
        if query and query not in str(cid) and query not in name.lower():
            continue
        results.append(
            CampaignSummary(
                id=cid,
                name=name,
                alias=item.get("alias"),
                state=item.get("state"),
                domain_id=item.get("domain_id"),
                group_id=item.get("group_id"),
                traffic_source_id=item.get("traffic_source_id"),
            )
        )

    results.sort(key=lambda c: c.id, reverse=True)
    return results
