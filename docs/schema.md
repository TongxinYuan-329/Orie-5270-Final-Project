# Stream Item Schema

This document defines the data contract for Step 1: Data & Stream Pipeline.

## Clean Input Table

The cleaned long-format dataset uses one row per ticker per trading day.

| column | type | description |
| --- | --- | --- |
| `date` | date string (`YYYY-MM-DD`) | Trading date. |
| `ticker` | string | Stock ticker, e.g. `AAPL`, `ORCL`, `MSFT`. |
| `open` | float | Opening price. |
| `high` | float | Highest price during the trading day. |
| `low` | float | Lowest price during the trading day. |
| `close` | float | Closing price used for return calculation. |
| `adj_close` | float | Adjusted close if available. For Yahoo multi-row files without an explicit adjusted close, this is set equal to `close` to preserve a stable schema. |
| `volume` | integer | Daily trading volume. |
| `ret` | float or null | Per-ticker close-to-close daily return: `close_t / close_{t-1} - 1`. The first row for each ticker has `null`. |

## Stream Item

The streaming algorithms consume a smaller item focused on online processing:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class StreamItem:
    date: str
    ticker: str
    close: float
    ret: float | None
```

Example:

```json
{
  "date": "2024-01-03",
  "ticker": "AAPL",
  "close": 184.25,
  "ret": 0.0123
}
```

## Stream Ordering

The stream is ordered by:

1. `date`
2. `ticker`

This ordering simulates market observations arriving one day at a time. All downstream sampling and monitoring components should operate on this interface rather than directly reading raw Excel files.
