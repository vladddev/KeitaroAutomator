from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.deps import get_keitaro_client
from app.schemas import CampaignCreateIn, CampaignCreateOut
from app.services import campaign_service
from app.services.keitaro_client import KeitaroClient

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignCreateOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreateIn,
    db: AsyncSession = Depends(get_db),
    keitaro: KeitaroClient = Depends(get_keitaro_client),
    settings: Settings = Depends(get_settings),
) -> CampaignCreateOut:
    return await campaign_service.create_campaign_with_streams(db, keitaro, settings, payload)
