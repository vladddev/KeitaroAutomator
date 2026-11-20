import pytest

from app.models import StreamOffer
from app.services.weights import (
    WeightValidationError,
    is_stream_dirty,
    recalculate_weights,
    validate_stream_for_push,
)


def _offer(
    oid: int,
    *,
    sort_order: int = 0,
    pub_status: str | None = "active",
    pub_share: int | None = 0,
    draft_status: str = "active",
    draft_share: int = 0,
    pinned: bool = False,
) -> StreamOffer:
    return StreamOffer(
        id=oid,
        stream_id=1,
        offer_keitaro_id=100 + oid,
        offer_name=f"Offer {oid}",
        sort_order=sort_order,
        published_status=pub_status,
        published_share=pub_share,
        published_is_pinned=False,
        draft_status=draft_status,
        draft_share=draft_share,
        draft_is_pinned=pinned,
    )


@pytest.mark.parametrize(
    ("count", "expected_shares"),
    [
        (1, [100]),
        (2, [50, 50]),
        (3, [34, 33, 33]),
        (4, [25, 25, 25, 25]),
        (7, [15, 15, 14, 14, 14, 14, 14]),
    ],
)
def test_recalculate_equal_distribution(count: int, expected_shares: list[int]) -> None:
    offers = [_offer(i + 1, sort_order=i) for i in range(count)]
    recalculate_weights(offers)
    assert [o.draft_share for o in offers] == expected_shares
    assert sum(o.draft_share for o in offers) == 100


def test_recalculate_with_single_and_multiple_pins() -> None:
    offers = [
        _offer(1, sort_order=0, draft_share=25, pinned=True),
        _offer(2, sort_order=1),
        _offer(3, sort_order=2),
        _offer(4, sort_order=3),
    ]
    recalculate_weights(offers)
    assert [o.draft_share for o in offers] == [25, 25, 25, 25]

    offers.pop()
    recalculate_weights(offers)
    assert [o.draft_share for o in offers] == [25, 38, 37]

    offers[1].draft_is_pinned = True
    offers[1].draft_share = 35
    recalculate_weights(offers)
    assert [o.draft_share for o in offers] == [25, 35, 40]

    offers[0].draft_is_pinned = False
    recalculate_weights(offers)
    assert [o.draft_share for o in offers] == [33, 35, 32]


def test_pinned_sum_exceeding_100_raises() -> None:
    offers = [
        _offer(1, sort_order=0, draft_share=60, pinned=True),
        _offer(2, sort_order=1, draft_share=50, pinned=True),
    ]
    with pytest.raises(WeightValidationError):
        recalculate_weights(offers)


def test_removed_and_bring_back_resets_share_and_pin() -> None:
    offers = [
        _offer(1, sort_order=0, draft_share=25, pinned=True),
        _offer(2, sort_order=1, draft_share=75),
    ]
    offers[0].draft_status = "removed"
    recalculate_weights(offers)
    assert offers[0].draft_share == 0
    assert offers[0].draft_is_pinned is False
    assert offers[1].draft_share == 100

    offers[0].draft_status = "active"
    recalculate_weights(offers)
    assert [o.draft_share for o in offers] == [50, 50]


def test_validate_stream_all_pinned_not_100_and_zero_active() -> None:
    offers = [
        _offer(1, sort_order=0, draft_share=30, pinned=True),
        _offer(2, sort_order=1, draft_share=40, pinned=True),
    ]
    recalculate_weights(offers)
    can_push, total, errors = validate_stream_for_push(offers)
    assert can_push is False
    assert total == 70
    assert len(errors) == 1

    for o in offers:
        o.draft_status = "removed"
    recalculate_weights(offers)
    can_push, total, errors = validate_stream_for_push(offers)
    assert can_push is False
    assert total == 0
    assert len(errors) == 1


def test_dirty_detection() -> None:
    offers = [_offer(1, pub_status="active", pub_share=100, draft_status="active", draft_share=100)]
    assert is_stream_dirty(offers) is False

    offers[0].draft_share = 50
    assert is_stream_dirty(offers) is True

    offers[0].draft_share = 100
    offers[0].published_status = None
    assert is_stream_dirty(offers) is True
