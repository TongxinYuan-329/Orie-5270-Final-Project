"""Reservoir sampling for stream data."""

from __future__ import annotations

import random
from collections.abc import Iterable
from typing import TypeVar

T = TypeVar("T")


def reservoir_sample(stream: Iterable[T], k: int, seed: int | None = None) -> list[T]:
    """Return a uniform size-k sample from a one-pass stream.

    Per-item update time is O(1) in expectation; storage is O(k).
    """

    if k < 0:
        raise ValueError("k must be non-negative")
    if k == 0:
        return []

    rng = random.Random(seed)
    reservoir: list[T] = []

    for n, item in enumerate(stream, start=1):
        if n <= k:
            reservoir.append(item)
            continue

        # Include the n-th item with probability k/n.
        draw = rng.randint(1, n)
        if draw <= k:
            replace_idx = rng.randrange(k)
            reservoir[replace_idx] = item

    return reservoir
