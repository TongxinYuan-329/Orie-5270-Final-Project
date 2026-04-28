# Stock Stream Pipeline

**Streaming Sampling and Event Monitoring for Financial Time Series**
ORIE 5270 final project, Cornell University.

> **Scope note.** This project implements streaming algorithms (sampling,
> rolling volatility, extreme-event detection, top-k tracking) on top of
> a real equity dataset. It is **not** a stock-prediction or trading-
> strategy project; no forecasts, signals, or returns are generated.

## 1. Purpose

Treat historical daily stock prices as a one-pass data stream and implement
five streaming building blocks on top of a unified `StreamItem` interface:

1. Reservoir sampling
2. Heap-based sampling (random tags)
3. Online rolling-volatility monitoring
4. Extreme-return event detection
5. Top-k extreme-return tracking

A full-history baseline is computed in parallel so that selected streaming
outputs (per-ticker volatility, top-k extremes) can be compared with a
full-history baseline.

## 2. Dataset

Eight daily Yahoo Finance series, project window `2021-04-01` through
`2026-04-01`:

`AAPL, ORCL, MSFT, AMD, ASML, INTC, META, NVDA`

The raw files live in `data/`:

| File | Tickers | Layout |
|---|---|---|
| `ASML_INTC_daily.csv` | ASML, INTC (also QQQ, SPY ignored) | Yahoo multi-row CSV |
| `META_NVDA_daily.csv` | META, NVDA | Yahoo multi-row CSV |
| `sp500_AAPL_ORCL_stocks.xlsx` | AAPL, ORCL | Sheet-per-ticker XLSX |
| `sp500_MSFT_AMD_stocks.xlsx` | MSFT, AMD | Sheet-per-ticker XLSX |

After cleaning and windowing, every ticker has the same number of trading
days and the unified long-format columns:

```text
date, ticker, open, high, low, close, adj_close, volume, ret
```

Per-ticker daily returns are computed as `ret_t = close_t / close_{t-1} - 1`.

## 3. Installation

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .[dev]
```

Or with the plain requirements file:

```bash
pip install -r requirements.txt
```

## 4. Run the full pipeline (one command)

```bash
python scripts/run_full_pipeline.py
```

This runs four stages in order:

1. `run_step1_pipeline.py` — load raw data, build the stream, compute the full-history baseline.
2. `run_sampling_evaluation.py` — reservoir vs. heap sampling: empirical sampling check, runtime, memory.
3. `run_monitoring.py` — rolling-volatility snapshots, extreme-return alerts, top-k tracking.
4. `run_validation_comparison.py` — compare sampling/monitoring outputs against the baseline; write plots.

All artifacts are written to `outputs/` (see "Outputs" below).

### Run a single stage

```bash
python scripts/run_step1_pipeline.py
python scripts/run_sampling_evaluation.py
python scripts/run_monitoring.py
python scripts/run_validation_comparison.py
```

### Use the package as a library

```python
from stock_stream import (
    OnlineMonitor,
    TopKExtremeReturns,
    dataframe_to_stream,
    heap_sample,
    reservoir_sample,
)
```

## 5. Test coverage

All tests pass locally with the following result (from `coverage run -m pytest && coverage report`):

| Metric | Result |
|---|---:|
| Number of tests | 38 |
| All tests passing | yes |
| Branch coverage (overall) | **85%** |
| Branch coverage — algorithmic modules<br/>(`reservoir`, `heap_sampler`, `monitoring`, `topk`) | 100% |
| Branch coverage — `data_loader` | 80% |
| Branch coverage — `stream` | 96% |
| Branch coverage — `sampling_evaluation` | 66% (driver loops exercised end-to-end via scripts) |

To reproduce locally:

```bash
pytest
coverage run -m pytest && coverage report
```

## 6. Outputs

`outputs/`:

- `clean_stock_data.csv` / `.xlsx` — unified long-format dataset.
- `full_history_baseline.csv` / `.xlsx` — per-ticker baseline metrics.
- `stream_preview.json` — first 12 stream items.
- `sampling_correctness_frequencies.csv`, `sampling_correctness_summary.csv`,
  `sampling_runtime_comparison.csv`, `sampling_memory_comparison.csv`,
  `sampling_sample_preview.json` — sampling validation experiments.
- `monitoring_snapshots.csv`, `monitoring_alerts.csv`,
  `topk_extreme_returns.csv` — online monitoring outputs.
- `validation_comparison_summary.csv`,
  `topk_vs_baseline_comparison.csv`,
  `volatility_comparison.csv` — cross-comparison tables.
- `plots/` — diagnostic figures (volatility scatter, top-k vs. baseline,
  rolling-volatility histogram, alert-magnitude histogram).

## 7. Repository layout

```text
stock_stream_pipeline_final/
├── data/                       raw inputs (csv + xlsx)
├── src/stock_stream/           package source
│   ├── types.py                StreamItem dataclass
│   ├── data_loader.py          load + clean + window
│   ├── stream.py               dataframe_to_stream / preview_stream
│   ├── baseline.py             full-history baseline
│   ├── reservoir.py            reservoir sampling
│   ├── heap_sampler.py         heap-based sampling
│   ├── sampling_evaluation.py  empirical sampling check / runtime / memory
│   ├── monitoring.py           OnlineMonitor (rolling vol + alerts)
│   └── topk.py                 TopKExtremeReturns
├── scripts/                    runnable entry points
├── tests/                      pytest suite (38 tests)
├── outputs/                    generated artifacts
├── docs/                       per-chapter report drafts
├── pyproject.toml
├── requirements.txt
├── .gitignore
└── README.md
```

## 8. Project report

The full project report (Chapters 1–10 + appendix) is in
[`docs/final_report.md`](docs/final_report.md). Per-chapter drafts from
each team member are in the same folder:

- `docs/step1_report_draft.md` — Chapters 2, 3, 4.1
- `docs/sampling_report_draft.md` — Chapters 4.2, 4.3, 6.1–6.3
- `docs/online_monitoring_report_draft.md` — Chapters 4.4–4.7, 6.4–6.5
- `docs/schema.md` — data and stream-item schema reference

## 9. Design note: rolling-volatility convention

`OnlineMonitor` first appends the current return to the per-ticker window
and then computes the sample standard deviation, so the rolling volatility
used for the extreme-return rule includes the latest return. We treat each
emitted snapshot as a *state summary after processing the new event*. A
strict "leave-one-out" anomaly detector — using only the previous window
to score the current return and *then* updating the window — is a natural
extension and would change the alert count by at most a handful of events
at the boundary of the threshold; the design choice and the alternative
are discussed in `docs/final_report.md` Chapter 4.5.

## 10. Author / team responsibilities

| Member | Responsibility | Files |
|---|---|---|
| 1 | Data & Stream Pipeline | `data_loader.py`, `stream.py`, `baseline.py`, `types.py` |
| 2 | Streaming Sampling | `reservoir.py`, `heap_sampler.py`, `sampling_evaluation.py` |
| 3 | Online Monitoring | `monitoring.py`, `topk.py` |
| 4 | Testing & Integration | `tests/`, `scripts/run_full_pipeline.py`, `pyproject.toml`, `README.md` |
