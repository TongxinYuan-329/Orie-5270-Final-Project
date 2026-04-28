"""Heap-based stream sampling using random tags."""

from __future__ import annotations

import heapq
import random
from collections.abc import Iterable
from typing import TypeVar

T = TypeVar("T")


def heap_sample(stream: Iterable[T], k: int, seed: int | None = None) -> list[T]:
    """Return a size-k sample by keeping the k smallest random tags.

    Per-item update time is O(log k); storage is O(k).
    """

    if k < 0:
        raise ValueError("k must be non-negative")
    if k == 0:
        return []

    rng = random.Random(seed)
    # Store (-tag, order, item) to emulate a max-heap on tag.
    heap: list[tuple[float, int, T]] = []

    for order, item in enumerate(stream):
        tag = rng.random()
        if len(heap) < k:
            heapq.heappush(heap, (-tag, order, item))
            continue

        largest_tag = -heap[0][0]
        if tag < largest_tag:
            heapq.heapreplace(heap, (-tag, order, item))

    # Keep output deterministic by original stream arrival order.
    return [entry[2] for entry in sorted(heap, key=lambda x: x[1])]
