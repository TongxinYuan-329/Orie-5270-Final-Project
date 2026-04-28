# Step 1 Report Draft: Data & Stream Pipeline

## Chapter 2: Dataset and Stream Construction

We use eight daily stock datasets over a common analysis window from 2021-04-01 through 2026-04-01: AAPL, ORCL, MSFT, AMD, ASML, INTC, META, and NVDA. Some raw files contain observations outside this window, but the data loader removes rows before 2021-04-01 and after 2026-04-01 so every ticker uses the same time horizon. The raw Excel files come from Yahoo Finance style historical daily data. Because the files have different layouts, the data loader standardizes them into a single long-format table with columns:

`date`, `ticker`, `open`, `high`, `low`, `close`, `adj_close`, `volume`, `ret`.

The cleaned dataset has one row per stock per trading day. The return column is computed per ticker as:

```text
ret_t = close_t / close_{t-1} - 1
```

The first observation for each ticker has a missing return because there is no previous close.

## Chapter 3: Problem Formulation - Stream Setup

The project treats historical daily stock data as a simulated data stream. After cleaning, rows are sorted by date and ticker. Each row is converted into a `StreamItem`:

```python
StreamItem(date: str, ticker: str, close: float, ret: float | None)
```

This design separates the raw dataset format from downstream streaming algorithms. Reservoir sampling, heap-based sampling, rolling volatility monitoring, and top-k extreme return tracking can all consume the same stream interface.

## Chapter 4.1: Full-History Baseline

Before implementing online algorithms, we compute a full-history baseline using all observations. The baseline table includes:

- number of observations per ticker,
- first and last trading dates,
- minimum daily low,
- maximum daily high,
- average close,
- last close,
- average daily return,
- return volatility,
- maximum absolute daily return.

These metrics give a complete-information benchmark for later streaming algorithms. Sampling methods can be compared against full-history distributions, and online monitoring alerts can be evaluated against full-history extreme-return events.

## Chapter 4.2: Method 1 - Reservoir Sampling

Reservoir sampling maintains a fixed-size sample for a one-pass stream without storing the full history. Let the target sample size be `k`.

Algorithm update logic:

1. For the first `k` items, insert directly into the reservoir.
2. For the `n`-th arriving item (`n > k`), include it with probability `k/n`.
3. If included, choose a uniform random index in `[0, k-1]` and replace that existing reservoir item.

Why this works for streams:

- It needs only one pass over data.
- It never stores more than `k` items.
- Every observed item has equal final inclusion probability `k/N` after `N` items.

Complexity:

- Per-item update time: `O(1)` expected.
- Storage: `O(k)`.

This method is ideal when memory is tight and update throughput is critical.

## Chapter 4.3: Method 2 - Heap-based Sampling with Random Tags

Heap-based sampling assigns each incoming item an independent random tag `u ~ Uniform(0,1)`. We keep the `k` smallest tags using a size-`k` max-heap.

Algorithm update logic:

1. Generate a random tag for each arriving item.
2. If heap size is less than `k`, push `(tag, item)`.
3. If heap is full and new tag is smaller than heap-top (current largest kept tag), replace heap-top.
4. The remaining `k` items are the sample.

Why this is useful:

- Conceptually direct: "keep globally smallest `k` random tags."
- Easy to explain alongside priority-queue material.
- Also produces a uniform sample without replacement.

Complexity:

- Per-item update time: `O(log k)` due to heap operations.
- Storage: `O(k)`.

Compared with reservoir sampling, this method is usually slower but remains memory-efficient.

## Chapter 6.1: Experiment 1 - Sampling Correctness

Goal: verify whether both sampling methods are approximately uniform.

Setup:

- Fix one cleaned stream.
- Choose sample size `k` (default implementation uses `k=50`).
- Repeat each method for many runs (e.g., `500` or `1000`).
- Count how many times each observation is selected.

Expected result:

- Reservoir and heap methods both produce near-uniform selection frequencies.
- Mean empirical selection probability should be close to theoretical `k/N`.

Deliverables:

- Frequency distribution data file:
  - `sampling_correctness_frequencies.csv`
- Summary table:
  - `sampling_correctness_summary.csv`

## Chapter 6.2: Experiment 2 - Runtime Comparison

Goal: compare runtime under different stream lengths and sample sizes.

Recommended settings:

- Stream length `N`: `1,000`, `10,000`, `100,000`
- Sample size `k`: `10`, `50`, `100`
- Repeat each configuration multiple times and report mean/std runtime.

Expected trend:

- Reservoir sampling is generally faster.
- Heap-based sampling slows more as `k` increases due to `O(log k)` update cost.

Deliverable table:

- `sampling_runtime_comparison.csv`

## Chapter 6.3: Experiment 3 - Memory Usage

Goal: compare memory behavior among:

1. Full-history baseline (store all stream items),
2. Reservoir sampling,
3. Heap-based sampling.

Expected trend:

- Full-history baseline memory grows with `N`.
- Reservoir and heap methods grow mainly with `k` and remain bounded relative to stream length.

Deliverable table:

- `sampling_memory_comparison.csv`

## Sampling Output Format (Unified)

Both sampling methods output the same sample structure. For a stream of `StreamItem`, each sampled row is serialized as:

```json
{
  "date": "YYYY-MM-DD",
  "ticker": "AAPL",
  "close": 123.45,
  "ret": 0.0123
}
```

Saved preview file:

- `sampling_sample_preview.json`
