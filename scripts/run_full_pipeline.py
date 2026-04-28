"""One-click runner: data -> sampling -> monitoring -> validation."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
SCRIPTS_DIR = PROJECT_DIR / "scripts"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_monitoring
import run_sampling_evaluation
import run_step1_pipeline
import run_validation_comparison


def banner(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:
    banner("Step 1: Data & Stream Pipeline")
    run_step1_pipeline.main()

    banner("Step 2: Streaming Sampling (reservoir + heap)")
    run_sampling_evaluation.main()

    banner("Step 3: Online Monitoring + Top-k")
    run_monitoring.main()

    banner("Step 4: Validation & Plots")
    run_validation_comparison.main()

    banner("Pipeline complete")
    print(f"All outputs are in: {(PROJECT_DIR / 'outputs').as_posix()}")


if __name__ == "__main__":
    main()
