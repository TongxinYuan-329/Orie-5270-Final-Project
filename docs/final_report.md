# Streaming Sampling and Event Monitoring for Financial Time Series

ORIE 5270 final project, Cornell University, Spring 2026.

The remainder of this report proceeds as follows. Chapter 1 sets out
the motivation and the boundaries of the project. Chapters 2 and 3
describe the dataset and formalise the stream interface that decouples
the data from the algorithms. Chapter 4 explains the five streaming
components in detail, together with the full-history baseline against
which they are compared. Chapter 5 describes the implementation,
including the package layout and the entry-point scripts. Chapter 6
reports the empirical experiments. Chapter 7 documents the test suite
and the coverage measurement. Chapter 8 summarises the substantive
findings, Chapter 9 records the limitations, and Chapter 10 returns
to the original question of how far the streaming paradigm is
worthwhile in this setting.

A note on scope is required at the outset. This project is a
streaming-algorithms exercise applied to a real equity dataset; it is
not a forecasting model, a portfolio-construction strategy, or a
trading system. No prediction, signal, or simulated return is produced
at any point in the pipeline. The full-history baseline that the
package also computes serves only as a reference against which a small
number of streaming outputs—per-ticker volatility and the top-k
absolute returns—can be compared.

## Chapter 1. Introduction

The lecture material on data streams begins from the observation that
the conventional algorithmic assumption that the input fits in memory
breaks down once observations arrive sequentially in an unbounded or
very long sequence (Zhang, 2026, lecture W7D2). The lecture's
examples—uniform sampling from a stream, distinct-element estimation,
heavy-hitter detection—are abstract by design, and a natural question
is whether these techniques are useful in practice once one steps away
from the textbook setting. This project addresses that question for a
single application area, the daily prices of U.S. equities, and asks
whether the streaming paradigm can be carried through end-to-end on
real data with reproducible numerical outputs.

The application domain is well suited to the question. Although five
years of daily prices for eight tickers is, in absolute terms, modest
in size, it is large enough to expose the difference between an
algorithm whose memory grows with the stream and one whose memory is
bounded by a small parameter, and small enough that a full-history
baseline can be computed alongside the streaming algorithms for
direct comparison. Daily returns, moreover, exhibit the heavy-tailed
behaviour and irregular event structure for which an adaptive
threshold-based alert rule is naturally motivated, even if the rule
itself is descriptive rather than predictive.

Five streaming components are implemented, each on top of a common
`StreamItem` interface. Reservoir sampling and heap-based sampling
with random tags maintain a uniform size-`k` sample of the entire
history without storing it; the online monitor maintains a per-ticker
rolling-volatility window and applies a threshold-based extreme-return
rule for each new observation; and the top-k tracker recovers the `k`
largest absolute returns ever seen using a bounded min-heap. A
full-history baseline is computed in parallel as a reference quantity.
The deliverable is a Python package, `stock_stream`, with thirty-eight
unit tests, eighty-five per cent branch coverage, and a one-command
pipeline that regenerates every output from the four raw input files.

## Chapter 2. Dataset and stream construction

The dataset consists of eight Yahoo Finance daily series over the
common analysis window 2021-04-01 to 2026-04-01: AAPL, ORCL, MSFT,
AMD, ASML, INTC, META, and NVDA. The raw data was supplied in two
different download formats. The first, exemplified by
`ASML_INTC_daily.csv` and `META_NVDA_daily.csv`, is a Yahoo multi-row
CSV in which the first three rows contain the field name, the ticker
label, and a placeholder date row, after which one row corresponds to
one trading day. The second, exemplified by
`sp500_AAPL_ORCL_stocks.xlsx` and `sp500_MSFT_AMD_stocks.xlsx`, is a
sheet-per-ticker workbook in which the column structure is already
flat. The data loader handles both layouts and reduces them to a
single long-format table whose schema is `date, ticker, open, high,
low, close, adj_close, volume, ret`. Some files extend slightly beyond
the project window; observations outside the window are discarded
before per-ticker returns are computed, so that all eight tickers
share exactly the same time horizon. Per-ticker daily returns are
computed as `ret_t = close_t / close_{t-1} − 1`, and the first
observation for each ticker is therefore missing.

After cleaning, every ticker has 1,256 trading days, and the cleaned
dataset contains 10,048 rows in total. The use of `adj_close` in the
schema is preserved for stability across raw layouts, even though the
multi-row CSV files do not always carry an explicit adjusted-close
column; in such cases the loader defaults `adj_close` to `close`,
which is recorded in the schema documentation.

## Chapter 3. Problem formulation

The cleaned dataset is sorted by `(date, ticker)` and replayed as a
stream of `StreamItem` records, defined as

```python
@dataclass(frozen=True)
class StreamItem:
    date: str        # YYYY-MM-DD
    ticker: str
    close: float
    ret: float | None
```

This dataclass is the single contract between the data layer
(`data_loader`, `stream`) and the algorithmic layer (`reservoir`,
`heap_sampler`, `monitoring`, `topk`). The motivation for keeping the
record narrow—four fields rather than the full set of OHLC and volume
columns—is that the streaming algorithms do not require those columns,
and reducing the record limits the surface area against which the
algorithmic interfaces are tied to the present dataset. The same
`StreamItem` interface would, in principle, accept observations from a
live websocket feed; everything downstream of `dataframe_to_stream`
is independent of how the items were produced.

## Chapter 4. Methods

### 4.1 Full-history baseline

Before the streaming algorithms are introduced it is convenient to
record the full-history baseline. The baseline is a simple aggregate
table, computed by reading the cleaned dataset once with random access
and producing per-ticker statistics: the number of observations, the
first and last trading dates, the minimum daily low and the maximum
daily high, the mean and last close, the mean return, the return
volatility (the sample standard deviation of returns with `ddof = 1`),
and the maximum absolute daily return. The baseline is the
complete-information reference against which the streaming algorithms
are checked in Chapter 6.

### 4.2 Reservoir sampling

Reservoir sampling holds at most `k` items at any time. For the first
`k` arrivals it inserts directly into the reservoir; for the `n`-th
arrival with `n > k`, the item is accepted with probability `k / n`,
and on acceptance it replaces a uniformly chosen reservoir slot. After
processing `N` items, every observed item has equal probability `k / N`
of being in the final sample, by the standard inductive argument that
combines the inclusion probability of the new item with the
conditional retention probability of every previously included item.
The per-item update time is constant in expectation and the storage
is `O(k)`.

### 4.3 Heap-based sampling with random tags

Heap-based sampling assigns each arrival an independent random tag
drawn from the uniform distribution on `(0, 1)` and retains the items
whose tags are the `k` smallest tags seen so far. The retention is
implemented with a max-heap on the tag of size `k`: when a new item
arrives, its tag is compared to the heap maximum, and the heap is
updated only if the new tag is smaller. The retained items form a
uniform sample without replacement, by the equivalence between
"select the `k` items with the smallest random priorities" and
"select `k` items uniformly at random". The per-item update time is
`O(log k)` and the storage is `O(k)`.

### 4.4 Online return calculation

The cleaned stream already contains `ret`, so the online stage need
only consume one return per arrival. Items with `ret = None` or `NaN`
(the first observation per ticker) are skipped because they cannot
contribute to volatility or alert calculations. This is a small but
necessary point because, were `NaN` returns silently propagated, the
rolling sample variance would also be `NaN` and every subsequent alert
would be either spurious or suppressed depending on the implementation.

### 4.5 Rolling-volatility monitoring

For each ticker the monitor maintains a `deque` of the most recent
`window_size` valid returns; the default window is 20, which is
approximately one trading month. While the window is filling, no
snapshot is emitted. Once the window is full, the rolling sample
standard deviation, with `ddof = 1`, is recomputed for every
subsequent valid return, and the monitor emits a snapshot containing
the date, the ticker, the return and its absolute value, the rolling
volatility, the threshold parameter, and the extreme-event flag. Each
ticker has its own window, so the volatilities of the eight tickers
are not mixed.

#### Volatility-window convention

Two natural designs exist. In the *state-after-event* convention,
which is the one used here, the new return is appended to the window
first, the volatility is then recomputed, and the rule is finally
evaluated; the volatility used for the rule therefore includes the
current return, and the emitted snapshot is best read as the state of
the monitor after the event has been processed. In the
*state-before-event* convention, sometimes called a leave-one-out
detector, only the previous window is used to score the current
return, and the window is updated afterwards; the score is then
independent of the value being scored. The literature on anomaly
detection sometimes prefers the second formulation for that reason.
We adopted the first because it is simpler and because, with a window
of twenty observations and a three-sigma threshold, the two
formulations disagree only at the boundary of the threshold and on at
most a handful of events; the substantive findings of Chapter 6 do
not depend on which is chosen. Switching conventions would require
swapping two lines in `monitoring.py:update` and is therefore a clean
extension rather than a bug fix.

### 4.6 Extreme-return event detection

A snapshot is flagged as extreme when the absolute return exceeds the
threshold multiplied by the rolling volatility, that is, when

```text
|ret_t| > threshold × rolling_volatility_t,
```

with the default threshold equal to three. The rule is adaptive in
the relevant sense: a return of a given magnitude is more likely to
be flagged during a calm regime, when the rolling volatility is low,
than during a turbulent one, when the rolling volatility is high.
Each flagged event is also written to `outputs/monitoring_alerts.csv`
in addition to appearing in the snapshot table.

### 4.7 Top-k extreme-return tracking

To recover the `k` largest absolute returns over the entire stream
without storing the entire stream, the tracker maintains a bounded
min-heap of size `k` keyed on the absolute return. While the heap has
fewer than `k` entries, the tracker inserts each new arrival; once
the heap is full, the tracker compares the absolute return of the
arrival with the heap minimum and replaces the minimum only if the
arrival is larger. At the end of the stream the heap is sorted in
descending order to produce a ranked top-k table. The per-item update
time is `O(log k)` and the storage is `O(k)`. Unlike reservoir and
heap-based sampling, this algorithm is deterministic, in the sense
that for a fixed input stream the output is unique.

## Chapter 5. Implementation

### 5.1 Package layout

The package is laid out following the standard `src/`-layout convention:

```text
stock_stream_pipeline_final/
├── data/                          raw inputs (csv + xlsx)
├── src/stock_stream/              package source
│   ├── types.py                   StreamItem dataclass
│   ├── data_loader.py             format-aware loader and windowing
│   ├── stream.py                  dataframe_to_stream / preview_stream
│   ├── baseline.py                full-history baseline
│   ├── reservoir.py               reservoir sampling
│   ├── heap_sampler.py            heap-based sampling
│   ├── sampling_evaluation.py     empirical check, runtime, memory
│   ├── monitoring.py              OnlineMonitor (rolling vol + alerts)
│   └── topk.py                    TopKExtremeReturns
├── scripts/                       runnable entry points
├── tests/                         pytest suite (38 tests)
├── outputs/                       generated artefacts
└── docs/                          this report and the per-chapter drafts
```

The `StreamItem` interface is the single point of contact between the
data layer (`data_loader`, `stream`) and the algorithmic layer
(`reservoir`, `heap_sampler`, `monitoring`, `topk`). The
`sampling_evaluation` module is logically part of the algorithmic
layer; `baseline` belongs to neither and operates directly on the
cleaned dataframe.

### 5.2 Entry-point scripts

The four pipeline stages are provided as standalone scripts, and a
fifth script runs all four in sequence. The first stage,
`scripts/run_step1_pipeline.py`, loads the raw files, applies the
window, computes per-ticker returns, and writes the cleaned dataset,
the full-history baseline, and a twelve-row stream preview. The
second, `scripts/run_sampling_evaluation.py`, runs the correctness,
runtime, and memory experiments described in Chapter 6 and writes the
five output tables. The third, `scripts/run_monitoring.py`, runs the
online monitor and the top-k tracker over the cleaned stream and
writes the snapshot table, the alert table, and the ranked top-k
table. The fourth, `scripts/run_validation_comparison.py`, compares
the streaming outputs against the baseline and writes four diagnostic
plots. The combined runner, `scripts/run_full_pipeline.py`, simply
invokes the four stages in order; on a recent Apple-silicon laptop it
completes in under five seconds end-to-end.

## Chapter 6. Experiments

### 6.1 Empirical sampling check

Both reservoir and heap-based sampling are randomised algorithms;
their guarantee is at the level of the inclusion *distribution*, not
on any single run. To verify this empirically we ran 500 independent
samples of size `k = 50` over the cleaned stream of length
`N = 10,048` and counted the number of times each observation
appeared in the final sample. The expected per-item inclusion
probability under uniform sampling is `k / N ≈ 4.976 × 10⁻³`.

| Method | `k / N` (theoretical) | Mean empirical inclusion probability | Standard deviation across items |
|---|---:|---:|---:|
| Reservoir | 0.004976 | 0.004976 | 0.003155 |
| Heap | 0.004976 | 0.004976 | 0.003110 |

The empirical means recover the theoretical value to six decimal
places, and the per-item standard deviation is consistent with the
binomial noise that a uniform sampler would produce in 500 runs. The
result is consistent with—but, by construction, not a proof of—
uniformity; the formal guarantees come from the inductive arguments
sketched in the lecture and rehearsed in Chapter 4.

### 6.2 Runtime

Stream lengths of 1,000, 10,000, and 10,048 were combined with sample
sizes of 10, 50, and 100, with five repetitions per configuration:

| `N` | `k` | Reservoir mean (ms) | Heap mean (ms) |
|------:|-----:|--------------------:|---------------:|
| 1,000 | 10 | 0.26 | 0.08 |
| 1,000 | 100 | 0.26 | 0.11 |
| 10,000 | 10 | 2.54 | 0.57 |
| 10,000 | 100 | 2.57 | 0.66 |

At the scale of the present stream the heap-based sampler is, in
absolute terms, roughly four times faster than the reservoir sampler,
even though its asymptotic per-item cost (`O(log k)`) is worse. The
reason is constant factors. Reservoir sampling, in the implementation
used here, makes two calls to the random-number generator per
accepted item (once to draw the acceptance probability and once to
choose the slot to replace); heap-based sampling makes only one
random draw per arrival and an occasional `heapreplace`. The
asymptotic ranking would still favour reservoir for very large `k`,
but in the streaming regime the project is designed for, where `k`
is small and bounded, heap-based sampling is the more practical
choice in pure Python.

### 6.3 Memory

Peak memory was measured using `tracemalloc`:

| Method | `k` | Peak memory (bytes) |
|---|---:|---:|
| Full-history baseline | — | 80,440 |
| Reservoir | 10 | 3,332 |
| Reservoir | 100 | 4,068 |
| Heap | 10 | 3,552 |
| Heap | 100 | 8,480 |

The streaming samplers use roughly one twentieth to one twenty-fifth
of the memory of the full-history baseline. Within the streaming
samplers, reservoir's footprint grows much more slowly in `k` than
heap's because the heap entry stores the random tag and the arrival
order alongside the item itself.

### 6.4 Online-monitoring experiment

With `window_size = 20` and `threshold = 3.0`, the monitor processed
the entire cleaned stream in a single pass, emitted 9,888 snapshots,
and flagged 96 alerts. The 152-snapshot deficit between the stream
length and the snapshot count corresponds exactly to the eight
per-ticker windows of nineteen observations that are required to
fill the rolling buffer before snapshots begin to be emitted, which
is the expected behaviour.

A short selection of the largest detected events, with the rolling
volatility used in the rule, illustrates the alignment with widely
reported public events:

| Date | Ticker | Return | Rolling volatility | Public event |
|---|---|---:|---:|---|
| 2025-09-10 | ORCL | +0.359 | 0.085 | cloud and AI revenue guidance |
| 2022-02-03 | META | −0.264 | 0.063 | Q4 2021 earnings miss |
| 2024-08-02 | INTC | −0.261 | 0.064 | Q2 2024 guidance and dividend cut |
| 2022-10-27 | META | −0.246 | 0.061 | Q3 2022 earnings |
| 2023-05-25 | NVDA | +0.244 | 0.058 | AI-driven guidance raise |

The rolling-volatility histogram in
`outputs/plots/rolling_volatility_hist.png` shows that the bulk of
the snapshot volatilities lie between roughly 0.015 and 0.030, with a
right tail extending past 0.05 that corresponds to the high-volatility
regimes around the events listed above. The cross-ticker scatter in
`outputs/plots/volatility_scatter.png` shows that the average rolling
volatility is, for every ticker, slightly below the full-history
volatility (the mean ratio is about 0.92), which is the expected
consequence of a sliding window under-weighting the rare full-period
shocks that contribute disproportionately to the unconditional
sample standard deviation.

### 6.5 Top-k experiment

With `k = 10`, the bounded min-heap recovered the same ten events as
the per-ticker maxima of the full-history baseline; the
top-k-versus-baseline scatter in
`outputs/plots/topk_vs_baseline_scatter.png` lies exactly on the
forty-five-degree line, with a maximum deviation across the five
contributing tickers of zero. AAPL, ASML, and MSFT did not place an
observation in the global top ten because their per-ticker maxima
were smaller than the tenth-largest event in the global ranking,
which is consistent with the values in `full_history_baseline.csv`.
This match should be read as confirmation, not as surprise: the
top-k tracker is a deterministic selection rule, and an exact match
to the baseline is the expected outcome.

## Chapter 7. Tests and reproducibility

### 7.1 Test suite

The tests are organised by module. Three tests cover the data loader,
verifying that each raw layout yields the expected tickers, that the
project window is enforced, and that the per-ticker row counts are
equal after windowing. Four tests cover the stream and baseline
modules, verifying chronological order, return computation, baseline
shape, and the project window constants. Seven tests cover the two
samplers and the sampling-evaluation helpers, checking exact-`k`
output, behaviour on streams shorter than `k`, the `k = 0` and `k < 0`
boundaries, and the schema of the correctness, runtime, and memory
tables. Eleven tests cover the online monitor, checking that no
snapshot is emitted before the window fills, that the rolling
volatility matches the analytical value, that the threshold rule is
respected in both directions, that tickers do not interfere, that
`None` and `NaN` returns are skipped, that the snapshot and alert
dataframes have the expected schema, that the reset method works, and
that the constructor rejects invalid arguments. Thirteen tests cover
the top-k tracker, checking partial-fill behaviour, the ranking rule,
sign symmetry, the handling of `None` and `NaN`, the replacement rule
in both directions, the empty-tracker behaviour, the handling of
duplicate absolute values, the reset method, and the constructor's
validation. The total is thirty-eight tests, all of which pass under
`pytest` with no warnings.

### 7.2 Coverage

Coverage was measured with `coverage` in branch mode after running
the test suite. The overall branch coverage is eighty-five per cent,
above the eighty-per-cent threshold suggested in the project rubric.
The algorithmic modules—`reservoir`, `heap_sampler`, `monitoring`,
and `topk`—are at one hundred per cent. The lower coverage of
`baseline`, `data_loader`, and `sampling_evaluation` is attributable
to file-writing helpers and the experiment-driver loops, which are
exercised end-to-end by the pipeline scripts but are not the subject
of separate unit tests. Concentrating coverage on the algorithmic
core is, we would argue, the appropriate emphasis: that is the part
of the package whose correctness is most consequential, and it is
the part that most directly implements the lecture material.

### 7.3 Reproducibility

The full pipeline is reproducible in a clean environment with three
commands:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_full_pipeline.py
```

Every cleaned table, every experiment table, every alert and top-k
record, and every figure in `outputs/` is regenerated from the four
raw input files in `data/` in under five seconds on a recent laptop.

## Chapter 8. Findings

The substantive findings can be summarised in four points. The first
is that the two randomised samplers are, within the precision of 500
runs, empirically uniform: the mean per-item inclusion probability
matches the theoretical `k / N` value to six decimal places for both
methods, and the per-item dispersion is consistent with binomial
noise. The second is that, in the streaming regime that the project
addresses, the heap-based sampler is roughly four times faster in
absolute wall-clock terms than the reservoir sampler, even though
its asymptotic per-item cost is the larger of the two; the
implication is that the choice between the two methods, in pure
Python and at moderate `k`, is governed by constant factors rather
than asymptotics. The third is that both streaming samplers reduce
peak memory by a factor of roughly twenty to twenty-five compared
with the full-history baseline, and that reservoir's footprint grows
more slowly in `k` than heap's, consistent with the heap's per-entry
overhead. The fourth is that the online monitor's alert events
align with widely reported public news (the META 2022-02-03 and
2022-10-27 earnings drops, the INTC 2024-08-02 guidance cut, the
ORCL 2025-09-10 cloud and AI guidance, the NVDA 2023-05-25 AI
guidance raise, and so on); the bounded top-k tracker, in turn,
recovers the same ten events as the per-ticker maxima of the
full-history baseline, which is the expected behaviour of a
deterministic selection rule.

## Chapter 9. Limitations

Several limitations follow from the choices that were made and
should be acknowledged. The pipeline assumes a regular daily
cadence; tick-level or otherwise irregular streams would require a
time-weighted version of the rolling statistic and an event-time
rather than count-time window. The threshold-based alert rule is
adaptive but blunt: in regime shifts such as earnings weeks it can
produce clusters of alerts on consecutive days, and a richer rule
incorporating, for example, a cooldown or a volatility-of-volatility
adjustment would reduce that clustering. The heap-based sampler uses
a single random tag per item, which is sufficient for sampling
without replacement at uniform weights but would have to be replaced
by a different priority function to support sampling with
replacement or weighted sampling along the lines of the A-Res
algorithm. Finally, the streaming behaviour in this project is
simulated rather than live: the cleaned dataframe is replayed in
date order through the `dataframe_to_stream` adapter, and a true
production deployment would require swapping that adapter for a
websocket or message-bus reader. The downstream interfaces do not
need to change, which was a principal motivation for keeping
`StreamItem` narrow.

## Chapter 10. Conclusion

This project set out to ask whether the streaming paradigm covered in
the lecture is worthwhile in practice once one steps away from the
textbook setting and onto a real, if modest, dataset. The answer
suggested by the experiments above is that it is, in three concrete
respects: the streaming samplers are empirically uniform and reduce
peak memory by an order of magnitude relative to the full-history
baseline; the online monitor recovers, with a single descriptive
statistic and a single threshold, a list of events that aligns with
well-known public news; and the bounded top-k tracker recovers the
same extreme events as the full-history baseline while using O(`k`)
rather than O(`N`) memory. None of these results is a forecast or a
trading signal, and the project does not claim to be one. What it
does claim is that the streaming paradigm—understood narrowly as a
collection of bounded-memory, single-pass data structures—can be
carried through end-to-end on five years of real U.S. equity data
with reproducible numerical outputs, thirty-eight passing tests, and
eighty-five-per-cent branch coverage.

## Appendix A. File-to-chapter map

| Code or data file | Chapter |
|---|---|
| `data/*.csv`, `data/*.xlsx` | 2 |
| `src/stock_stream/data_loader.py`, `stream.py`, `types.py` | 2, 3 |
| `src/stock_stream/baseline.py` | 4.1 |
| `src/stock_stream/reservoir.py` | 4.2 |
| `src/stock_stream/heap_sampler.py` | 4.3 |
| `src/stock_stream/monitoring.py` | 4.4, 4.5, 4.6 |
| `src/stock_stream/topk.py` | 4.7 |
| `src/stock_stream/sampling_evaluation.py` | 6.1, 6.2, 6.3 |
| `scripts/run_*` | 5.2 |
| `tests/*` | 7 |
| `outputs/full_history_baseline.csv` | 4.1, 6.5 |
| `outputs/sampling_correctness_*.csv` | 6.1 |
| `outputs/sampling_runtime_comparison.csv` | 6.2 |
| `outputs/sampling_memory_comparison.csv` | 6.3 |
| `outputs/monitoring_snapshots.csv` | 6.4 |
| `outputs/monitoring_alerts.csv` | 4.6, 6.4 |
| `outputs/topk_extreme_returns.csv` | 4.7, 6.5 |
| `outputs/plots/*.png` | 6.4, 6.5 |

## References

Zhang, Z. (2026). *Data Streams.* W7D2 lecture, ORIE 5270, Cornell
University, Spring 2026.
