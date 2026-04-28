"""Online monitoring utilities for the stock-price stream.

This module provides an online (one-pass) monitor that computes per-ticker
rolling volatility and flags extreme returns.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

import numpy as np
import pandas as pd

from stock_stream.types import StreamItem

SNAPSHOT_COLUMNS = [
    "date",
    "ticker",
    "ret",
    "abs_ret",
    "rolling_volatility",
    "threshold",
    "is_extreme",
]


class OnlineMonitor:
    """Online monitor for rolling volatility and extreme return alerts."""

    def __init__(self, window_size: int = 20, threshold: float = 3.0) -> None:
        if window_size < 2:
            raise ValueError("window_size must be at least 2")
        if threshold <= 0:
            raise ValueError("threshold must be positive")

        self.window_size = int(window_size)
        self.threshold = float(threshold)

        self._windows: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.window_size)
        )
        self._snapshots: list[dict[str, Any]] = []
        self._alerts: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Clear all internal state."""

        self._windows = defaultdict(lambda: deque(maxlen=self.window_size))
        self._snapshots = []
        self._alerts = []

    def update(self, item: StreamItem) -> dict[str, Any] | None:
        """Process one stream item and optionally return a monitoring snapshot.

        Returns ``None`` until a ticker has accumulated ``window_size`` valid
        returns. Once available, a snapshot is produced for every subsequent
        valid return.
        """

        ret = item.ret
        if ret is None:
            return None
        if pd.isna(ret):
            return None

        ret_f = float(ret)
        window = self._windows[item.ticker]
        window.append(ret_f)

        if len(window) < self.window_size:
            return None

        values = np.fromiter(window, dtype=float, count=len(window))
        rolling_vol = float(np.std(values, ddof=1))

        is_valid_vol = (not np.isnan(rolling_vol)) and rolling_vol > 0.0
        abs_ret = abs(ret_f)
        is_extreme = bool(is_valid_vol and (abs_ret > (self.threshold * rolling_vol)))

        snapshot: dict[str, Any] = {
            "date": item.date,
            "ticker": item.ticker,
            "ret": ret_f,
            "abs_ret": abs_ret,
            "rolling_volatility": rolling_vol,
            "threshold": self.threshold,
            "is_extreme": is_extreme,
        }

        self._snapshots.append(snapshot)
        if is_extreme:
            self._alerts.append(snapshot)

        return snapshot

    def get_snapshots(self) -> pd.DataFrame:
        """Return all monitoring snapshots as a DataFrame."""

        if not self._snapshots:
            return pd.DataFrame(columns=SNAPSHOT_COLUMNS)
        return pd.DataFrame(self._snapshots)

    def get_alerts(self) -> pd.DataFrame:
        """Return only extreme snapshots as a DataFrame."""

        if not self._alerts:
            return pd.DataFrame(columns=SNAPSHOT_COLUMNS)
        return pd.DataFrame(self._alerts)
