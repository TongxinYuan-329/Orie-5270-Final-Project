from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from stock_stream.data_loader import (
    DEFAULT_FILES,
    EXPECTED_TICKERS,
    default_data_dir,
    load_all_data,
    load_raw_file,
)

DATA_DIR = default_data_dir()


def _data_files_present() -> bool:
    return all((DATA_DIR / name).exists() for name in DEFAULT_FILES)


needs_data = pytest.mark.skipif(
    not _data_files_present(),
    reason="raw data files not available",
)


@needs_data
def test_load_each_raw_file_yields_expected_tickers() -> None:
    for filename, tickers in DEFAULT_FILES.items():
        df = load_raw_file(DATA_DIR / filename, tickers)
        assert set(df["ticker"].unique()).issuperset(set(tickers))
        assert {"date", "open", "high", "low", "close", "volume"}.issubset(df.columns)


@needs_data
def test_load_all_data_window_and_tickers() -> None:
    df = load_all_data(DATA_DIR)
    assert set(df["ticker"].unique()) == set(EXPECTED_TICKERS)
    assert df["date"].min() >= pd.Timestamp("2021-04-01")
    assert df["date"].max() <= pd.Timestamp("2026-04-01")
    assert df.groupby("ticker")["ret"].apply(lambda s: s.iloc[0]).isna().all()


@needs_data
def test_load_all_data_has_consistent_row_count_per_ticker() -> None:
    df = load_all_data(DATA_DIR)
    counts = df.groupby("ticker").size()
    assert counts.nunique() == 1, f"unequal rows per ticker: {counts.to_dict()}"
