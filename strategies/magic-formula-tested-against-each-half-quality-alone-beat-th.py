"""Magic Formula quality-only leg: at the first trading session of each year
rank the universe on return on capital and hold the top 30 names equal-weighted
until the next annual reselection. Long only, cash when not selected; the
harness lags the weights per column, so no shift here.

Data limitation: the contract supplies OHLCV only -- no fundamentals -- so the
ROIC rank is proxied by trailing `lookback_bars` price return. The
`quality_metric` keyword is accepted for contract parity (roic/roe/roa sweep)
but does not change the ranking, since every fundamentals-based definition
collapses to the same price-only proxy."""
from __future__ import annotations

import pandas as pd


def signal(data: dict[str, pd.DataFrame],
           top_n: int = 30,
           quality_metric: str = "roic_nopat_over_invested_capital",
           lookback_bars: int = 504,
           **_) -> pd.DataFrame:
    universe = list(data)
    idx = next(iter(data.values())).index
    closes = pd.concat(
        [data[t]["close"].reindex(idx).astype(float) for t in universe],
        axis=1, keys=universe)
    closes.columns = universe

    # Price-only proxy for the cross-sectional quality rank.
    quality = closes / closes.shift(lookback_bars) - 1.0

    # Annual anchor: first trading session of each calendar year.
    year = pd.Series(idx.year, index=idx)
    is_anchor = ~year.duplicated()

    # Stable descending rank, ties broken by universe order. Names without
    # enough history (NaN quality) are never picked.
    rank = quality.where(is_anchor).rank(ascending=False, method="first", axis=1)
    w_step = ((rank <= top_n) / top_n).where(rank.notna(), 0.0)

    # Hold the anchor basket until the next anchor; weights lag behind via
    # the harness, so the anchor row itself is the executable target.
    weights = w_step.where(is_anchor).ffill().fillna(0.0)

    # No weight before a ticker's first quote.
    weights = weights.where(closes.notna(), 0.0)
    return weights.astype(float).reindex(columns=universe)