"""Tests for the external_shim packages. The shims are loaded by putting
external_shim/ first on sys.path (exactly how run_external.py injects them),
so 'import yfinance' resolves to the shim, not the real package."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
SHIM = str(ROOT / "external_shim")

Prices = pd.DataFrame(
    {"open": [1.0, 2.0], "high": [1.5, 2.5], "low": [0.5, 1.5],
     "close": [1.2, 2.2], "volume": [100, 200]},
    index=pd.DatetimeIndex(["2020-01-02", "2020-01-03"]))


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    prices = tmp_path / "data" / "prices"
    prices.mkdir(parents=True)
    Prices.to_csv(prices / "AAPL.csv")
    cat = tmp_path / "data" / "catalog"
    cat.mkdir(parents=True)
    pd.DataFrame({"close": [3.0, 3.1]},
                 index=pd.DatetimeIndex(["2020-01-02", "2020-01-03"])
                 ).to_csv(cat / "fred_DGS10.csv")
    monkeypatch.setenv("AUTOQUANT_DATA_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def shims(data_root):
    """Import the shim packages fresh, with external_shim/ front of sys.path."""
    saved_path = sys.path[:]
    saved_mods = {k: sys.modules.pop(k) for k in
                  ("yfinance", "pandas_datareader", "_aqdata") if k in sys.modules}
    sys.path.insert(0, SHIM)
    import yfinance
    import pandas_datareader
    import _aqdata
    yield {"yfinance": yfinance, "pandas_datareader": pandas_datareader,
           "_aqdata": _aqdata}
    sys.path[:] = saved_path
    for k in ("yfinance", "pandas_datareader", "_aqdata"):
        sys.modules.pop(k, None)
    sys.modules.update(saved_mods)


class TestDataNotAvailable:
    def test_unknown_symbol(self, shims):
        with pytest.raises(shims["_aqdata"].DataNotAvailable):
            shims["_aqdata"].frame_for("MSFT")

    def test_unset_data_root(self, monkeypatch, shims):
        monkeypatch.delenv("AUTOQUANT_DATA_ROOT")
        with pytest.raises(shims["_aqdata"].DataNotAvailable):
            shims["_aqdata"].frame_for("AAPL")

    def test_range_miss(self, shims):
        with pytest.raises(shims["_aqdata"].DataNotAvailable):
            shims["_aqdata"].frame_for("AAPL", "2025-01-01", "2025-12-31")


class TestYFinance:
    def test_download_single(self, shims):
        df = shims["yfinance"].download("AAPL", start="2020-01-01")
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 2

    def test_download_multi_returns_multiindex(self, shims, data_root):
        Prices.to_csv(data_root / "data" / "prices" / "MSFT.csv")
        panel = shims["yfinance"].download(["AAPL", "MSFT"])
        assert isinstance(panel.columns, pd.MultiIndex)
        assert set(panel.columns.get_level_values(0)) == {"AAPL", "MSFT"}

    def test_download_miss_raises_clean(self, shims):
        with pytest.raises(shims["_aqdata"].DataNotAvailable):
            shims["yfinance"].download("ZZZZZ")

    def test_ticker_history(self, shims):
        df = shims["yfinance"].Ticker("AAPL").history(start="2020-01-01",
                                                      end="2020-01-31")
        assert len(df) == 2
        assert "close" in df.columns
