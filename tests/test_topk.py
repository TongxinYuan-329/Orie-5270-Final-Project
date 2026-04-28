from __future__ import annotations

import pytest

from stock_stream.topk import TopKExtremeReturns
from stock_stream.types import StreamItem


def make_item(date: str, ticker: str, ret: float | None) -> StreamItem:
    return StreamItem(date=date, ticker=ticker, close=100.0, ret=ret)


def test_returns_fewer_than_k_when_fewer_observations() -> None:
    tracker = TopKExtremeReturns(k=5)
    tracker.update(make_item("2024-01-01", "A", 0.01))
    tracker.update(make_item("2024-01-02", "A", -0.05))
    tracker.update(make_item("2024-01-03", "A", 0.03))

    df = tracker.get_topk()
    assert len(df) == 3


def test_returns_exactly_k_after_enough_observations() -> None:
    tracker = TopKExtremeReturns(k=3)
    for i, r in enumerate([0.01, -0.05, 0.03, -0.10, 0.02], start=1):
        tracker.update(make_item(f"2024-01-0{i}", "A", r))

    df = tracker.get_topk()
    assert len(df) == 3


def test_ranks_by_absolute_return_descending() -> None:
    tracker = TopKExtremeReturns(k=3)
    rets = [0.01, -0.05, 0.03, -0.10, 0.02]
    for i, r in enumerate(rets, start=1):
        tracker.update(make_item(f"2024-01-0{i}", "A", r))

    df = tracker.get_topk()
    assert list(df["rank"]) == [1, 2, 3]
    assert list(df["abs_ret"]) == pytest.approx([0.10, 0.05, 0.03])


def test_positive_and_negative_returns_are_symmetric() -> None:
    tracker = TopKExtremeReturns(k=2)
    tracker.update(make_item("2024-01-01", "A", 0.08))
    tracker.update(make_item("2024-01-02", "A", -0.08))

    df = tracker.get_topk()
    assert len(df) == 2
    assert list(df["abs_ret"]) == pytest.approx([0.08, 0.08])


def test_ignores_none_returns() -> None:
    tracker = TopKExtremeReturns(k=5)
    tracker.update(make_item("2024-01-01", "A", 0.01))
    tracker.update(make_item("2024-01-02", "A", None))
    tracker.update(make_item("2024-01-03", "A", -0.05))

    df = tracker.get_topk()
    assert len(df) == 2


def test_ignores_nan_returns() -> None:
    tracker = TopKExtremeReturns(k=5)
    tracker.update(make_item("2024-01-01", "A", 0.01))
    tracker.update(make_item("2024-01-02", "A", float("nan")))
    tracker.update(make_item("2024-01-03", "A", -0.05))

    df = tracker.get_topk()
    assert len(df) == 2


def test_replaces_smallest_when_larger_abs_return_appears() -> None:
    tracker = TopKExtremeReturns(k=2)
    tracker.update(make_item("2024-01-01", "A", 0.01))
    tracker.update(make_item("2024-01-02", "A", 0.02))
    tracker.update(make_item("2024-01-03", "A", 0.10))

    df = tracker.get_topk()
    assert list(df["abs_ret"]) == pytest.approx([0.10, 0.02])


def test_ignores_smaller_item_when_heap_full() -> None:
    tracker = TopKExtremeReturns(k=2)
    tracker.update(make_item("2024-01-01", "A", 0.10))
    tracker.update(make_item("2024-01-02", "A", 0.08))
    tracker.update(make_item("2024-01-03", "A", 0.01))

    df = tracker.get_topk()
    assert list(df["abs_ret"]) == pytest.approx([0.10, 0.08])


def test_output_dataframe_columns() -> None:
    tracker = TopKExtremeReturns(k=3)
    tracker.update(make_item("2024-01-01", "A", 0.01))
    tracker.update(make_item("2024-01-02", "A", -0.05))
    tracker.update(make_item("2024-01-03", "A", 0.03))

    df = tracker.get_topk()
    assert list(df.columns) == ["rank", "date", "ticker", "ret", "abs_ret"]


def test_empty_tracker_returns_empty_dataframe_with_columns() -> None:
    tracker = TopKExtremeReturns(k=3)
    df = tracker.get_topk()
    assert df.empty
    assert list(df.columns) == ["rank", "date", "ticker", "ret", "abs_ret"]


def test_duplicate_absolute_values_handled_stably() -> None:
    tracker = TopKExtremeReturns(k=3)
    tracker.update(make_item("2024-01-01", "A", 0.05))
    tracker.update(make_item("2024-01-02", "A", -0.05))
    tracker.update(make_item("2024-01-03", "A", 0.03))

    df = tracker.get_topk()
    assert len(df) == 3
    assert list(df["abs_ret"]) == pytest.approx([0.05, 0.05, 0.03])


def test_reset() -> None:
    tracker = TopKExtremeReturns(k=3)
    tracker.update(make_item("2024-01-01", "A", 0.01))
    tracker.update(make_item("2024-01-02", "A", -0.05))
    assert not tracker.get_topk().empty

    tracker.reset()
    df = tracker.get_topk()
    assert df.empty
    assert list(df.columns) == ["rank", "date", "ticker", "ret", "abs_ret"]


def test_invalid_k() -> None:
    with pytest.raises(ValueError):
        TopKExtremeReturns(k=0)
    with pytest.raises(ValueError):
        TopKExtremeReturns(k=-1)
