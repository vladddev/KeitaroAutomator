from collections.abc import Callable

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.deps import SESSION_COOKIE_NAME, get_keitaro_client_factory
from app.schemas import AuthMeOut, LoginIn
from app.services import auth_service
from app.services.keitaro_client import KeitaroClient

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=AuthMeOut)
async def login(
    payload: LoginIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client_factory: Callable[[str, str], KeitaroClient] = Depends(get_keitaro_client_factory),
) -> AuthMeOut:
    session = await auth_service.login(db, settings, payload.api_key, client_factory)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.id,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_hours * 3600,
    )
    return AuthMeOut(
        authenticated=True,
        mode=session.mode,  # type: ignore[arg-type]
        key_hint=session.key_hint,
        default_key_configured=bool(settings.keitaro_default_api_key.strip()),
        default_campaign_prefix=settings.default_campaign_prefix,
    )


@router.get("/me", response_model=AuthMeOut)
async def me(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthMeOut:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    session = await auth_service.get_active_session(db, session_id)
    default_configured = bool(settings.keitaro_default_api_key.strip())
    if session is None:
        return AuthMeOut(
            authenticated=False,
            mode=None,
            key_hint=None,
            default_key_configured=default_configured,
            default_campaign_prefix=settings.default_campaign_prefix,
        )

    return AuthMeOut(
        authenticated=True,
        mode=session.mode,  # type: ignore[arg-type]
        key_hint=session.key_hint,
        default_key_configured=default_configured,
        default_campaign_prefix=settings.default_campaign_prefix,
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    await auth_service.logout(db, session_id)
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return {"ok": True}
