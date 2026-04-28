"""Cross-check sampling/monitoring outputs against the full-history baseline."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend for reproducibility

import matplotlib.pyplot as plt
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
OUTPUT_DIR = PROJECT_DIR / "outputs"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input file: {path}")
    return pd.read_csv(path)


def main() -> None:
    baseline = _load_csv(OUTPUT_DIR / "full_history_baseline.csv")
    snapshots = _load_csv(OUTPUT_DIR / "monitoring_snapshots.csv")
    alerts = _load_csv(OUTPUT_DIR / "monitoring_alerts.csv")
    topk = _load_csv(OUTPUT_DIR / "topk_extreme_returns.csv")

    rolling_mean_vol = (
        snapshots.groupby("ticker", as_index=False)["rolling_volatility"]
        .mean()
        .rename(columns={"rolling_volatility": "rolling_volatility_mean"})
    )

    vol_compare = baseline.merge(rolling_mean_vol, on="ticker", how="left")
    vol_compare = vol_compare[["ticker", "return_volatility", "rolling_volatility_mean"]].copy()
    vol_compare["vol_ratio"] = (
        vol_compare["rolling_volatility_mean"] / vol_compare["return_volatility"]
    )

    print("\n[Volatility Comparison]")
    print(vol_compare.sort_values("ticker").to_string(index=False))

    if topk.empty:
        topk_max_per_ticker = pd.DataFrame({"ticker": [], "topk_max_abs_ret": []})
    else:
        topk_max_per_ticker = (
            topk.groupby("ticker", as_index=False)["abs_ret"].max()
            .rename(columns={"abs_ret": "topk_max_abs_ret"})
        )

    extreme_compare = baseline.merge(topk_max_per_ticker, on="ticker", how="left")
    extreme_compare = extreme_compare[["ticker", "max_abs_return", "topk_max_abs_ret"]].copy()
    extreme_compare["abs_diff"] = (
        extreme_compare["topk_max_abs_ret"] - extreme_compare["max_abs_return"]
    ).abs()

    print("\n[Extreme Return Comparison]")
    print(extreme_compare.sort_values("abs_diff", ascending=False).to_string(index=False))

    print("\n[Alerts Preview (largest abs_ret)]")
    if alerts.empty:
        print("(no alerts)")
    else:
        print(alerts.sort_values("abs_ret", ascending=False).head(20).to_string(index=False))

    if (not alerts.empty) and (not topk.empty):
        alerts_key = alerts[["date", "ticker", "ret"]].drop_duplicates()
        topk_key = topk[["date", "ticker", "ret"]].drop_duplicates()
        overlap = alerts_key.merge(topk_key, on=["date", "ticker", "ret"], how="inner")
        overlap_count = len(overlap)
    else:
        overlap_count = 0

    n_tickers = int(baseline["ticker"].nunique()) if "ticker" in baseline.columns else 0
    ratio_series = vol_compare["vol_ratio"].dropna()
    avg_ratio = float(ratio_series.mean()) if not ratio_series.empty else float("nan")
    diffs = extreme_compare["abs_diff"].dropna()
    max_dev = float(diffs.max()) if not diffs.empty else float("nan")

    print("\n[Summary Diagnostics]")
    print(f"Tickers: {n_tickers}")
    print(f"Average volatility ratio (rolling_mean / baseline): {avg_ratio:.4f}")
    print(f"Max deviation (|baseline max_abs_return - topk max|): {max_dev:.6f}")
    print(f"Alerts: {len(alerts)}")
    print(f"Alert/top-k overlap (date,ticker,ret): {overlap_count}")

    summary_path = OUTPUT_DIR / "validation_comparison_summary.csv"
    vol_compare.to_csv(OUTPUT_DIR / "volatility_comparison.csv", index=False)
    extreme_compare.to_csv(OUTPUT_DIR / "topk_vs_baseline_comparison.csv", index=False)
    pd.DataFrame(
        {
            "metric": [
                "n_tickers",
                "avg_vol_ratio",
                "max_topk_baseline_dev",
                "n_alerts",
                "alert_topk_overlap",
            ],
            "value": [n_tickers, avg_ratio, max_dev, len(alerts), overlap_count],
        }
    ).to_csv(summary_path, index=False)

    plot_vol = vol_compare.dropna(subset=["return_volatility", "rolling_volatility_mean"])
    plt.figure()
    plt.scatter(plot_vol["return_volatility"], plot_vol["rolling_volatility_mean"], alpha=0.7)
    if not plot_vol.empty:
        vmin = float(min(plot_vol["return_volatility"].min(), plot_vol["rolling_volatility_mean"].min()))
        vmax = float(max(plot_vol["return_volatility"].max(), plot_vol["rolling_volatility_mean"].max()))
        plt.plot([vmin, vmax], [vmin, vmax])
    plt.xlabel("baseline return_volatility")
    plt.ylabel("mean rolling_volatility")
    plt.title("Volatility comparison (per ticker)")

    plot_ext = extreme_compare.dropna(subset=["max_abs_return", "topk_max_abs_ret"])
    plt.figure()
    plt.scatter(plot_ext["max_abs_return"], plot_ext["topk_max_abs_ret"], alpha=0.7)
    if not plot_ext.empty:
        emin = float(min(plot_ext["max_abs_return"].min(), plot_ext["topk_max_abs_ret"].min()))
        emax = float(max(plot_ext["max_abs_return"].max(), plot_ext["topk_max_abs_ret"].max()))
        plt.plot([emin, emax], [emin, emax])
    plt.xlabel("baseline max_abs_return")
    plt.ylabel("topk max abs_ret (per ticker)")
    plt.title("Top-k extremes vs baseline maxima")

    plt.figure()
    if snapshots.empty:
        plt.hist([])
    else:
        plt.hist(snapshots["rolling_volatility"].dropna(), bins=30)
    plt.xlabel("rolling_volatility")
    plt.ylabel("count")
    plt.title("Distribution of rolling volatility (all snapshots)")

    plt.figure()
    if alerts.empty:
        plt.hist([])
    else:
        plt.hist(alerts["abs_ret"].dropna(), bins=30)
    plt.xlabel("abs_ret (alerts)")
    plt.ylabel("count")
    plt.title("Alert magnitude distribution")

    plots_dir = OUTPUT_DIR / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    plt.figure(1)
    plt.savefig(plots_dir / "volatility_scatter.png", dpi=200, bbox_inches="tight")

    plt.figure(2)
    plt.savefig(plots_dir / "topk_vs_baseline_scatter.png", dpi=200, bbox_inches="tight")

    plt.figure(3)
    plt.savefig(plots_dir / "rolling_volatility_hist.png", dpi=200, bbox_inches="tight")

    plt.figure(4)
    plt.savefig(plots_dir / "alert_magnitudes_hist.png", dpi=200, bbox_inches="tight")

    print(f"\nSaved diagnostic plots to: {plots_dir}")
    print(f"Saved comparison tables to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
