"""pandas_datareader shim — DataReader over the project cache (issue #26).

Supported data_sources: "yahoo" (default), "fred", "stooq" — the sources
catalog.py caches. Anything else raises DataNotAvailable: recorded, never a
live fetch.
"""
from __future__ import annotations

from _aqdata import DataNotAvailable, frame_for  # noqa: F401

__all__ = ["DataNotAvailable", "DataReader"]

SOURCES = ("yahoo", "fred", "stooq")


def DataReader(name, data_source=None, start=None, end=None, **kwargs):
    if isinstance(name, (list, tuple)):
        return {n: DataReader(n, data_source, start, end, **kwargs) for n in name}
    source = data_source or "yahoo"
    if source not in SOURCES:
        raise DataNotAvailable(
            f"data_source {data_source!r} not shimmed (known: {', '.join(SOURCES)})")
    return frame_for(str(name), start, end, source=source)
