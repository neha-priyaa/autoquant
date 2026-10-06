"""All Weather: quarterly ERC across SPY/TLT/IEF/GLD/DBC, levered ex ante to
the trailing vol of a monthly-rebalanced 60/40 SPY/AGG reference, clipped to
[min_gross, max_gross], reset yearly at the January anchor. AGG is reference
data only and is never traded (weight stays 0.0)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _erc_weights(cov3: np.ndarray, iters: int) -> np.ndarray:
    """Long-only equal-risk-contribution weights per date from a (T, N, N)
    covariance tensor via a fixed-point iteration on the risk contributions."""
    n_dates, n_assets, _ = cov3.shape
    w = np.full((n_dates, n_assets), np.nan)
    valid = np.isfinite(cov3).all(axis=(1, 2))
    if not valid.any():
        return w
    c = cov3[valid]
    var = np.einsum("tii->ti", c)
    inv_vol = 1.0 / np.sqrt(np.maximum(var, 1e-18))
    wv = inv_vol / inv_vol.sum(axis=1, keepdims=True)
    for _ in range(iters):
        s = np.einsum("tij,tj->ti", c, wv)          # cov @ w
        rc = wv * s                                  # risk contributions
        target = rc.sum(axis=1, keepdims=True) / c.shape[1]
        wv = wv * target / np.maximum(rc, 1e-18)
        wv = np.maximum(wv, 0.0)
        wv = np.minimum(wv, 1e6)
        wv /= wv.sum(axis=1, keepdims=True)
    w[valid] = wv
    return w


def signal(data: dict[str, pd.DataFrame], lookback_bars: int = 252,
           min_gross: float = 0.5, max_gross: float = 2.0,
           ref_spy_weight: float = 0.60,
           erc_iters: int = 200, **_) -> pd.DataFrame:
    universe = list(data)
    n = len(universe)
    idx = next(iter(data.values())).index
    closes = pd.concat(
        [data[t]["close"].reindex(idx).astype(float) for t in universe],
        axis=1, keys=universe)
    closes.columns = universe

    rets = closes.pct_change()
    cov_df = rets.rolling(lookback_bars).cov()
    cov3 = cov_df.values.reshape(len(idx), n, n)

    w_erc = pd.DataFrame(_erc_weights(cov3, erc_iters), index=idx,
                         columns=universe)
    cov_w = np.einsum("tj,tjk->tk", w_erc.values, cov3)
    book_vol = pd.Series(
        np.sqrt(np.maximum(np.einsum("tk,tk->t", w_erc.values, cov_w), 0.0)),
        index=idx)

    ref = ref_spy_weight * rets["SPY"] + (1.0 - ref_spy_weight) * rets["AGG"]
    ref_vol = ref.rolling(lookback_bars).std() * np.sqrt(lookback_bars)
    gross = (ref_vol / book_vol).clip(min_gross, max_gross)

    # w_erc re-estimates at each quarterly rebalance; gross is reset once per
    # year at the January anchor -- both from data available on that date.
    q = pd.Series(idx.to_period("Q"), index=idx)
    rb = q != q.shift(1)
    yr = pd.Series(idx.year, index=idx)
    jan = yr != yr.shift(1)

    w_step = w_erc.where(rb, np.nan).ffill()
    gross_step = gross.where(jan, np.nan).ffill()
    weights = w_step.mul(gross_step, axis=0)

    weights["AGG"] = 0.0  # reference-only, never traded
    return weights.fillna(0.0).astype(float).reindex(columns=universe)