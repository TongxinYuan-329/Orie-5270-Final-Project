from __future__ import annotations

import pytest

from stock_stream.heap_sampler import heap_sample
from stock_stream.reservoir import reservoir_sample
from stock_stream.sampling_evaluation import (
    run_correctness_experiment,
    run_memory_experiment,
    run_runtime_experiment,
)


def test_reservoir_returns_exact_k_when_stream_long_enough() -> None:
    stream = list(range(200))
    sample = reservoir_sample(stream, 10, seed=7)
    assert len(sample) == 10
    assert all(item in stream for item in sample)


def test_heap_returns_exact_k_when_stream_long_enough() -> None:
    stream = list(range(200))
    sample = heap_sample(stream, 10, seed=7)
    assert len(sample) == 10
    assert all(item in stream for item in sample)


def test_two_methods_handle_short_stream() -> None:
    stream = [1, 2, 3]
    assert len(reservoir_sample(stream, 10, seed=1)) == 3
    assert len(heap_sample(stream, 10, seed=1)) == 3


def test_zero_k_returns_empty() -> None:
    assert reservoir_sample([1, 2, 3], 0) == []
    assert heap_sample([1, 2, 3], 0) == []


def test_negative_k_raises() -> None:
    with pytest.raises(ValueError):
        reservoir_sample([1, 2, 3], -1)
    with pytest.raises(ValueError):
        heap_sample([1, 2, 3], -1)


def test_correctness_summary_shape() -> None:
    stream = list(range(50))
    freq, summary = run_correctness_experiment(stream_items=stream, k=5, runs=200)
    assert set(summary["method"]) == {"reservoir", "heap"}
    assert len(freq) == len(stream) * 2


def test_runtime_and_memory_experiments_return_expected_columns() -> None:
    stream = list(range(2000))
    runtime_df = run_runtime_experiment(stream, n_values=[1000], k_values=[10], repeats=2)
    memory_df = run_memory_experiment(stream, k_values=[10])

    assert {"method", "stream_length_n", "k", "runtime_ms_mean"}.issubset(runtime_df.columns)
    assert {"method", "n", "k", "peak_memory_bytes"}.issubset(memory_df.columns)
    assert (memory_df["peak_memory_bytes"] > 0).all()
