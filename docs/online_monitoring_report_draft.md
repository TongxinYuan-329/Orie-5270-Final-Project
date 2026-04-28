# Online Monitoring Report Draft (Member 3)

## Chapter 4.4: Online Return Calculation

The online monitoring module uses the cleaned stock stream created in the previous pipeline stage. Each row is passed through the stream interface as a `StreamItem` containing `date`, `ticker`, `close`, and `ret`. The daily return is already computed in the cleaned data as:

```text
ret_t = close_t / close_{t-1} - 1
```

In the online monitoring step, the return value is treated as the incoming signal for each new stream observation. Missing returns are skipped because the first observation for each ticker has no previous close and therefore cannot be used for volatility or extreme-return calculations.

Implementation file:

- `src/stock_stream/monitoring.py`
- `src/stock_stream/topk.py`
- `scripts/run_monitoring.py`

Main functions / classes:

- `OnlineMonitor.update(item)` processes one stream item at a time.
- `TopKExtremeReturns.update(item)` updates the top-k extreme-return tracker.
- `run_monitoring()` reads `outputs/clean_stock_data.csv`, processes the stream, and returns monitoring snapshots, alert events, top-k extreme returns, and total processed rows.
- `save_monitoring_outputs()` writes the monitoring output tables to `outputs/`.

Output / deliverable:

- Input file: `outputs/clean_stock_data.csv`
- Output files:
  - `outputs/monitoring_snapshots.csv`
  - `outputs/monitoring_alerts.csv`
  - `outputs/topk_extreme_returns.csv`

## Chapter 4.5: Rolling Volatility Monitoring

Rolling volatility is computed online for each ticker using a fixed-length moving window of recent daily returns. The implemented default window size is `20`, which approximates one trading month. The monitor maintains a separate return window for each ticker so that volatility is not mixed across firms.

For each valid incoming return:

1. The return is appended to the ticker-specific window.
2. No snapshot is returned until that ticker has accumulated `window_size` valid returns.
3. Once the window is full, the rolling sample standard deviation is computed using `ddof=1`.
4. The output snapshot records the date, ticker, return, absolute return, rolling volatility, threshold value, and extreme-event flag.

Implementation file:

- `src/stock_stream/monitoring.py`

Main class:

- `OnlineMonitor(window_size=20, threshold=3.0)`

Main output file:

- `outputs/monitoring_snapshots.csv`

Output columns:

```text
date, ticker, ret, abs_ret, rolling_volatility, threshold, is_extreme
```

The current run produced `9,888` monitoring snapshots. Since the first 19 valid returns for each ticker are used only to fill the rolling window, the snapshot table is slightly smaller than the full cleaned stream.

### Graph: Distribution of Rolling Volatility

![Distribution of rolling volatility](plots/rolling_volatility_hist.png)

Interpretation: Most rolling-volatility values are concentrated around roughly `0.015` to `0.030`, suggesting that typical one-month daily return volatility is relatively moderate for most ticker-date observations. The distribution is right-skewed, with a smaller number of windows above `0.05`. These right-tail windows likely correspond to high-uncertainty periods or firm-specific shocks, making rolling volatility a useful online risk indicator.

### Graph: Per-Ticker Volatility Comparison

![Volatility comparison per ticker](plots/volatility_scatter.png)

Interpretation: The scatter plot compares each ticker's full-history return volatility with its average rolling volatility. The points follow a clear positive relationship, meaning tickers with higher full-history volatility also tend to have higher average online rolling volatility. The rolling-volatility values are generally slightly below the full-history volatility line, which is reasonable because rolling windows smooth local behavior and do not always capture the most extreme full-period shocks at the same time.

## Chapter 4.6: Extreme Return Detection

Extreme return detection is based on the current return relative to the ticker's rolling volatility. A stream observation is flagged as extreme when:

```text
abs(ret_t) > threshold × rolling_volatility_t
```

The default threshold is `3.0`. This means an alert is generated only when the absolute return is more than three times the current rolling volatility. This design makes the alert rule adaptive: a return of the same size is more likely to trigger an alert during calm periods and less likely to trigger an alert during already volatile periods.

Implementation file:

- `src/stock_stream/monitoring.py`

Main class / method:

- `OnlineMonitor.update(item)`
- `OnlineMonitor.get_alerts()`

Main output file:

- `outputs/monitoring_alerts.csv`

Output columns:

```text
date, ticker, ret, abs_ret, rolling_volatility, threshold, is_extreme
```

The current run produced `96` alert events. Example alert events include ORCL on `2021-06-16`, AMD on `2021-06-17`, and INTC on `2021-07-23`. Later high-magnitude alerts include META on `2026-01-29`, MSFT on `2026-01-29`, and AMD on `2026-02-04`.

### Graph: Alert Magnitude Distribution

![Alert magnitude distribution](plots/alert_magnitudes_hist.png)

Interpretation: Most alert events have absolute returns between about `0.04` and `0.16`, while only a few events exceed `0.20`. The long right tail shows that the alert system captures both moderately unusual returns and rare, very large price moves. The largest detected event has an absolute return near `0.36`, indicating that the monitoring procedure successfully identifies severe extreme-return events rather than only routine fluctuations.

## Chapter 4.7: Top-K Extreme Return Tracking

The top-k tracker maintains the largest absolute returns observed so far using a bounded min-heap. Instead of storing all historical returns, the algorithm keeps only the current `k` largest absolute-return events. The default value is `k=10`.

For each incoming stream item:

1. Missing returns are skipped.
2. The absolute return is computed.
3. If the heap has fewer than `k` records, the event is inserted.
4. If the heap is full, the new event replaces the smallest stored event only when its absolute return is larger.
5. At the end, the heap is sorted in descending absolute-return order and returned as a ranked table.

Implementation file:

- `src/stock_stream/topk.py`

Main class / method:

- `TopKExtremeReturns(k=10)`
- `TopKExtremeReturns.update(item)`
- `TopKExtremeReturns.get_topk()`

Main output file:

- `outputs/topk_extreme_returns.csv`

Output columns:

```text
rank, date, ticker, ret, abs_ret
```

The current top-k output contains `10` records. The largest event is ORCL on `2025-09-10`, with an absolute return of about `0.3595`. Other large events include META on `2022-02-03`, INTC on `2024-08-02`, and META on `2022-10-27`.

### Graph: Top-K Extremes vs. Full-History Baseline Maxima

![Top-k extremes vs baseline maxima](plots/topk_vs_baseline_scatter.png)

Interpretation: The points lie almost exactly on the 45-degree comparison line. This indicates that the online top-k tracker recovers the same maximum absolute-return events that appear in the full-history baseline. In other words, the bounded heap approach produces the correct extreme-event ranking while using much less memory than storing the entire stream.

## Chapter 6.4: Online Monitoring Experiment

The monitoring experiment evaluates whether the online monitor can update risk metrics as each new stock observation arrives. The experiment uses the cleaned stream from `outputs/clean_stock_data.csv` and processes observations in date-ticker order.

Experiment setup:

- Input stream: cleaned daily stock observations.
- Rolling window size: `20` valid returns per ticker.
- Extreme-return threshold: `3.0 × rolling volatility`.
- Output granularity: one monitoring snapshot per valid post-window observation.
- Alert rule: `abs_ret > threshold × rolling_volatility`.

Implementation file:

- `scripts/run_monitoring.py`
- `src/stock_stream/monitoring.py`

Entry point:

```bash
python3 scripts/run_monitoring.py
```

Output files:

- `outputs/monitoring_snapshots.csv`: all post-window monitoring observations.
- `outputs/monitoring_alerts.csv`: only observations flagged as extreme.

Main findings:

- The monitor processed the cleaned stream in one pass.
- It produced `9,888` rolling-volatility snapshots.
- It detected `96` extreme-return events.
- The alert output includes both the return magnitude and the rolling volatility used to determine whether the event is unusual.

## Chapter 6.5: Top-K Extreme Return Experiment

The top-k experiment checks whether the online heap tracker can recover the largest absolute-return events without storing the full stream. The result is compared visually against the full-history baseline maximum absolute returns.

Experiment setup:

- Input stream: cleaned daily stock observations.
- Ranking variable: `abs_ret`.
- Heap size: `k=10`.
- Output: ranked top-k absolute-return events.

Implementation file:

- `scripts/run_monitoring.py`
- `src/stock_stream/topk.py`

Output file:

- `outputs/topk_extreme_returns.csv`

Main findings:

- The top-k tracker returned exactly `10` ranked events.
- The largest event is ORCL on `2025-09-10`, with `abs_ret ≈ 0.3595`.
- The top-k vs. baseline scatter plot shows that the online heap tracker matches the full-history maximum-return benchmark.
- This supports the use of a bounded min-heap as a memory-efficient method for online extreme-return tracking.

## Reproducibility and Validation

The monitoring and top-k implementation is validated by the test files:

- `tests/test_monitoring.py`
- `tests/test_topk.py`

The monitoring tests verify:

- no output is produced before a ticker's rolling window is full,
- rolling volatility is computed correctly,
- extreme-return flags are triggered only when the threshold rule is satisfied,
- each ticker has an independent rolling window,
- missing and NaN returns are ignored,
- output DataFrame structures are consistent,
- invalid initialization inputs are rejected.

The top-k tests verify:

- fewer than `k` records are returned when fewer valid observations exist,
- exactly `k` records are returned once enough observations have arrived,
- ranking is based on absolute return in descending order,
- positive and negative returns are treated symmetrically,
- smaller observations are ignored once the heap is full,
- duplicate absolute values are handled consistently,
- invalid `k` values are rejected.

## Final Deliverables for Member 3

Code deliverables:

- `src/stock_stream/monitoring.py`
- `src/stock_stream/topk.py`
- `scripts/run_monitoring.py`
- `scripts/run_validation_comparison.py`
- `tests/test_monitoring.py`
- `tests/test_topk.py`

Data deliverables:

- `outputs/monitoring_snapshots.csv`
- `outputs/monitoring_alerts.csv`
- `outputs/topk_extreme_returns.csv`

Graph deliverables:

- `outputs/plots/rolling_volatility_hist.png`
- `outputs/plots/volatility_scatter.png`
- `outputs/plots/alert_magnitudes_hist.png`
- `outputs/plots/topk_vs_baseline_scatter.png`

Overall conclusion: the online monitoring component successfully updates rolling volatility, detects alert dates / extreme events, and returns a ranked top-k extreme-return table using streaming-compatible data structures. The graph outputs further confirm that the online metrics are consistent with the full-history baseline while requiring less memory than full-history storage.
