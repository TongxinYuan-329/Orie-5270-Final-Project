# Stock Stream Pipeline

Streaming sampling and event monitoring for financial time series.
ORIE 5270 final project, Cornell University, Spring 2026.

This repository implements a small Python package, `stock_stream`, that
treats five years of daily U.S. equity prices as a one-pass data stream
and applies the streaming data-structure techniques covered in the
W7D2 lecture (Zhang, 2026): reservoir sampling, heap-based sampling
with random tags, online rolling-volatility monitoring with a
threshold-based alert rule, and a bounded top-k tracker for the
largest absolute returns. The work is a streaming-algorithms exercise
applied to a real dataset; it is not a forecasting or trading project,
and it does not produce predictions, signals, or simulated returns.
The full-history baseline that the package also computes is used only
as a reference against which selected streaming outputs—per-ticker
volatility and the top-k absolute returns—can be compared.

## 1. Purpose and scope

The lecture material on data streams begins from the observation that
the conventional "all data fits in memory" assumption breaks down once
observations arrive sequentially and the stream is, in principle,
unbounded. The five components implemented here illustrate how that
observation translates into concrete data-structure choices: a
fixed-size reservoir; a bounded heap of random priorities; a per-ticker
rolling window with a single sample-variance update per arrival; a
single-pass scan that flags returns exceeding a multiple of the local
volatility; and a min-heap that keeps only the `k` largest absolute
returns ever seen. All five share a common interface, the `StreamItem`
record (`date, ticker, close, ret`), so that the data layer and the
algorithmic layer can be developed and tested independently.

A deliberate choice has been to keep the project narrow. There is no
predictive model, no portfolio-construction step, no parameter
optimisation against future returns; the only learning quantity is the
rolling sample standard deviation, which is a descriptive statistic
rather than a forecast. This narrowness is itself a substantive choice:
the lecture's principal claim is that the streaming paradigm is
worthwhile in its own right, and the value of the present project lies
in showing that the paradigm can be carried through end-to-end on real
data with reproducible numerical outputs.

## 2. Dataset

The package consumes eight Yahoo Finance daily series over the common
window 2021-04-01 to 2026-04-01: AAPL, ORCL, MSFT, AMD, ASML, INTC,
META, and NVDA. The raw files, located in `data/`, were obtained in two
different download formats; the loader in `src/stock_stream/data_loader.py`
handles both:

| File | Tickers | Layout |
|---|---|---|
| `ASML_INTC_daily.csv` | ASML, INTC (also QQQ and SPY, which are filtered out) | Yahoo multi-row CSV |
| `META_NVDA_daily.csv` | META, NVDA | Yahoo multi-row CSV |
| `sp500_AAPL_ORCL_stocks.xlsx` | AAPL, ORCL | Sheet-per-ticker XLSX |
| `sp500_MSFT_AMD_stocks.xlsx` | MSFT, AMD | Sheet-per-ticker XLSX |

After cleaning and windowing, every ticker has 1,256 trading days, and
the cleaned long-format table has the columns
`date, ticker, open, high, low, close, adj_close, volume, ret`. The
per-ticker daily return is computed as
`ret_t = close_t / close_{t-1} − 1`; the first observation for each
ticker is therefore missing and is treated as such throughout the
package.

## 3. Installation

A standard editable install from the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .[dev]
```

Or, if a more conservative path is preferred:

```bash
pip install -r requirements.txt
```

## 4. Running the pipeline

The full pipeline runs in one command:

```bash
python scripts/run_full_pipeline.py
```

Internally, this script chains four stages, each of which is also a
standalone entry point. The first stage, `run_step1_pipeline.py`, loads
the raw data files, applies the project window, computes per-ticker
returns, and writes the full-history baseline. The second stage,
`run_sampling_evaluation.py`, applies reservoir and heap-based sampling
to the resulting stream and records empirical inclusion frequencies,
runtime, and peak memory. The third, `run_monitoring.py`, runs the
online monitor and the top-k tracker over the same stream and writes
the snapshots, alert events, and ranked top-k table. The fourth,
`run_validation_comparison.py`, compares the streaming outputs against
the full-history baseline and writes the diagnostic figures.

Each stage can also be run on its own:

```bash
python scripts/run_step1_pipeline.py
python scripts/run_sampling_evaluation.py
python scripts/run_monitoring.py
python scripts/run_validation_comparison.py
```

The package can equally be used as a library, with the principal
public interfaces re-exported from the top-level module:

```python
from stock_stream import (
    OnlineMonitor,
    TopKExtremeReturns,
    dataframe_to_stream,
    heap_sample,
    reservoir_sample,
)
```

## 5. Tests and coverage

The test suite contains thirty-eight tests covering the public surface
of every module and the principal error paths. Coverage is measured
with `coverage` in branch mode and is reproduced by the two commands
below:

```bash
pytest
coverage run -m pytest && coverage report
```

The most recent local run produced the following:

| Metric | Result |
|---|---:|
| Number of tests | 38 |
| All tests passing | yes |
| Branch coverage, overall | 85% |
| Branch coverage, algorithmic modules (`reservoir`, `heap_sampler`, `monitoring`, `topk`) | 100% |
| Branch coverage, `data_loader` | 80% |
| Branch coverage, `stream` | 96% |
| Branch coverage, `sampling_evaluation` | 66% (driver loops are exercised end-to-end via the scripts rather than in isolated unit tests) |

Branch coverage of 85% is above the 80% threshold suggested in the
project rubric; the algorithmic modules, where correctness is most
consequential, are at 100%.

## 6. Outputs

All artefacts produced by the pipeline are written to `outputs/`. The
cleaned long-format dataset is saved as both
`clean_stock_data.csv` and `clean_stock_data.xlsx`; the full-history
baseline as `full_history_baseline.csv` and `full_history_baseline.xlsx`;
and the first twelve stream items as `stream_preview.json`. The
sampling stage writes `sampling_correctness_frequencies.csv`,
`sampling_correctness_summary.csv`, `sampling_runtime_comparison.csv`,
`sampling_memory_comparison.csv`, and `sampling_sample_preview.json`.
The online monitor and top-k tracker write `monitoring_snapshots.csv`,
`monitoring_alerts.csv`, and `topk_extreme_returns.csv`. The validation
stage writes `validation_comparison_summary.csv`,
`topk_vs_baseline_comparison.csv`, and `volatility_comparison.csv`,
together with four diagnostic figures in `outputs/plots/`: a per-ticker
volatility scatter, a top-k versus baseline scatter, a histogram of
rolling volatilities, and a histogram of alert magnitudes.

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
├── outputs/                    generated artefacts
├── docs/                       per-chapter report drafts
├── pyproject.toml
├── requirements.txt
├── .gitignore
└── README.md
```

## 8. Project report

The full project report is in [`docs/final_report.md`](docs/final_report.md).
The per-chapter drafts written by the individual team members during
implementation, kept for the record, are `docs/step1_report_draft.md`
(Chapters 2, 3, 4.1), `docs/sampling_report_draft.md` (Chapters 4.2,
4.3, 6.1–6.3), `docs/online_monitoring_report_draft.md` (Chapters
4.4–4.7, 6.4–6.5), and `docs/schema.md` (the data and stream-item
schema).

## 9. Design note: rolling-volatility convention

`OnlineMonitor.update` first appends the current return to the
per-ticker window and only then recomputes the sample standard
deviation, so that the rolling volatility used in the extreme-return
rule includes the latest return. The snapshot emitted at each step is
therefore best read as a state summary after the new event has been
processed. A stricter "leave-one-out" convention, in which the
volatility used to score the current return depends only on the
preceding window, would be the natural alternative; in our setting,
with a window of twenty observations and a three-sigma threshold, the
two conventions disagree on at most a handful of borderline events,
and none of the substantive findings (the META 2022-02-03 drop, the
ORCL 2025-09-10 jump, the INTC 2024-08-02 fall, and so on) depend on
which convention is adopted. The choice and its implications are
discussed at greater length in `docs/final_report.md`, Chapter 4.5.

## 10. Authorship and division of labour

| Member | Responsibility | Files |
|---|---|---|
| 1 | Data and stream pipeline | `data_loader.py`, `stream.py`, `baseline.py`, `types.py` |
| 2 | Streaming sampling | `reservoir.py`, `heap_sampler.py`, `sampling_evaluation.py` |
| 3 | Online monitoring | `monitoring.py`, `topk.py` |
| 4 | Testing, integration, packaging, and documentation | `tests/`, `scripts/run_full_pipeline.py`, `pyproject.toml`, `README.md` |
