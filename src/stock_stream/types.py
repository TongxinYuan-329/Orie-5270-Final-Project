"""Shared data types for the streaming stock pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StreamItem:
    """One observation arriving from the stock-price stream."""

    date: str
    ticker: str
    close: float
    ret: float | None
