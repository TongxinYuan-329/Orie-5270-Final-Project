"""Run sampling algorithms and experiments for report chapters 4.2/4.3/6.1-6.3."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stock_stream.sampling_evaluation import run_all_sampling_evaluations


def main() -> None:
    output_dir = PROJECT_DIR / "outputs"
    clean_csv = output_dir / "clean_stock_data.csv"
    if not clean_csv.exists():
        raise FileNotFoundError(
            f"{clean_csv} not found. Run scripts/run_step1_pipeline.py first."
        )
    paths = run_all_sampling_evaluations(clean_csv, output_dir)
    print("Sampling evaluation complete:")
    for name, path in paths.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
