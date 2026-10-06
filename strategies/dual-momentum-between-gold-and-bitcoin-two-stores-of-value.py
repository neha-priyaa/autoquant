"""Dual Momentum Between Gold and Bitcoin (Two Stores of Value).

Weekly (Wednesday-close) dual-momentum switch: compute the 40-bar
(8-week) close-to-close return of GLD and of the Bitcoin leg (BITO
before IBIT's first quote, IBIT thereafter); hold 100% of the 40-bar
winner only if its 40-bar return is positive, otherwise sit in cash.
Never hold both names.
"""
from __future__ import annotations

import pandas as pd


def signal(data: dict[str, pd.DataFrame], lookback_bars: int = 40,
           weekday: int = 2, **_) -> pd.DataFrame:
    universe = list(data)
    idx = next(iter(data.values())).index

    closes = pd.concat(
        [data[t]["close"].reindex(idx).astype(float) for t in universe],
        axis=1)
    closes.columns = universe

    gld = closes["GLD"]

    # Tradable Bitcoin leg: BITO until IBIT starts printing, IBIT after.
    ibit = closes["IBIT"]
    bito = closes["BITO"]
    btc = ibit.where(ibit.notna(), bito)

    r_gld = gld.pct_change(lookback_bars)
    r_btc = btc.pct_change(lookback_bars)

    # Weekly clock: act on the last bar of each Wed-anchored week.
    wk = pd.Series(idx.to_period("W-WED"), index=idx)
    rebal = (wk != wk.shift(1)).fillna(False)

    pick_gld = (r_gld >= r_btc).where(rebal)
    winner_ret = r_gld.where(pick_gld, r_btc).where(rebal)
    hold = (winner_ret > 0).where(rebal)

    # Hold the decision through the week.
    hold = hold.ffill().fillna(False)
    pick_gld = pick_gld.ffill().fillna(False)

    w_btc = (hold & ~pick_gld).astype(float)
    weights = pd.DataFrame({"GLD": (hold & pick_gld).astype(float),
                            "BITO": w_btc, "IBIT": w_btc}, index=idx)

    # Flat wherever either leg has no tradable quote yet.
    weights = weights.where(gld.notna() & btc.notna(), 0.0)
    return weights.fillna(0.0).astype(float).reindex(columns=universe)