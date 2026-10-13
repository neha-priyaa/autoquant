"""Shared cache-serving code for the yfinance / pandas_datareader shims.

Deliberately self-contained: it runs inside external repos' venvs where only
pandas is guaranteed — no project imports. The served data root comes from
AUTOQUANT_DATA_ROOT (set by run_external.py):

    <root>/data/prices/<SYMBOL>.csv       legacy per-ticker cache
    <root>/data/catalog/<source>_<id>.csv catalog cache (catalog.py)

Prefetching happens in the parent harness (run_external.py warms
catalog.load for the triaged symbols); this shim only serves what is on
disk and raises DataNotAvailable on a miss — a recorded, actionable verdict
rather than a hang or a live fetch.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


class DataNotAvailable(Exception):
    """Requested symbol/date-range is not in our cache."""


def data_root() -> Path:
    root = os.environ.get("AUTOQUANT_DATA_ROOT")
    if not root:
        raise DataNotAvailable(
            "AUTOQUANT_DATA_ROOT is not set -- the shim only serves a "
            "configured data root")
    return Path(root)


def _candidates(symbol: str, source: str) -> list[Path]:
    root = data_root()
    safe = symbol.replace("/", "_")
    out = [root / "data" / "prices" / f"{safe}.csv"]
    if source != "yahoo":
        out.insert(0, root / "data" / "catalog" / f"{source}_{safe}.csv")
    else:
        out.append(root / "data" / "catalog" / f"yahoo_{safe}.csv")
    return out


def frame_for(symbol: str, start=None, end=None, source: str = "yahoo") -> pd.DataFrame:
    """Normalized frame: lowercase columns, ascending DatetimeIndex (naive),
    filtered to [start, end]. Non-empty after filtering, else DataNotAvailable."""
    for path in _candidates(symbol, source):
        if not path.exists():
            continue
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.columns = [str(c).lower() for c in df.columns]
        df.index = pd.to_datetime(df.index)
        try:
            df.index = df.index.tz_localize(None)
        except (TypeError, AttributeError):
            pass
        df = df.sort_index()
        if start:
            df = df[df.index >= pd.Timestamp(start)]
        if end:
            df = df[df.index <= pd.Timestamp(end)]
        if df.empty:
            raise DataNotAvailable(
                f"{symbol}: cached data does not cover [{start}, {end}]")
        return df
    raise DataNotAvailable(
        f"{symbol}: not in the price cache -- the harness pre-fetches triaged "
        f"symbols; add it to the cache and re-run")
