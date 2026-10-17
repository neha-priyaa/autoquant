"""fix_yahoo_finance shim — the pre-2019 name of yfinance.

External code that predates the yfinance rename (`import fix_yahoo_finance
as fyf; fyf.download(...)`, `fyf.pdr_override()`) gets the same cache-backed
objects as the yfinance shim. No network, by construction.
"""
from yfinance import DataNotAvailable, Ticker, download, pdr_override  # noqa: F401

__all__ = ["DataNotAvailable", "Ticker", "download", "pdr_override"]
