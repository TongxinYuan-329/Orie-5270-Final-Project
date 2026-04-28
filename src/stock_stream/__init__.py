"""Streaming sampling and event monitoring for financial time series."""

from stock_stream.baseline import full_history_baseline
from stock_stream.heap_sampler import heap_sample
from stock_stream.monitoring import OnlineMonitor
from stock_stream.reservoir import reservoir_sample
from stock_stream.stream import dataframe_to_stream, preview_stream
from stock_stream.topk import TopKExtremeReturns
from stock_stream.types import StreamItem

__all__ = [
    "StreamItem",
    "dataframe_to_stream",
    "preview_stream",
    "full_history_baseline",
    "reservoir_sample",
    "heap_sample",
    "OnlineMonitor",
    "TopKExtremeReturns",
]
