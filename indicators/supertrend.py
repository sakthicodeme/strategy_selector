"""
Supertrend Indicator calculation using Wilder's ATR and dynamic band filtering.
Accurate for 5m candlestick intervals.
"""

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class SupertrendResult:
    direction: int                # +1 for Bullish (Green), -1 for Bearish (Red)
    trend_label: str             # "BULLISH" or "BEARISH"
    supertrend_line: float       # Value of the Supertrend support/resistance line
    trailing_stop: float         # Equivalent to the active supertrend level
    distance_pct: float          # Percentage distance of close to supertrend line
    is_flip: bool                # True if a flip occurred on the latest completed candle
    atr: float                   # Current Average True Range
    series: pd.DataFrame         # Complete calculated series


def calculate_supertrend(
    df: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0
) -> SupertrendResult:
    """
    Calculates Supertrend indicator on a dataframe of candles.
    Expects columns: ['open', 'high', 'low', 'close', 'volume'].
    """
    if df.empty or len(df) < period + 2:
        return SupertrendResult(
            direction=1,
            trend_label="BULLISH",
            supertrend_line=0.0,
            trailing_stop=0.0,
            distance_pct=0.0,
            is_flip=False,
            atr=0.0,
            series=pd.DataFrame()
        )

    data = df.copy()

    # True Range calculation
    high = data["high"]
    low = data["low"]
    close_prev = data["close"].shift(1)

    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    # Ensure first bar has valid TR (high - low)
    if not tr.empty:
        tr.iloc[0] = high.iloc[0] - low.iloc[0]

    # Wilder's Smoothing for ATR (matches TradingView Supertrend)
    atr = tr.ewm(alpha=1.0 / period, min_periods=1, adjust=False).mean()
    data["atr"] = atr

    # Basic Upper and Lower Bands
    hl2 = (high + low) / 2.0
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)

    data["basic_upper"] = basic_upper
    data["basic_lower"] = basic_lower

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    supertrend = pd.Series(index=data.index, dtype=float)
    trend = pd.Series(index=data.index, dtype=int)

    # Initialize first valid values
    trend.iloc[0] = 1
    supertrend.iloc[0] = basic_lower.iloc[0]

    for i in range(1, len(data)):
        # Final lower band adjustment
        if basic_lower.iloc[i] > final_lower.iloc[i - 1] or data["close"].iloc[i - 1] < final_lower.iloc[i - 1]:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]

        # Final upper band adjustment
        if basic_upper.iloc[i] < final_upper.iloc[i - 1] or data["close"].iloc[i - 1] > final_upper.iloc[i - 1]:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]

        # Trend direction determination
        prev_trend = trend.iloc[i - 1]
        curr_close = data["close"].iloc[i]

        if prev_trend == 1:
            if curr_close < final_lower.iloc[i]:
                trend.iloc[i] = -1
                supertrend.iloc[i] = final_upper.iloc[i]
            else:
                trend.iloc[i] = 1
                supertrend.iloc[i] = final_lower.iloc[i]
        else:
            if curr_close > final_upper.iloc[i]:
                trend.iloc[i] = 1
                supertrend.iloc[i] = final_lower.iloc[i]
            else:
                trend.iloc[i] = -1
                supertrend.iloc[i] = final_upper.iloc[i]

    data["supertrend"] = supertrend
    data["trend"] = trend

    latest_idx = data.index[-1]
    prev_idx = data.index[-2] if len(data) > 1 else latest_idx

    latest_close = float(data.loc[latest_idx, "close"])
    latest_st = float(data.loc[latest_idx, "supertrend"])
    latest_trend = int(data.loc[latest_idx, "trend"])
    latest_atr = float(data.loc[latest_idx, "atr"])

    prev_trend = int(data.loc[prev_idx, "trend"])
    is_flip = (latest_trend != prev_trend)

    distance_pct = round(((latest_close - latest_st) / latest_close) * 100.0, 2)

    return SupertrendResult(
        direction=latest_trend,
        trend_label="BULLISH" if latest_trend == 1 else "BEARISH",
        supertrend_line=round(latest_st, 2),
        trailing_stop=round(latest_st, 2),
        distance_pct=distance_pct,
        is_flip=is_flip,
        atr=round(latest_atr, 2),
        series=data
    )
