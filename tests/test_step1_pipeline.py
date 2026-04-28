from __future__ import annotations

import pandas as pd
import pytest

from stock_stream.baseline import full_history_baseline
from stock_stream.data_loader import END_DATE, START_DATE, add_returns
from stock_stream.stream import dataframe_to_stream, preview_stream


def test_add_returns_computes_per_ticker_returns() -> None:
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-01", "2024-01-02"]),
            "ticker": ["AAPL", "AAPL", "ORCL", "ORCL"],
            "open": [10.0, 11.0, 20.0, 18.0],
            "high": [11.0, 12.0, 21.0, 19.0],
            "low": [9.0, 10.0, 19.0, 17.0],
            "close": [10.0, 12.0, 20.0, 18.0],
            "adj_close": [10.0, 12.0, 20.0, 18.0],
            "volume": [100, 110, 200, 210],
        }
    )

    out = add_returns(df)

    aapl = out[out["ticker"] == "AAPL"].sort_values("date")
    orcl = out[out["ticker"] == "ORCL"].sort_values("date")
    assert pd.isna(aapl["ret"].iloc[0])
    assert aapl["ret"].iloc[1] == pytest.approx(0.2)
    assert pd.isna(orcl["ret"].iloc[0])
    assert orcl["ret"].iloc[1] == pytest.approx(-0.1)


def test_stream_items_are_chronological() -> None:
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-01"]),
            "ticker": ["ORCL", "AAPL"],
            "close": [18.0, 10.0],
            "ret": [-0.1, None],
        }
    )

    items = list(dataframe_to_stream(df))

    assert items[0].date == "2024-01-01"
    assert items[0].ticker == "AAPL"
    assert items[1].date == "2024-01-02"
    assert items[1].ret == -0.1


def test_preview_stream_returns_n_dicts() -> None:
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "ticker": ["AAPL", "AAPL", "AAPL"],
            "close": [10.0, 11.0, 12.0],
            "ret": [None, 0.1, 0.0909],
        }
    )

    preview = preview_stream(df, n=2)

    assert isinstance(preview, list)
    assert len(preview) == 2
    assert set(preview[0].keys()) == {"date", "ticker", "close", "ret"}


def test_full_history_baseline_has_one_row_per_ticker() -> None:
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-01", "2024-01-02"]),
            "ticker": ["AAPL", "AAPL", "ORCL", "ORCL"],
            "low": [9.0, 10.0, 19.0, 17.0],
            "high": [11.0, 12.0, 21.0, 19.0],
            "close": [10.0, 12.0, 20.0, 18.0],
            "ret": [None, 0.2, None, -0.1],
        }
    )

    baseline = full_history_baseline(df)

    assert list(baseline["ticker"]) == ["AAPL", "ORCL"]
    assert baseline.loc[baseline["ticker"] == "AAPL", "rows"].iloc[0] == 2
    assert baseline.loc[baseline["ticker"] == "ORCL", "min_low"].iloc[0] == 17.0


def test_project_window_is_2021_2026() -> None:
    assert START_DATE == pd.Timestamp("2021-04-01")
    assert END_DATE == pd.Timestamp("2026-04-01")
