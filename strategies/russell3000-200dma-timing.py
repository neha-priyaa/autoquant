"""^RUA 200-day moving-average timing (spec: spy-200dma-timing).

Weight 1.0 while ^RUA's close is above its N-day simple moving average,
0.0 (cash) otherwise. The harness lags the signal and applies costs —
nothing is shifted here. Vectorised; cash earns 0.
"""
from __future__ import annotations

import pandas as pd


def signal(df: pd.DataFrame, lookback_bars: int = 200) -> pd.Series:
    sma = df["close"].rolling(int(lookback_bars)).mean()
    return (df["close"] > sma).astype(float)
