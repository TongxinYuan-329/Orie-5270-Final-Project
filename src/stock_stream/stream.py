"""Stream construction utilities."""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from stock_stream.types import StreamItem


def dataframe_to_stream(df: pd.DataFrame) -> Iterator[StreamItem]:
    """Yield stock observations in chronological order."""

    ordered = df.sort_values(["date", "ticker"])
    for row in ordered.itertuples(index=False):
        ret = None if pd.isna(row.ret) else float(row.ret)
        date = pd.Timestamp(row.date).strftime("%Y-%m-%d")
        yield StreamItem(
            date=date,
            ticker=str(row.ticker),
            close=float(row.close),
            ret=ret,
        )


def preview_stream(df: pd.DataFrame, n: int = 10) -> list[dict[str, float | str | None]]:
    """Return the first n stream items as serializable dictionaries."""

    items: list[dict[str, float | str | None]] = []
    for item in dataframe_to_stream(df):
        items.append(
            {
                "date": item.date,
                "ticker": item.ticker,
                "close": item.close,
                "ret": item.ret,
            }
        )
        if len(items) >= n:
            break
    return items
