"""Cross-sectional 7-day momentum on ten crypto majors: long the top 3 and
short the bottom 3 by trailing close-to-close weekly return, 1/6 of book per
position, rebalanced every 7 daily bars from the start of the sample. Ranks
are refreshed only on rebalance sessions on data available then; the harness
lags weights to next_open, so no shift here. Flat sleeves sit in cash."""
from __future__ import annotations

import numpy as np
import pandas as pd


def signal(data: dict[str, pd.DataFrame], lookback_bars: int = 7,
           top_n: int = 3, bottom_n: int = 3, leg_weight: float = 1.0 / 6.0,
           rebalance_every: int = 7, **_) -> pd.DataFrame:
    universe = list(data)
    idx = next(iter(data.values())).index
    closes = pd.concat(
        [data[t]["close"].reindex(idx).astype(float) for t in universe],
        axis=1, keys=universe)
    closes.columns = universe

    mom = closes.pct_change(lookback_bars)

    # Trade only every `rebalance_every`-th bar from the sample start.
    n = len(idx)
    is_rebal = np.zeros(n, dtype=bool)
    is_rebal[::rebalance_every] = True
    mom_step = mom.where(pd.Series(is_rebal, index=idx))

    # Descending cross-sectional rank; ties broken by ticker order.
    rank = mom_step.rank(ascending=False, method="first", axis=1)
    long_m = (rank >= 1) & (rank <= top_n)
    short_m = (rank >= len(universe) - bottom_n + 1) & rank.notna()

    target = leg_weight * long_m.astype(float) - leg_weight * short_m.astype(float)

    # Hold the basket between rebalances; rebalance-day zeros are real exits.
    weights = target.loc[is_rebal].reindex(idx).ffill().fillna(0.0)

    # No weight before a ticker's first quote (momentum undefined there).
    weights = weights.where(closes.notna(), 0.0)
    return weights.astype(float).reindex(columns=universe)