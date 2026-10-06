"""Dual Momentum for a Collapsing Currency: weekly dual-momentum rotation over
a twelve-asset Turkish-saver universe. Dollar-ETF closes are converted to
nominal TL via USDTRY when that series is supplied; BIST-100 and the TL deposit
series are TL-native. Per lookback (10w, 25w): rank by TL momentum, take the
top 3, drop any asset failing the absolute filter (its own lookback momentum
<= 0), and reassign each failed slot to whichever of the TL deposit fallback
or the dollar safe asset has the higher fallback-lookback momentum. Sleeve
weight 1/3 per slot; final weights blend the two sleeves 50/50 (1/6 per slot).
Weekly rebalance, long-only, gross <= 1."""
from __future__ import annotations

import numpy as np
import pandas as pd

_TL_NATIVE = ("BIST100_TR", "TL_DEPOSIT_1M")


def _sleeve(mom: pd.DataFrame, fb_mom: pd.DataFrame, tickers: list[str],
            top_n: int, fb_tl: str, fb_usd: str) -> pd.DataFrame:
    """One lookback sleeve: top-N by momentum with absolute filter, failed
    slots reassigned to the deposits-or-dollars fallback. Returns weekly
    weights (1/top_n per slot, gross <= 1)."""
    rank = mom.rank(axis=1, ascending=False)
    picked = (rank <= top_n) & (mom > 0)          # NaN momentum -> not picked
    n_fail = top_n - picked.sum(axis=1)

    fb_tl_m = fb_mom[fb_tl]
    fb_usd_m = fb_mom[fb_usd]
    both_nan = fb_tl_m.isna() & fb_usd_m.isna()   # no fallback history -> cash
    use_tl = fb_tl_m.fillna(-np.inf) >= fb_usd_m.fillna(-np.inf)

    w = picked.astype(float).div(top_n, axis=0)
    fb_share = n_fail / top_n
    w[fb_tl] = w[fb_tl].add(fb_share.where(use_tl & ~both_nan, 0.0),
                            fill_value=0.0)
    w[fb_usd] = w[fb_usd].add(fb_share.where(~use_tl & ~both_nan, 0.0),
                              fill_value=0.0)
    return w.reindex(columns=tickers).fillna(0.0)


def signal(data: dict[str, pd.DataFrame],
           lookback_weeks: tuple[int, int] = (10, 25),
           top_n: int = 3,
           blend: tuple[float, float] = (0.5, 0.5),
           fallback_tl: str = "TL_DEPOSIT_1M",
           fallback_usd: str = "SHY",
           fallback_weeks: int = 10,
           usdtry_ticker: str | None = None,
           **_) -> pd.DataFrame:
    universe = list(data)
    idx = next(iter(data.values())).index
    closes = pd.DataFrame(
        {t: data[t]["close"].reindex(idx).astype(float) for t in universe})

    # Dollar-side assets expressed in nominal TL via USDTRY when available;
    # TL-native series (BIST index, TL deposits) pass through unchanged.
    px_tl = closes.copy()
    if usdtry_ticker is not None and usdtry_ticker in data:
        usdtry = data[usdtry_ticker]["close"].reindex(idx).astype(float)
        for t in universe:
            if t not in _TL_NATIVE:
                px_tl[t] = closes[t] * usdtry

    wk = px_tl.resample("W-FRI").last()
    moms = {w: wk.pct_change(w, fill_method=None) for w in lookback_weeks}
    fb_mom = wk.pct_change(fallback_weeks, fill_method=None)

    sleeves = [_sleeve(moms[w], fb_mom, universe, top_n, fallback_tl,
                       fallback_usd) for w in lookback_weeks]
    w_weekly = sum(b * s for b, s in zip(blend, sleeves))

    # Weekly decision held across the week; the harness lags per column.
    return (w_weekly.reindex(idx).ffill().fillna(0.0)
            .astype(float).reindex(columns=universe))