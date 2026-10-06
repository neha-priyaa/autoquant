"""European country rotation vs sector rotation: monthly top-3 rotation on
trailing 12-month momentum across ten USD-listed iShares global sector ETFs,
equal weight 1/3 each, long only, cash when flat. Ranks are refreshed at each
month-end on data available then; the harness lags weights, so no shift here."""
from __future__ import annotations

import numpy as np
import pandas as pd


def signal(data: dict[str, pd.DataFrame], lookback_bars: int = 252,
           n_holdings: int = 3, **_) -> pd.DataFrame:
    universe = list(data)
    idx = next(iter(data.values())).index
    closes = pd.concat(
        [data[t]["close"].reindex(idx).astype(float) for t in universe],
        axis=1, keys=universe)
    closes.columns = universe

    mom = closes / closes.shift(lookback_bars) - 1.0

    # Rank only on month-end sessions; hold the basket until the next month-end.
    m = pd.Series(idx.to_period("M"), index=idx)
    is_month_end = m != m.shift(-1)
    mom_step = mom.where(is_month_end)

    # Stable descending rank: ties broken by ticker order in the universe.
    rank = mom_step.rank(ascending=False, method="first", axis=1)
    w_step = (rank <= n_holdings).astype(float)
    w_step = w_step.div(n_holdings).where(rank.notna(), 0.0)

    weights = w_step.replace(0.0, np.nan).ffill().fillna(0.0)

    # No weight before a ticker's first quote (momentum undefined there).
    weights = weights.where(closes.notna(), 0.0)
    return weights.astype(float).reindex(columns=universe)