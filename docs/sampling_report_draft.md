# Sampling Report Draft (Member 2)

## Chapter 4.2: Method 1 - Reservoir Sampling

Reservoir sampling is designed for one-pass data streams when only a fixed-size memory budget is available. Let the target sample size be `k`. The algorithm keeps a container (the reservoir) of at most `k` items while scanning the stream from left to right.

For the first `k` observations, each item is inserted directly into the reservoir. For the `n`-th arriving item (`n > k`), the algorithm includes it with probability `k/n`. If the item is selected, one existing reservoir entry is chosen uniformly at random and replaced.

This update rule guarantees that after processing `N` items, each observed item has the same inclusion probability `k/N`. The per-item update cost is `O(1)` in expectation, and memory usage is `O(k)`. These properties make reservoir sampling well-suited for streaming settings with strict memory limits.

Implementation file:

- `src/stock_stream/reservoir.py`

Main function:

- `reservoir_sample(stream, k, seed=None)`

## Chapter 4.3: Method 2 - Heap-based Sampling with Random Tags

Heap-based sampling assigns each stream item an independent random tag from `Uniform(0,1)` and keeps the `k` items with the smallest tags. This can be implemented online with a size-`k` max-heap over tags.

When a new item arrives, a new random tag is generated. If the heap contains fewer than `k` elements, the item is inserted directly. Otherwise, the new tag is compared to the largest tag currently stored (heap top). If the new tag is smaller, the top element is replaced.

At the end of the stream, the retained `k` items form an unbiased sample without replacement, equivalent to selecting the smallest `k` random priorities. The per-item update cost is `O(log k)` due to heap operations, and memory usage is `O(k)`.

Implementation file:

- `src/stock_stream/heap_sampler.py`

Main function:

- `heap_sample(stream, k, seed=None)`

## Chapter 6.1: Experiment 1 - Sampling Correctness

The correctness experiment evaluates whether both methods behave like uniform sampling. A fixed cleaned stream is used, and each algorithm is repeated many times (for example, 500 runs) with different random seeds. For each observation, we count how often it appears in the final sample.

If the sampler is correct, empirical selection frequencies should be close to the theoretical probability `k/N`, where `N` is stream length. Both reservoir and heap-based methods should show approximately uniform inclusion patterns across observations.

Output files:

- `outputs/sampling_correctness_frequencies.csv`
- `outputs/sampling_correctness_summary.csv`

## Chapter 6.2: Experiment 2 - Runtime Comparison

The runtime experiment compares online update speed under different stream lengths and sample sizes. The standard configuration uses stream lengths `N = 1,000`, `10,000`, and `100,000`, and sample sizes `k = 10`, `50`, and `100`. Each configuration is repeated multiple times and reported with mean and standard deviation in milliseconds.

Theoretical expectation: reservoir sampling has lower asymptotic per-item update cost (`O(1)` expected) than heap-based sampling (`O(log k)`). In practice, language-level constant factors can affect measured wall-clock results, so both the theoretical analysis and empirical timing table should be reported.

Output file:

- `outputs/sampling_runtime_comparison.csv`

## Chapter 6.3: Experiment 3 - Memory Usage

The memory experiment compares three approaches:

1. full-history baseline (store all stream items),
2. reservoir sampling,
3. heap-based sampling.

The full-history baseline scales with `N`, while both streaming samplers scale primarily with `k`. This experiment verifies the key streaming property that memory remains bounded as the stream grows, as long as `k` is fixed.

Output file:

- `outputs/sampling_memory_comparison.csv`

## Unified Sampling Output Format

Both methods return sampled stream items in the same schema:

```json
{
  "date": "YYYY-MM-DD",
  "ticker": "AAPL",
  "close": 123.45,
  "ret": 0.0123
}
```

Preview output file:

- `outputs/sampling_sample_preview.json`

## Reproducibility and Entry Point

All sampling experiments are implemented in:

- `src/stock_stream/sampling_evaluation.py`

Entry-point script:

- `scripts/run_sampling_evaluation.py`

Run command:

```bash
python3 scripts/run_sampling_evaluation.py
```

The script reads cleaned data from `outputs/clean_stock_data.csv` and writes all sampling outputs to `outputs/`.
