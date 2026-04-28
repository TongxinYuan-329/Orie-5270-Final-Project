"""Full-history baseline statistics for the stock stream."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

BASELINE_COLUMNS = [
    "ticker",
    "rows",
    "first_date",
    "last_date",
    "min_low",
    "max_high",
    "avg_close",
    "last_close",
    "avg_return",
    "return_volatility",
    "max_abs_return",
]


def full_history_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """Compute baseline metrics using the complete history of each ticker."""

    rows = []
    for ticker, group in df.sort_values("date").groupby("ticker", sort=True):
        valid_ret = group["ret"].dropna()
        rows.append(
            {
                "ticker": ticker,
                "rows": len(group),
                "first_date": pd.Timestamp(group["date"].iloc[0]).strftime("%Y-%m-%d"),
                "last_date": pd.Timestamp(group["date"].iloc[-1]).strftime("%Y-%m-%d"),
                "min_low": float(group["low"].min()),
                "max_high": float(group["high"].max()),
                "avg_close": float(group["close"].mean()),
                "last_close": float(group["close"].iloc[-1]),
                "avg_return": float(valid_ret.mean()),
                "return_volatility": float(valid_ret.std(ddof=1)),
                "max_abs_return": float(valid_ret.abs().max()),
            }
        )
    return pd.DataFrame(rows, columns=BASELINE_COLUMNS)


def save_baseline(baseline: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    """Persist baseline metrics as xlsx and csv."""

    output_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = output_dir / "full_history_baseline.xlsx"
    csv_path = output_dir / "full_history_baseline.csv"
    baseline.to_excel(xlsx_path, index=False, engine="openpyxl")
    baseline.to_csv(csv_path, index=False)
    return xlsx_path, csv_path
