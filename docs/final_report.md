# Streaming Sampling and Event Monitoring for Financial Time Series

**ORIE 5270 – Final Project**
Cornell University, Spring 2026

> **Scope.** This report describes streaming algorithms (sampling, rolling
> volatility, extreme-event detection, top-k tracking) implemented on top
> of a real equity dataset. **It is not a stock-prediction or trading-
> strategy project**: no forecasts, signals, or returns are generated.
> The full-history baseline is used purely as a reference for verifying
> that streaming outputs behave consistently with the underlying data.

---

## Chapter 1. Introduction

When a quantitative analyst receives market data, the data does not arrive
all at once: prices stream in trade-by-trade, minute-by-minute, day-by-day.
Two practical pressures appear immediately. First, the stream may be too
long to keep in memory. Second, downstream consumers — risk monitors,
alerting systems, dashboards — must update *continuously* and cannot wait
for the stream to end. These constraints match exactly the data-stream
paradigm covered in lecture (W7D2 *Data Streams*).

This project applies that paradigm to U.S. equities. Treating five years of
daily closes as a simulated stream, we build a small Python package that
reads each observation once and supports five streaming building blocks:

1. **Reservoir sampling** — keep a uniform size-`k` sample without storing
   the full history.
2. **Heap-based sampling with random tags** — keep the `k` items with the
   smallest random tags using a bounded heap.
3. **Online return calculation and rolling-volatility monitoring** —
   maintain a per-ticker rolling window and compute volatility on the fly.
4. **Extreme-return event detection** — flag any return exceeding
   `threshold × rolling_volatility`.
5. **Top-`k` extreme-return tracking** — maintain a running top-`k` of the
   largest absolute returns using a min-heap.

A full-history baseline is computed in parallel as a reference for
checking that selected streaming outputs (per-ticker volatility, the
top-k absolute returns) behave consistently with the underlying data.
The deliverable is a Python package (`stock_stream`) with a reproducible
one-command pipeline, 38 unit tests, and 85 % branch coverage.

---

## Chapter 2. Dataset and Stream Construction

We use eight Yahoo Finance daily series over the common analysis window
**2021-04-01 → 2026-04-01**:

`AAPL, ORCL, MSFT, AMD, ASML, INTC, META, NVDA`.

The raw data lives in `data/` and is split across two file formats:

| File | Tickers | Format |
|------|---------|--------|
| `ASML_INTC_daily.csv` | ASML, INTC (also QQQ, SPY ignored) | Yahoo multi-row CSV |
| `META_NVDA_daily.csv` | META, NVDA | Yahoo multi-row CSV |
| `sp500_AAPL_ORCL_stocks.xlsx` | AAPL, ORCL | sheet-per-ticker XLSX |
| `sp500_MSFT_AMD_stocks.xlsx` | MSFT, AMD | sheet-per-ticker XLSX |

Some files extend slightly outside the project window. The data loader
discards any row before 2021-04-01 or after 2026-04-01 so every ticker uses
exactly the same time horizon.

After cleaning, all eight tickers share the long-format schema

```text
date, ticker, open, high, low, close, adj_close, volume, ret
```

and the per-ticker daily return is

```text
ret_t = close_t / close_{t-1} − 1
```

The first row for each ticker has `ret = NaN` because no previous close
exists. The cleaned dataset contains **10 048 rows = 8 tickers × 1 256
trading days**.

---

## Chapter 3. Problem Formulation – Stream Setup

The cleaned dataset is sorted by `(date, ticker)` and replayed as a stream
of `StreamItem` records:

```python
@dataclass(frozen=True)
class StreamItem:
    date: str        # YYYY-MM-DD
    ticker: str
    close: float
    ret: float | None
```

Every downstream component — reservoir sampling, heap sampling, the online
monitor, and the top-k tracker — consumes the *same* iterator interface,
which decouples raw file formats from algorithmic logic and makes it
trivial to swap in a live data feed later.

---

## Chapter 4. Methods

### 4.1 Full-History Baseline

The baseline reads the cleaned dataset *once*, with random access, and
computes per-ticker statistics: row count, first and last trading dates,
min low, max high, mean close, last close, mean return, return volatility
(`std(ret, ddof=1)`), and `max |ret|`. This is the complete-information
reference against which all streaming algorithms are validated in
Chapter 6.

### 4.2 Method 1 – Reservoir Sampling

Reservoir sampling holds at most `k` items at any time. For the first `k`
arrivals it inserts directly. For the `n`-th arrival with `n > k`, the
item is accepted with probability `k / n` and, if accepted, replaces a
uniformly chosen reservoir slot. After processing `N` items, every observed
item has equal probability `k / N` of being in the final sample.

| | |
|---|---|
| Per-item update time | `O(1)` expected |
| Storage | `O(k)` |

### 4.3 Method 2 – Heap-Based Sampling with Random Tags

Each arrival is given an independent tag `u ∼ Uniform(0,1)`. A size-`k`
max-heap keyed on the tag retains the `k` smallest tags seen so far. When a
new item's tag is smaller than the heap maximum, the heap-top is replaced.
This is mathematically equivalent to "select the `k` items with the
smallest random priorities", and yields a uniform sample without
replacement.

| | |
|---|---|
| Per-item update time | `O(log k)` |
| Storage | `O(k)` |

### 4.4 Online Return Calculation

The cleaned stream already contains `ret`, so the online step only needs to
*consume* one return per arrival. Items with `ret = None` or `NaN` (the
first observation per ticker) are silently skipped because they cannot
contribute to volatility or alert calculations.

### 4.5 Rolling-Volatility Monitoring

For each ticker we maintain a `deque` of the most recent `window_size`
valid returns (default `window_size = 20`, ≈ one trading month). When the
window fills, the rolling sample standard deviation (`ddof = 1`) is
recomputed for every new arrival. Each post-window arrival emits a
*snapshot* with `(date, ticker, ret, abs_ret, rolling_volatility,
threshold, is_extreme)`. Per-ticker independence ensures volatilities are
not contaminated across firms.

#### Volatility-window convention

Two natural designs exist:

1. **State-after-event** (the convention used here). Append the new
   return to the window first, then recompute volatility, then evaluate
   the rule. The volatility used for the rule includes the current
   return. The snapshot is interpreted as *the state of the monitor
   after processing this event*.
2. **State-before-event** ("leave-one-out"). Use only the previous
   window to score the current return; update the window afterwards.

Design 2 is sometimes preferred for anomaly-detection writeups because
the score is independent of the value being scored. Design 1 is simpler
and is the convention adopted by `OnlineMonitor`. With `window_size = 20`
and `threshold = 3 σ`, the two designs disagree on at most a handful of
events near the boundary; the substantive findings (e.g. the META
2022-02-03 and ORCL 2025-09-10 alerts) are unchanged. Switching
conventions would require swapping two lines in `monitoring.py:update`
and is a clean extension rather than a bug fix.

### 4.6 Extreme-Return Event Detection

A snapshot is flagged as **extreme** when

```text
|ret_t| > threshold × rolling_volatility_t
```

with default `threshold = 3.0`. The rule is *adaptive*: a 3 % return is
extreme during a calm regime but routine during a turbulent one. All
flagged events are written to `outputs/monitoring_alerts.csv`.

### 4.7 Top-`k` Extreme-Return Tracking

To recover the largest absolute returns over the entire stream without
storing the entire stream, we keep a bounded **min-heap** of size `k`
keyed on `abs_ret`. When the heap is full and a new arrival's `abs_ret`
exceeds the heap minimum, we replace it. At the end the heap is sorted in
descending order to produce a ranked top-`k` table.

| | |
|---|---|
| Per-item update time | `O(log k)` |
| Storage | `O(k)` |

---

## Chapter 5. Implementation Design

### 5.1 Package layout

```text
stock_stream_pipeline_final/
├── data/                          raw inputs (csv + xlsx)
├── src/stock_stream/              package source
│   ├── types.py                   StreamItem dataclass
│   ├── data_loader.py             format-aware loader + windowing
│   ├── stream.py                  dataframe_to_stream / preview_stream
│   ├── baseline.py                full-history baseline
│   ├── reservoir.py               reservoir sampling
│   ├── heap_sampler.py            heap-based sampling
│   ├── sampling_evaluation.py     correctness / runtime / memory
│   ├── monitoring.py              OnlineMonitor (rolling vol + alerts)
│   └── topk.py                    TopKExtremeReturns
├── scripts/                       runnable entry points
├── tests/                         pytest suite (38 tests)
├── outputs/                       generated artifacts
└── docs/                          this report and per-chapter drafts
```

### 5.2 Module dependency graph

```text
types ─────► stream ─────► sampling_evaluation
   │            │              │
   │            ▼              ▼
   ├──► baseline             reservoir, heap_sampler
   │
   └──► monitoring, topk
            ▲
            │
       data_loader (raw csv/xlsx → cleaned dataframe → stream)
```

The unified `StreamItem` interface is the single contract between the data
layer (`data_loader`, `stream`) and the algorithmic layer (`reservoir`,
`heap_sampler`, `monitoring`, `topk`).

### 5.3 Entry-point scripts

| Script | Purpose |
|--------|---------|
| `scripts/run_step1_pipeline.py` | raw → clean dataset, baseline, stream preview |
| `scripts/run_sampling_evaluation.py` | correctness, runtime, memory experiments |
| `scripts/run_monitoring.py` | snapshots, alerts, top-k |
| `scripts/run_validation_comparison.py` | cross-checks + four diagnostic plots |
| `scripts/run_full_pipeline.py` | runs all four stages in one command |

---

## Chapter 6. Experiments

### 6.1 Empirical sampling check

Both reservoir and heap sampling are *randomized* algorithms; their
guarantee is at the level of the inclusion *distribution*, not on any
single run. To check this empirically, for each method we run 500
independent samples of size `k = 50` over the cleaned stream of length
`N = 10 048` and count how often each observation is selected.

| Method | `k / N` (theory) | mean selection prob (empirical) | std of per-item prob |
|---|---:|---:|---:|
| Reservoir | 0.004976 | 0.004976 | 0.003155 |
| Heap | 0.004976 | 0.004976 | 0.003110 |

Both empirical means match the theoretical value to six decimals, and
the per-item standard deviation is consistent with the finite-sample
binomial noise that a uniform sampler would produce. This is consistent
with — but, by construction, not a *proof* of — uniformity; the formal
guarantees come from the inductive arguments sketched in the lecture.

Outputs: `sampling_correctness_frequencies.csv`,
`sampling_correctness_summary.csv`.

### 6.2 Runtime comparison

Stream lengths `N ∈ {1 000, 10 000, 10 048}`, sample sizes
`k ∈ {10, 50, 100}`, 5 repeats per configuration.

| `N` | `k` | reservoir mean (ms) | heap mean (ms) |
|------:|-----:|---------------------:|---------------:|
| 1 000 | 10 | 0.26 | 0.08 |
| 1 000 | 100 | 0.26 | 0.11 |
| 10 000 | 10 | 2.54 | 0.57 |
| 10 000 | 100 | 2.57 | 0.66 |

The heap-based sampler is ~4× faster in absolute wall-clock time at this
scale even though its asymptotic per-item cost (`O(log k)`) is *worse*
than the reservoir sampler's (`O(1)` expected). The reason is constant
factors: reservoir sampling calls `rng.randint` and `rng.randrange`
twice per accepted item, while the heap sampler does one `rng.random`
plus an occasional `heapreplace`.

The asymptotic ranking would still favour reservoir for very large `k`,
but in the realistic streaming regime (`k` bounded, `N` huge) heap
sampling is competitive in Python.

Output: `sampling_runtime_comparison.csv`.

### 6.3 Memory comparison

| Method | `k` | peak memory (B) |
|--------|----:|------------------:|
| full-history baseline | — | 80 440 |
| reservoir | 10 | 3 332 |
| reservoir | 100 | 4 068 |
| heap | 10 | 3 552 |
| heap | 100 | 8 480 |

Both streaming samplers use **20–25× less peak memory** than the
full-history baseline, and reservoir's footprint grows much more slowly
in `k` than heap's because the heap stores three extra fields per slot
(tag, order, item).

Output: `sampling_memory_comparison.csv`.

### 6.4 Online-monitoring experiment

Window 20, threshold 3.0. The monitor processed the entire stream in one
pass and produced **9 888 snapshots and 96 alerts**. The first 19 returns
per ticker (8 × 19 = 152) are used to fill the rolling window and do not
emit snapshots, which explains the gap from 10 048.

Examples of detected extreme events (full list in
`outputs/monitoring_alerts.csv`):

| date | ticker | ret | rolling vol | comment |
|------|--------|-----:|-------------:|---------|
| 2025-09-10 | ORCL | +0.359 | 0.085 | cloud-AI guidance surprise |
| 2022-02-03 | META | −0.264 | 0.063 | Q4 2021 earnings miss |
| 2024-08-02 | INTC | −0.261 | 0.064 | Q2 2024 guidance + dividend cut |
| 2022-10-27 | META | −0.246 | 0.061 | Q3 2022 earnings |
| 2023-05-25 | NVDA | +0.244 | 0.058 | AI-driven guidance raise |

The histogram in `outputs/plots/alert_magnitudes_hist.png` shows most
alerts cluster in `|ret| ∈ [0.04, 0.16]` with a heavy right tail. The
volatility scatter in `outputs/plots/volatility_scatter.png` shows that
the average rolling volatility is consistently slightly *below* the
full-history volatility (mean ratio ≈ 0.92), as expected: a 20-day window
under-weights the rare full-period blow-ups.

### 6.5 Top-`k` experiment

`k = 10`. The bounded heap returns the same 10 events that the
full-history baseline's `max |ret|` per ticker would return — the
scatter in `outputs/plots/topk_vs_baseline_scatter.png` lies exactly on
the 45° line, with **max deviation 0.000000** across the five tickers
that contributed to the top 10. AAPL, ASML, MSFT did not place any
observation in the global top 10 (their per-ticker maxima are smaller),
which is consistent with the baseline's `max_abs_return` ranking.

Output: `outputs/topk_extreme_returns.csv`.

---

## Chapter 7. Unit Testing and Reproducibility

### 7.1 Test suite

The 38-test suite (`tests/`) covers every public function and every error
path:

| Module | Tests | What is verified |
|--------|------:|------------------|
| `data_loader.py` | 3 | format-aware loading, project window, equal rows per ticker |
| `stream.py` / `baseline.py` | 4 | chronological order, return computation, baseline shape, project window constants |
| `reservoir.py` / `heap_sampler.py` / `sampling_evaluation.py` | 7 | exact-`k` output, short-stream behaviour, `k = 0`, `k < 0` error, correctness/runtime/memory schemas |
| `monitoring.py` | 11 | window-fill behaviour, vol formula, threshold rule, ticker independence, NaN/None handling, dataframe schemas, reset, init validation |
| `topk.py` | 13 | partial fill, ranking, sign symmetry, NaN/None handling, replacement rule, reset, init validation |

Run:

```bash
pytest                              # 38 passed
coverage run -m pytest && coverage report
```

### 7.2 Coverage

Branch coverage is **85 %** overall, exceeding the project's 80 % target:

```text
Name                                Stmts  Miss Branch BrPart  Cover
src/stock_stream/__init__.py            8     0      0      0   100%
src/stock_stream/baseline.py           17     6      2      0    68%
src/stock_stream/data_loader.py       103    17     30      9    80%
src/stock_stream/heap_sampler.py       22     0     10      0   100%
src/stock_stream/monitoring.py         51     0     16      0   100%
src/stock_stream/reservoir.py          21     0     10      0   100%
src/stock_stream/sampling_evaluation.py 101  32     32      1    66%
src/stock_stream/stream.py             17     0      6      1    96%
src/stock_stream/topk.py               38     0     14      0   100%
src/stock_stream/types.py               8     0      0      0   100%
TOTAL                                 386    55    120     11    85%
```

Algorithmic modules (`reservoir`, `heap_sampler`, `monitoring`, `topk`)
are at 100 % branch coverage; the lower-coverage modules consist of CSV/
XLSX writer paths and large experiment-driver loops that are exercised
end-to-end by the pipeline scripts but not in isolated unit tests.

### 7.3 One-command reproducibility

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_full_pipeline.py
```

The full pipeline regenerates **every** CSV, XLSX, JSON, and PNG in
`outputs/` from the four raw files in `data/` in under five seconds on a
laptop.

---

## Chapter 8. Results

1. **Sampling is empirically uniform and cheap.** Across 500 runs, both
   reservoir and heap sampling match the theoretical inclusion
   probability `k/N` to six decimals, and both use 20–25× less memory
   than the full-history baseline.
2. **Heap is faster in practice, reservoir is leaner.** At `N = 10 000`
   the heap sampler is roughly 4× faster in wall-clock terms despite a
   larger asymptotic constant; reservoir keeps a smaller and slower-growing
   memory footprint.
3. **Online monitoring matches well-known events.** The 96 alerts include
   the META 2022-02-03 earnings drop, the INTC 2024-08-02 guidance cut,
   the NVDA 2023-05-25 guidance beat, and the ORCL 2025-09-10 cloud-AI
   surprise — every one of these is a real news event that triggered a
   ≥ 3σ daily move.
4. **Top-`k` matches the baseline.** The bounded heap recovers the same
   10 largest absolute-return events as the full-history baseline (zero
   deviation across the five tickers contributing to the global top 10),
   while using O(`k`) instead of O(`N`) memory. Note that this is a
   *deterministic* selection rule, not a randomized sampler, so an exact
   match is the expected outcome.
5. **Average rolling volatility runs ≈ 8 % below baseline volatility.**
   This is consistent with the sliding window under-weighting rare,
   full-period shocks.

---

## Chapter 9. Limitations

- **Daily granularity only.** The pipeline assumes a fixed, regular
  cadence. Tick-level or irregular streams would require time-weighted
  rolling statistics.
- **Threshold-based alerts** are simple and adaptive but can produce
  clusters of alerts during regime shifts (e.g. earnings week). A
  cooldown or volatility-of-volatility rule could reduce noise.
- **Single random tag per item** for heap sampling — to support sampling
  with replacement or weighted sampling we would need a different priority
  function (e.g. the A-Res algorithm).
- **No live feed.** The streaming behaviour is *simulated* by replaying a
  cleaned dataframe in date order. A real production deployment would
  swap `dataframe_to_stream` for a websocket/Kafka adapter; everything
  downstream stays unchanged thanks to the `StreamItem` interface.

---

## Chapter 10. Conclusion

The project closes the loop between the lecture material on data streams
and a reproducible quantitative-finance pipeline that is *not* a
prediction or trading system: every component is a streaming data-
structure exercise applied to real equity data. We implemented both
classical streaming-sampling algorithms, a per-ticker rolling-volatility
monitor, a threshold-based extreme-return alert rule, and a bounded
top-`k` tracker, all on top of a single `StreamItem` interface. The
randomized samplers behave empirically as the theory predicts (mean
inclusion probability matches `k/N` to six decimals over 500 runs); the
deterministic top-`k` tracker recovers the same global top-10 events as
the full-history baseline; and all four streaming components run in
memory bounded by `k` or `window_size` rather than by `N`, validating
the data-stream paradigm on five years of U.S. equity data. The package
ships with 38 unit tests and 85 % branch coverage, and the entire
deliverable can be regenerated with a single command from raw inputs.

---

## Appendix A. File-to-Chapter Map

| Code / data file | Chapter |
|------------------|---------|
| `data/*.csv`, `data/*.xlsx` | 2 |
| `src/stock_stream/data_loader.py`, `stream.py`, `types.py` | 2, 3 |
| `src/stock_stream/baseline.py` | 4.1 |
| `src/stock_stream/reservoir.py` | 4.2 |
| `src/stock_stream/heap_sampler.py` | 4.3 |
| `src/stock_stream/monitoring.py` | 4.4, 4.5, 4.6 |
| `src/stock_stream/topk.py` | 4.7 |
| `src/stock_stream/sampling_evaluation.py` | 6.1, 6.2, 6.3 |
| `scripts/run_*` | 5.3 |
| `tests/*` | 7 |
| `outputs/full_history_baseline.csv` | 4.1, 6.5 |
| `outputs/sampling_correctness_*.csv` | 6.1 |
| `outputs/sampling_runtime_comparison.csv` | 6.2 |
| `outputs/sampling_memory_comparison.csv` | 6.3 |
| `outputs/monitoring_snapshots.csv` | 6.4 |
| `outputs/monitoring_alerts.csv` | 4.6, 6.4 |
| `outputs/topk_extreme_returns.csv` | 4.7, 6.5 |
| `outputs/plots/*.png` | 6.4, 6.5 |
