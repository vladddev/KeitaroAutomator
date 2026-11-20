from collections.abc import AsyncGenerator, Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.services import auth_service
from app.services.keitaro_client import KeitaroClient

SESSION_COOKIE_NAME = "kt_session"


def build_keitaro_client(base_url: str, api_key: str) -> KeitaroClient:
    return KeitaroClient(base_url=base_url, api_key=api_key)


def get_keitaro_client_factory() -> Callable[[str, str], KeitaroClient]:
    return build_keitaro_client


async def require_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> str:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    session = await auth_service.get_active_session(db, session_id)
    api_key = (
        auth_service.resolve_session_api_key(session, settings)
        if session is not None
        else None
    )

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Требуется авторизация по API ключу Keitaro",
        )
    return api_key


async def get_keitaro_client(
    api_key: str = Depends(require_api_key),
    settings: Settings = Depends(get_settings),
    factory: Callable[[str, str], KeitaroClient] = Depends(get_keitaro_client_factory),
) -> AsyncGenerator[KeitaroClient, None]:
    async with factory(settings.keitaro_api_url, api_key) as client:
        yield client
