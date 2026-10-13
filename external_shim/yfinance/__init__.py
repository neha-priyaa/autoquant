"""yfinance shim — serves the project price cache (issue #26).

Injected via PYTHONPATH=external_shim so `import yfinance` resolves here in
external code. Supported subset, on evidence from the pilot repos:

    yf.download(ticker | [tickers], start=, end=, ...)  -> DataFrame
        single ticker: flat lowercase ohlcv frame
        list: MultiIndex columns (ticker, field)
    yf.Ticker(sym).history(period=, start=, end=, ...)  -> DataFrame

Everything else (downloaders, search, screener, crawl) raises
DataNotAvailable or AttributeError — loud and recorded, never a live fetch.

Fidelity notes: multi-ticker download is all-or-nothing — any miss raises
DataNotAvailable, unlike real yfinance's NaN-filled columns. MultiIndex
column order is (ticker, field). Meaningful kwargs we cannot honor
(period/interval/actions beyond the defaults) print one warning line to
stderr per ignored value.
"""
from __future__ import annotations

import sys

import pandas as pd
from _aqdata import DataNotAvailable, frame_for  # noqa: F401

__all__ = ["DataNotAvailable", "download", "Ticker"]

FIELDS = ["open", "high", "low", "close", "volume"]


def _warn(where: str, **ignored) -> None:
    """One stderr line per kwarg whose value deviates from the default."""
    for name, value in ignored.items():
        if value is None or value is False:
            continue
        if name == "period" and value == "max":
            continue
        if name == "interval" and value == "1d":
            continue
        print(f"[aq-shim] yf.{where}: ignoring {name}={value!r} — serving "
              f"full cached range", file=sys.stderr)


def _frame(symbol: str, start=None, end=None) -> pd.DataFrame:
    df = frame_for(symbol, start, end)
    cols = [c for c in FIELDS if c in df.columns]
    if not cols:
        raise DataNotAvailable(f"{symbol}: no ohlcv columns in cached data")
    return df[cols]


def download(tickers, start=None, end=None, *, auto_adjust=True,
             progress=False, group_by="column", period=None, interval=None,
             actions=False, **kwargs):
    _warn("download", period=period, interval=interval, actions=actions)
    single = isinstance(tickers, str)
    names = [tickers] if single else list(tickers)
    frames = {t: _frame(t, start, end) for t in names}
    if single:
        return frames[names[0]]
    return pd.concat(frames, axis=1, names=["ticker", "field"])


class Ticker:
    def __init__(self, symbol: str):
        self.symbol = symbol

    def history(self, period="max", interval="1d", start=None, end=None, **kwargs):
        _warn("Ticker.history", period=period, interval=interval)
        return _frame(self.symbol, start, end)
