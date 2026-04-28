from __future__ import annotations

import math

import pytest

from stock_stream.monitoring import OnlineMonitor
from stock_stream.types import StreamItem


def make_item(date: str, ticker: str, ret: float | None) -> StreamItem:
    return StreamItem(date=date, ticker=ticker, close=100.0, ret=ret)


def test_no_output_before_window_full() -> None:
    monitor = OnlineMonitor(window_size=3)

    assert monitor.update(make_item("2024-01-01", "AAPL", 0.01)) is None
    assert monitor.update(make_item("2024-01-02", "AAPL", 0.02)) is None

    snapshots = monitor.get_snapshots()
    assert snapshots.empty


def test_rolling_volatility_correct() -> None:
    monitor = OnlineMonitor(window_size=3)

    monitor.update(make_item("2024-01-01", "AAPL", 0.01))
    monitor.update(make_item("2024-01-02", "AAPL", 0.02))
    snapshot = monitor.update(make_item("2024-01-03", "AAPL", 0.03))

    assert snapshot is not None

    expected = math.sqrt(((0.01 - 0.02) ** 2 + (0.02 - 0.02) ** 2 + (0.03 - 0.02) ** 2) / 2)
    assert snapshot["rolling_volatility"] == pytest.approx(expected)


def test_extreme_detection() -> None:
    monitor = OnlineMonitor(window_size=3, threshold=2.0)

    monitor.update(make_item("2024-01-01", "AAPL", 0.099))
    monitor.update(make_item("2024-01-02", "AAPL", 0.100))
    snapshot = monitor.update(make_item("2024-01-03", "AAPL", 0.101))

    assert snapshot is not None
    assert bool(snapshot["is_extreme"]) is True

    alerts_df = monitor.get_alerts()
    assert len(alerts_df) == 1
    assert alerts_df.iloc[0]["ticker"] == "AAPL"
    assert alerts_df.iloc[0]["date"] == "2024-01-03"
    assert bool(alerts_df.iloc[0]["is_extreme"]) is True


def test_no_extreme_below_threshold() -> None:
    monitor = OnlineMonitor(window_size=3, threshold=4.0)

    monitor.update(make_item("2024-01-01", "AAPL", 0.01))
    monitor.update(make_item("2024-01-02", "AAPL", 0.02))
    snapshot = monitor.update(make_item("2024-01-03", "AAPL", 0.03))

    assert snapshot is not None
    assert snapshot["is_extreme"] is False
    assert monitor.get_alerts().empty


def test_ticker_independence() -> None:
    monitor = OnlineMonitor(window_size=3)

    monitor.update(make_item("2024-01-01", "A", 0.01))
    monitor.update(make_item("2024-01-01", "B", 0.10))
    monitor.update(make_item("2024-01-02", "A", 0.02))
    monitor.update(make_item("2024-01-02", "B", 0.20))
    monitor.update(make_item("2024-01-03", "A", 0.03))
    monitor.update(make_item("2024-01-03", "B", 0.30))

    snapshots = monitor.get_snapshots()
    assert not snapshots.empty

    a_last = snapshots[snapshots["ticker"] == "A"].iloc[-1]
    b_last = snapshots[snapshots["ticker"] == "B"].iloc[-1]

    assert a_last["rolling_volatility"] != b_last["rolling_volatility"]
    assert a_last["rolling_volatility"] == pytest.approx(0.01)
    assert b_last["rolling_volatility"] == pytest.approx(0.1)


def test_ignore_none_returns() -> None:
    monitor = OnlineMonitor(window_size=3)

    assert monitor.update(make_item("2024-01-01", "AAPL", 0.01)) is None
    assert monitor.update(make_item("2024-01-02", "AAPL", None)) is None
    assert monitor.update(make_item("2024-01-03", "AAPL", 0.02)) is None
    snapshot = monitor.update(make_item("2024-01-04", "AAPL", 0.03))

    assert snapshot is not None
    assert len(monitor.get_snapshots()) == 1


def test_ignore_nan_returns() -> None:
    monitor = OnlineMonitor(window_size=3)

    assert monitor.update(make_item("2024-01-01", "AAPL", 0.01)) is None
    assert monitor.update(make_item("2024-01-02", "AAPL", float("nan"))) is None
    assert monitor.update(make_item("2024-01-03", "AAPL", 0.02)) is None
    snapshot = monitor.update(make_item("2024-01-04", "AAPL", 0.03))

    assert snapshot is not None
    assert len(monitor.get_snapshots()) == 1


def test_alerts_and_snapshots_dataframe_structure() -> None:
    monitor = OnlineMonitor(window_size=3, threshold=2.0)

    monitor.update(make_item("2024-01-01", "AAPL", 0.099))
    monitor.update(make_item("2024-01-02", "AAPL", 0.100))
    monitor.update(make_item("2024-01-03", "AAPL", 0.101))

    expected = [
        "date",
        "ticker",
        "ret",
        "abs_ret",
        "rolling_volatility",
        "threshold",
        "is_extreme",
    ]
    assert list(monitor.get_snapshots().columns) == expected
    assert list(monitor.get_alerts().columns) == expected


def test_reset() -> None:
    monitor = OnlineMonitor(window_size=3)
    monitor.update(make_item("2024-01-01", "AAPL", 0.01))
    monitor.update(make_item("2024-01-02", "AAPL", 0.02))
    monitor.update(make_item("2024-01-03", "AAPL", 0.03))

    assert not monitor.get_snapshots().empty

    monitor.reset()

    assert monitor.get_snapshots().empty
    assert monitor.get_alerts().empty


def test_invalid_initialization() -> None:
    with pytest.raises(ValueError):
        OnlineMonitor(window_size=1)
    with pytest.raises(ValueError):
        OnlineMonitor(window_size=3, threshold=0)
