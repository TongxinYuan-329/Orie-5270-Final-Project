"""Top-k tracking utilities for the stock-price stream."""

from __future__ import annotations

import heapq
from typing import Any

import pandas as pd

from stock_stream.types import StreamItem


class TopKExtremeReturns:
    """Track the top-k largest absolute returns using a bounded min-heap."""

    def __init__(self, k: int = 10) -> None:
        if k <= 0:
            raise ValueError("k must be positive")
        self.k = int(k)
        self._heap: list[tuple[float, int, str, str, float]] = []
        self._counter = 0

    def reset(self) -> None:
        """Clear all internal state."""

        self._heap = []
        self._counter = 0

    def update(self, item: StreamItem) -> None:
        """Process one stream item and update the top-k structure."""

        ret = item.ret
        if ret is None:
            return
        if pd.isna(ret):
            return

        ret_f = float(ret)
        abs_ret = abs(ret_f)
        self._counter += 1

        entry = (abs_ret, self._counter, item.date, item.ticker, ret_f)

        if len(self._heap) < self.k:
            heapq.heappush(self._heap, entry)
            return

        if abs_ret > self._heap[0][0]:
            heapq.heapreplace(self._heap, entry)

    def get_topk(self) -> pd.DataFrame:
        """Return the current top-k as a ranked DataFrame."""

        if not self._heap:
            return pd.DataFrame(columns=["rank", "date", "ticker", "ret", "abs_ret"])

        ordered = sorted(self._heap, key=lambda x: (-x[0], x[1]))
        rows: list[dict[str, Any]] = []
        for rank, (abs_ret, _cnt, date, ticker, ret) in enumerate(ordered, start=1):
            rows.append(
                {"rank": rank, "date": date, "ticker": ticker, "ret": ret, "abs_ret": abs_ret}
            )

        return pd.DataFrame(rows, columns=["rank", "date", "ticker", "ret", "abs_ret"])
