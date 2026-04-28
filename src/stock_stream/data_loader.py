"""Load, clean, and standardize the raw stock data files.

Two raw layouts are supported, both produced by Yahoo Finance style downloads:

1. Yahoo multi-row format (csv or xlsx) with three header rows:
   ``Price`` row (Open/High/Low/Close/Volume),
   ``Ticker`` row (per-ticker labels), and a blank/Date row.

2. Sheet-per-ticker xlsx format with one sheet per ticker and the columns
   ``date, open, high, low, close, adj_close, volume``.

The eight target tickers are filtered into the common project window
``2021-04-01`` through ``2026-04-01``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

EXPECTED_TICKERS = ("AAPL", "ORCL", "MSFT", "AMD", "ASML", "INTC", "META", "NVDA")
START_DATE = pd.Timestamp("2021-04-01")
END_DATE = pd.Timestamp("2026-04-01")
STANDARD_COLUMNS = [
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "ret",
]

DEFAULT_FILES: dict[str, tuple[str, ...]] = {
    "ASML_INTC_daily.csv": ("ASML", "INTC"),
    "META_NVDA_daily.csv": ("META", "NVDA"),
    "sp500_AAPL_ORCL_stocks.xlsx": ("AAPL", "ORCL"),
    "sp500_MSFT_AMD_stocks.xlsx": ("MSFT", "AMD"),
}


def project_root() -> Path:
    """Return the package root that contains the ``data/`` folder."""

    return Path(__file__).resolve().parents[2]


def default_data_dir() -> Path:
    """Return the default location of the raw data files."""

    return project_root() / "data"


def _clean_column_name(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_")


def _parse_dates(values: pd.Series) -> pd.Series:
    """Parse either normal dates or Excel serial dates."""

    if pd.api.types.is_datetime64_any_dtype(values):
        return pd.to_datetime(values, errors="coerce")
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.notna().sum() > values.notna().sum() / 2:
        return pd.to_datetime(numeric, unit="D", origin="1899-12-30", errors="coerce")
    return pd.to_datetime(values, errors="coerce")


def _standardize_one_ticker(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Standardize a single-ticker frame into the common long format."""

    renamed = {_clean_column_name(c): c for c in df.columns}
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = required.difference(renamed)
    if missing:
        raise ValueError(f"{ticker}: missing required columns {sorted(missing)}")

    out = pd.DataFrame(
        {
            "date": _parse_dates(df[renamed["date"]]),
            "ticker": ticker,
            "open": pd.to_numeric(df[renamed["open"]], errors="coerce"),
            "high": pd.to_numeric(df[renamed["high"]], errors="coerce"),
            "low": pd.to_numeric(df[renamed["low"]], errors="coerce"),
            "close": pd.to_numeric(df[renamed["close"]], errors="coerce"),
            "adj_close": pd.to_numeric(
                df[renamed.get("adj_close", renamed["close"])], errors="coerce"
            ),
            "volume": pd.to_numeric(df[renamed["volume"]], errors="coerce"),
        }
    )
    out = out.dropna(subset=["date", "close"]).sort_values("date")
    out["volume"] = out["volume"].astype("Int64")
    return out


def _load_sheet_xlsx(path: Path, tickers: tuple[str, ...]) -> list[pd.DataFrame]:
    """Load a sheet-per-ticker xlsx file."""

    frames: list[pd.DataFrame] = []
    xls = pd.ExcelFile(path)
    available = set(xls.sheet_names)
    for ticker in tickers:
        if ticker not in available:
            continue
        raw = pd.read_excel(path, sheet_name=ticker)
        frames.append(_standardize_one_ticker(raw, ticker))
    return frames


def _frames_from_multiline(raw: pd.DataFrame, tickers: tuple[str, ...]) -> list[pd.DataFrame]:
    """Reshape a Yahoo multi-row table (already loaded with header=[0,1])."""

    date_col = ("Price", "Ticker")
    if date_col not in raw.columns:
        return []

    raw = raw[raw[date_col].astype(str).str.lower() != "date"].copy()
    dates = _parse_dates(raw[date_col])
    fields = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}

    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        if ("Close", ticker) not in raw.columns:
            continue
        out = pd.DataFrame({"date": dates, "ticker": ticker})
        for dst, src in fields.items():
            out[dst] = pd.to_numeric(raw[(src, ticker)], errors="coerce")
        # These files do not always contain Adj Close explicitly. Keep the schema stable.
        out["adj_close"] = out["close"]
        out = out.dropna(subset=["date", "close"]).sort_values("date")
        out["volume"] = out["volume"].astype("Int64")
        frames.append(out)
    return frames


def _load_yahoo_multiline_xlsx(path: Path, tickers: tuple[str, ...]) -> list[pd.DataFrame]:
    raw = pd.read_excel(path, sheet_name=0, header=[0, 1])
    return _frames_from_multiline(raw, tickers)


def _load_yahoo_multiline_csv(path: Path, tickers: tuple[str, ...]) -> list[pd.DataFrame]:
    raw = pd.read_csv(path, header=[0, 1])
    return _frames_from_multiline(raw, tickers)


def load_raw_file(path: Path, tickers: tuple[str, ...]) -> pd.DataFrame:
    """Load one raw file (csv or xlsx) into the common long format without returns."""

    suffix = path.suffix.lower()
    if suffix == ".csv":
        frames = _load_yahoo_multiline_csv(path, tickers)
    elif suffix in {".xlsx", ".xls"}:
        frames = _load_sheet_xlsx(path, tickers)
        if not frames:
            frames = _load_yahoo_multiline_xlsx(path, tickers)
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")

    if not frames:
        raise ValueError(f"Could not load expected tickers from {path}")
    return pd.concat(frames, ignore_index=True)


def add_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-ticker close-to-close daily returns."""

    out = df.copy()
    out = out.sort_values(["ticker", "date"]).reset_index(drop=True)
    out["ret"] = out.groupby("ticker")["close"].pct_change()
    out = out.sort_values(["date", "ticker"]).reset_index(drop=True)
    return out[STANDARD_COLUMNS]


def load_all_data(raw_dir: Path | None = None) -> pd.DataFrame:
    """Load all project raw files and return a cleaned long-format DataFrame.

    Tickers are truncated to the common analysis window 2021-04-01 through
    2026-04-01 before returns are computed, so every streamed observation
    uses the same project time horizon.
    """

    root = raw_dir or default_data_dir()
    frames = []
    for filename, tickers in DEFAULT_FILES.items():
        path = root / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing raw dataset: {path}")
        frames.append(load_raw_file(path, tickers))

    combined = pd.concat(frames, ignore_index=True)
    combined = combined[combined["ticker"].isin(EXPECTED_TICKERS)]
    combined = combined[(combined["date"] >= START_DATE) & (combined["date"] <= END_DATE)]
    return add_returns(combined)


def save_clean_data(df: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    """Persist the cleaned dataset as both xlsx and csv."""

    output_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = output_dir / "clean_stock_data.xlsx"
    csv_path = output_dir / "clean_stock_data.csv"
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    df.to_csv(csv_path, index=False)
    return xlsx_path, csv_path
