"""Run Step 1: data loading, stream construction, and full-history baseline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stock_stream.baseline import full_history_baseline, save_baseline
from stock_stream.data_loader import default_data_dir, load_all_data, save_clean_data
from stock_stream.stream import preview_stream


def main() -> None:
    raw_dir = default_data_dir()
    output_dir = PROJECT_DIR / "outputs"

    cleaned = load_all_data(raw_dir)
    clean_xlsx, clean_csv = save_clean_data(cleaned, output_dir)

    baseline = full_history_baseline(cleaned)
    baseline_xlsx, baseline_csv = save_baseline(baseline, output_dir)

    preview_path = output_dir / "stream_preview.json"
    preview_path.write_text(
        json.dumps(preview_stream(cleaned, n=12), indent=2),
        encoding="utf-8",
    )

    print(f"Clean data rows: {len(cleaned)}")
    print(f"Tickers: {', '.join(sorted(cleaned['ticker'].unique()))}")
    print(f"Clean dataset: {clean_xlsx}")
    print(f"Clean dataset csv: {clean_csv}")
    print(f"Full-history baseline: {baseline_xlsx}")
    print(f"Full-history baseline csv: {baseline_csv}")
    print(f"Stream preview: {preview_path}")


if __name__ == "__main__":
    main()
