from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_keitaro_client, require_api_key
from app.schemas import AddOfferIn, PinOfferIn, StreamOut
from app.services import editor_service
from app.services.keitaro_client import KeitaroClient

router = APIRouter(prefix="/api", tags=["editor"])


@router.get("/campaigns/{campaign_keitaro_id}/streams", response_model=list[StreamOut])
async def get_campaign_streams(
    campaign_keitaro_id: int,
    _: str = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[StreamOut]:
    return await editor_service.get_campaign_streams(db, campaign_keitaro_id)


@router.post("/campaigns/{campaign_keitaro_id}/fetch-streams", response_model=list[StreamOut])
async def fetch_campaign_streams(
    campaign_keitaro_id: int,
    db: AsyncSession = Depends(get_db),
    keitaro: KeitaroClient = Depends(get_keitaro_client),
) -> list[StreamOut]:
    return await editor_service.fetch_streams(db, keitaro, campaign_keitaro_id)


@router.post("/streams/{stream_id}/offers", response_model=StreamOut)
async def add_stream_offer(
    stream_id: int,
    payload: AddOfferIn,
    db: AsyncSession = Depends(get_db),
    keitaro: KeitaroClient = Depends(get_keitaro_client),
) -> StreamOut:
    return await editor_service.add_offer(db, keitaro, stream_id, payload.offer_id)


@router.post("/streams/{stream_id}/offers/{offer_keitaro_id}/remove", response_model=StreamOut)
async def remove_stream_offer(
    stream_id: int,
    offer_keitaro_id: int,
    _: str = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> StreamOut:
    return await editor_service.remove_offer(db, stream_id, offer_keitaro_id)


@router.post(
    "/streams/{stream_id}/offers/{offer_keitaro_id}/bring-back", response_model=StreamOut
)
async def bring_back_stream_offer(
    stream_id: int,
    offer_keitaro_id: int,
    _: str = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> StreamOut:
    return await editor_service.bring_back_offer(db, stream_id, offer_keitaro_id)


@router.patch("/streams/{stream_id}/offers/{offer_keitaro_id}/pin", response_model=StreamOut)
async def pin_stream_offer(
    stream_id: int,
    offer_keitaro_id: int,
    payload: PinOfferIn,
    _: str = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> StreamOut:
    return await editor_service.pin_offer(
        db, stream_id, offer_keitaro_id, payload.is_pinned, payload.share
    )


@router.post("/streams/{stream_id}/push", response_model=StreamOut)
async def push_stream(
    stream_id: int,
    db: AsyncSession = Depends(get_db),
    keitaro: KeitaroClient = Depends(get_keitaro_client),
) -> StreamOut:
    return await editor_service.push_stream(db, keitaro, stream_id)


@router.post("/streams/{stream_id}/cancel", response_model=StreamOut)
async def cancel_stream(
    stream_id: int,
    _: str = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> StreamOut:
    return await editor_service.cancel_stream(db, stream_id)
