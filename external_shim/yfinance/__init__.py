"""yfinance shim — serves the project price cache (issue #26).

Injected via PYTHONPATH=external_shim so `import yfinance` resolves here in
external code. Supported subset, on evidence from the pilot repos:

    yf.download(ticker | [tickers], start=, end=, ...)  -> DataFrame
        single ticker: flat lowercase ohlcv frame
        list: MultiIndex columns (ticker, field)
    yf.Ticker(sym).history(period=, start=, end=, ...)  -> DataFrame

Everything else (downloaders, search, screener, crawl) raises
DataNotAvailable or AttributeError — loud and recorded, never a live fetch.
"""
from __future__ import annotations

import pandas as pd
from _aqdata import DataNotAvailable, frame_for  # noqa: F401

__all__ = ["DataNotAvailable", "download", "Ticker"]

FIELDS = ["open", "high", "low", "close", "volume"]


def _frame(symbol: str, start=None, end=None) -> pd.DataFrame:
    df = frame_for(symbol, start, end)
    cols = [c for c in FIELDS if c in df.columns]
    if not cols:
        raise DataNotAvailable(f"{symbol}: no ohlcv columns in cached data")
    return df[cols]


def download(tickers, start=None, end=None, *, auto_adjust=True,
             progress=False, group_by="column", **kwargs):
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
        return _frame(self.symbol, start, end)
