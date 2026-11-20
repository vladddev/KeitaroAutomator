from collections.abc import Sequence

from app.models import StreamOffer


class WeightValidationError(ValueError):
    """Raised when pinned offer weights violate traffic distribution constraints."""


def is_stream_dirty(offers: Sequence[StreamOffer]) -> bool:
    """Return True when stream draft differs from last synced/pushed Keitaro state."""
    for offer in offers:
        if offer.published_status is None:
            return True
        if offer.draft_status != offer.published_status:
            return True
        if (
            offer.draft_status == "active"
            and offer.published_status == "active"
            and offer.draft_share != offer.published_share
        ):
            return True
    return False


def recalculate_weights(offers: Sequence[StreamOffer]) -> None:
    """Redistribute remaining percentage equally among active unpinned offers."""
    active: list[StreamOffer] = []
    for offer in offers:
        if offer.draft_status == "removed":
            offer.draft_share = 0
            offer.draft_is_pinned = False
        else:
            active.append(offer)

    pinned = [o for o in active if o.draft_is_pinned]
    unpinned = sorted(
        (o for o in active if not o.draft_is_pinned),
        key=lambda o: (o.sort_order, o.id or 0),
    )

    for offer in pinned:
        if offer.draft_share < 0 or offer.draft_share > 100:
            raise WeightValidationError("Закрепленный вес должен быть от 0 до 100%")

    pinned_sum = sum(o.draft_share for o in pinned)
    if pinned_sum > 100:
        raise WeightValidationError(f"Сумма закрепленных весов ({pinned_sum}%) превышает 100%")

    remaining = 100 - pinned_sum
    if not unpinned:
        return

    base, rem = divmod(remaining, len(unpinned))
    for idx, offer in enumerate(unpinned):
        offer.draft_share = base + (1 if idx < rem else 0)


def validate_stream_for_push(offers: Sequence[StreamOffer]) -> tuple[bool, int, list[str]]:
    """Validate whether stream draft can be published to Keitaro."""
    active = [o for o in offers if o.draft_status == "active"]
    total_active_share = sum(o.draft_share for o in active)
    errors: list[str] = []

    if not active:
        errors.append("В потоке должен остаться хотя бы один активный оффер")
        return False, total_active_share, errors

    if any(o.draft_share < 0 or o.draft_share > 100 for o in active):
        errors.append("Вес каждого активного оффера должен быть в диапазоне от 0% до 100%")

    if total_active_share != 100:
        errors.append(
            f"Сумма весов активных офферов: {total_active_share}%, требуется ровно 100%"
        )

    return len(errors) == 0, total_active_share, errors
