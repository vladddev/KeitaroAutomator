import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import AuthSession
from app.services.keitaro_client import KeitaroClient


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= utcnow()


def _mask_key(api_key: str) -> str:
    if len(api_key) >= 4:
        return f"...{api_key[-4:]}"
    return "****"


async def login(
    db: AsyncSession,
    settings: Settings,
    api_key: str | None,
    client_factory: Callable[[str, str], KeitaroClient],
) -> AuthSession:
    cleaned = (api_key or "").strip()
    if not cleaned:
        default_key = settings.keitaro_default_api_key.strip()
        if not default_key:
            raise HTTPException(
                status_code=503,
                detail="Тестовый API ключ Keitaro не настроен на сервере. Введите свой ключ.",
            )
        mode = "default"
        actual_key = default_key
        custom_api_key = None
        key_hint = f"Тестовый ({_mask_key(default_key)})"
    else:
        mode = "custom"
        actual_key = cleaned
        custom_api_key = cleaned
        key_hint = f"Личный ({_mask_key(cleaned)})"

    async with client_factory(settings.keitaro_api_url, actual_key) as client:
        await client.validate_api_key()

    now = utcnow()
    session = AuthSession(
        id=secrets.token_urlsafe(32),
        mode=mode,
        custom_api_key=custom_api_key,
        key_hint=key_hint,
        created_at=now,
        expires_at=now + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_active_session(db: AsyncSession, session_id: str | None) -> AuthSession | None:
    if not session_id:
        return None
    session = await db.get(AuthSession, session_id)
    if session is None:
        return None
    if is_expired(session.expires_at):
        await db.delete(session)
        await db.commit()
        return None
    return session


def resolve_session_api_key(session: AuthSession, settings: Settings) -> str | None:
    if session.mode == "custom":
        return session.custom_api_key
    key = settings.keitaro_default_api_key.strip()
    return key or None


async def logout(db: AsyncSession, session_id: str | None) -> None:
    if not session_id:
        return
    session = await db.get(AuthSession, session_id)
    if session is not None:
        await db.delete(session)
        await db.commit()
