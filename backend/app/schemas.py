from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LoginIn(BaseModel):
    api_key: str | None = Field(default=None, description="Optional Keitaro Admin API key")


class AuthMeOut(BaseModel):
    authenticated: bool
    mode: Literal["default", "custom"] | None = None
    key_hint: str | None = None
    default_key_configured: bool = False
    default_campaign_prefix: str = "test_lukashov_"


class ReferenceItem(BaseModel):
    id: int
    name: str


class ReferencesOut(BaseModel):
    domains: list[ReferenceItem]
    groups: list[ReferenceItem]
    traffic_sources: list[ReferenceItem]
    defaults: dict[str, int | None]


class OfferItem(BaseModel):
    id: int
    name: str
    state: str | None = None


class CampaignSummary(BaseModel):
    id: int
    name: str
    alias: str | None = None
    state: str | None = None
    domain_id: int | None = None
    group_id: int | None = None
    traffic_source_id: int | None = None


class CampaignCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    country: str = Field(..., min_length=2, max_length=255)
    offer_id: int = Field(..., gt=0)
    domain_id: int | None = Field(default=None, gt=0)
    group_id: int | None = Field(default=None, gt=0)
    traffic_source_id: int | None = Field(default=None, gt=0)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Название кампании не может быть пустым")
        return cleaned

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str) -> str:
        raw_codes = [part.strip().upper() for part in value.split(",") if part.strip()]
        if not raw_codes:
            raise ValueError("Укажите хотя бы один код страны (например, US, RU, DE)")
        for code in raw_codes:
            if len(code) != 2 or not code.isascii() or not code.isalpha():
                raise ValueError(
                    f"Некорректный код страны '{code}'. Каждый код должен состоять из 2 латинских букв (например, US, DE, RU)"
                )
        unique_codes = list(dict.fromkeys(raw_codes))
        return ", ".join(unique_codes)

    @property
    def countries(self) -> list[str]:
        return [c.strip() for c in self.country.split(",") if c.strip()]


class StreamOfferOut(BaseModel):
    id: int
    offer_keitaro_id: int
    offer_name: str
    sort_order: int
    published_status: Literal["active", "removed"] | None
    published_share: int | None
    published_is_pinned: bool
    draft_status: Literal["active", "removed"]
    draft_share: int
    draft_is_pinned: bool


class StreamOut(BaseModel):
    id: int
    keitaro_id: int
    campaign_keitaro_id: int
    name: str
    position: int
    stream_type: str
    schema_name: str
    has_offers: bool
    is_dirty: bool
    can_push: bool
    total_active_share: int
    validation_errors: list[str]
    synced_at: datetime
    offers: list[StreamOfferOut]


class CampaignCreateOut(BaseModel):
    id: int
    keitaro_id: int
    name: str
    alias: str | None
    domain_id: int | None
    group_id: int | None
    traffic_source_id: int | None
    streams: list[StreamOut]


class AddOfferIn(BaseModel):
    offer_id: int = Field(..., gt=0)


class PinOfferIn(BaseModel):
    is_pinned: bool
    share: int | None = Field(default=None, ge=0, le=100)
