"""Run online monitoring and top-k tracking on the cleaned stream."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
OUTPUT_DIR = PROJECT_DIR / "outputs"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stock_stream.monitoring import OnlineMonitor  # noqa: E402
from stock_stream.stream import dataframe_to_stream  # noqa: E402
from stock_stream.topk import TopKExtremeReturns  # noqa: E402


def validate_columns(df: pd.DataFrame) -> None:
    required = ["date", "ticker", "close", "ret"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def run_monitoring(
    window_size: int = 20,
    threshold: float = 3.0,
    k: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int]:
    input_path = OUTPUT_DIR / "clean_stock_data.csv"
    if not input_path.exists():
        raise FileNotFoundError(
            f"{input_path} not found. Run scripts/run_step1_pipeline.py first."
        )

    df = pd.read_csv(input_path)
    validate_columns(df)

    stream = dataframe_to_stream(df)

    monitor = OnlineMonitor(window_size=window_size, threshold=threshold)
    topk = TopKExtremeReturns(k=k)

    total_count = 0
    for item in stream:
        monitor.update(item)
        topk.update(item)
        total_count += 1

    snapshots_df = monitor.get_snapshots()
    alerts_df = monitor.get_alerts()
    topk_df = topk.get_topk()

    return snapshots_df, alerts_df, topk_df, total_count


def save_monitoring_outputs(
    snapshots_df: pd.DataFrame,
    alerts_df: pd.DataFrame,
    topk_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Save monitoring outputs to CSV files in the output directory."""

    output_dir.mkdir(parents=True, exist_ok=True)

    snapshots_path = output_dir / "monitoring_snapshots.csv"
    alerts_path = output_dir / "monitoring_alerts.csv"
    topk_path = output_dir / "topk_extreme_returns.csv"

    snapshots_df.to_csv(snapshots_path, index=False)
    alerts_df.to_csv(alerts_path, index=False)
    topk_df.to_csv(topk_path, index=False)

    print(f"Saved monitoring snapshots to: {snapshots_path}")
    print(f"Saved monitoring alerts to:    {alerts_path}")
    print(f"Saved top-k results to:        {topk_path}")


def main() -> None:
    snapshots_df, alerts_df, topk_df, total_count = run_monitoring()

    save_monitoring_outputs(
        snapshots_df=snapshots_df,
        alerts_df=alerts_df,
        topk_df=topk_df,
        output_dir=OUTPUT_DIR,
    )

    print("[Monitoring Complete]")
    print(f"Processed: {total_count} rows")
    print(f"Snapshots: {len(snapshots_df)}")
    print(f"Alerts:    {len(alerts_df)}")
    print(f"Top-k:     {len(topk_df)}")


if __name__ == "__main__":
    main()
