"""
Cumulative Volume Delta (CVD) indicator and Divergence Detector for ETHUSD 5m.
Calculates aggressive buyer vs seller order flow aggression and absorption patterns.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd


@dataclass
class CVDResult:
    current_cvd: float
    cvd_slope: float             # Rate of change or EMA slope (+1.0 to -1.0 scaled)
    cvd_trend: str              # "RISING" (Accumulation), "FALLING" (Distribution), "FLAT"
    divergence: str             # "BULLISH_DIVERGENCE", "BEARISH_DIVERGENCE", "NONE"
    divergence_desc: str        # Human-readable explanation of divergence
    last_bar_delta: float       # Buy volume minus sell volume on latest 5m bar
    cvd_ema: float              # Smoothed CVD value
    series: pd.DataFrame        # Full calculated DataFrame


def calculate_cvd(
    df: pd.DataFrame,
    lookback: int = 50,
    ema_period: int = 10,
    recent_trades: Optional[List[Dict[str, Any]]] = None
) -> CVDResult:
    """
    Computes bar-by-bar volume delta and cumulative sum (CVD).
    Detects order flow divergences between price and aggressive taker volume.
    """
    if df.empty or len(df) < 5:
        return CVDResult(
            current_cvd=0.0,
            cvd_slope=0.0,
            cvd_trend="FLAT",
            divergence="NONE",
            divergence_desc="Insufficient data",
            last_bar_delta=0.0,
            cvd_ema=0.0,
            series=pd.DataFrame()
        )

    data = df.copy()

    # Intra-bar volume delta estimation
    # High-Low Range
    hl_range = data["high"] - data["low"]
    
    # Delta ratio based on closing position within the bar range
    # When Close == High, ratio is +1.0 (100% buy aggression)
    # When Close == Low, ratio is -1.0 (100% sell aggression)
    # When Close == Midpoint, ratio is 0.0 (Balanced)
    ratio = np.where(
        hl_range > 1e-6,
        (2.0 * data["close"] - data["high"] - data["low"]) / hl_range,
        0.0
    )
    
    bar_delta = data["volume"] * ratio
    data["bar_delta"] = bar_delta

    # If recent micro trades from Delta Exchange are passed, adjust the latest bar
    if recent_trades and len(recent_trades) > 0 and len(data) > 0:
        taker_buys = sum(
            float(t.get("size", 0)) for t in recent_trades
            if t.get("buyer_role") == "taker" or t.get("seller_role") == "maker"
        )
        taker_sells = sum(
            float(t.get("size", 0)) for t in recent_trades
            if t.get("seller_role") == "taker" or t.get("buyer_role") == "maker"
        )
        trade_delta = taker_buys - taker_sells
        # Blend trade delta into the last candle
        last_idx = data.index[-1]
        data.loc[last_idx, "bar_delta"] = 0.5 * data.loc[last_idx, "bar_delta"] + 0.5 * trade_delta

    # Cumulative Volume Delta
    data["cvd"] = data["bar_delta"].cumsum()

    # CVD Smoothing (EMA)
    data["cvd_ema"] = data["cvd"].ewm(span=ema_period, adjust=False).mean()

    # CVD Slope over last 3 bars
    if len(data) >= 4:
        recent_cvd = data["cvd"].iloc[-1]
        past_cvd = data["cvd"].iloc[-4]
        slope_raw = (recent_cvd - past_cvd) / 3.0
        cvd_trend = "RISING" if slope_raw > 0 else ("FALLING" if slope_raw < 0 else "FLAT")
    else:
        slope_raw = 0.0
        cvd_trend = "FLAT"

    # Divergence Analysis across the lookback window (last 20 bars)
    divergence = "NONE"
    divergence_desc = "No divergence detected. CVD order flow confirms price direction."
    
    sub_window = min(20, len(data))
    if sub_window >= 10:
        prices = data["close"].iloc[-sub_window:].values
        cvds = data["cvd"].iloc[-sub_window:].values

        mid = sub_window // 2
        p_first_half_min = np.min(prices[:mid])
        p_second_half_min = np.min(prices[mid:])

        cvd_first_half_min = np.min(cvds[:mid])
        cvd_second_half_min = np.min(cvds[mid:])

        p_first_half_max = np.max(prices[:mid])
        p_second_half_max = np.max(prices[mid:])

        cvd_first_half_max = np.max(cvds[:mid])
        cvd_second_half_max = np.max(cvds[mid:])

        # Bullish Divergence (Absorption): Price makes Lower Low, but CVD makes Higher Low
        if p_second_half_min < p_first_half_min and cvd_second_half_min > cvd_first_half_min:
            divergence = "BULLISH_DIVERGENCE"
            divergence_desc = "Bullish CVD Divergence (Absorption): Price made lower low while CVD made higher low. Takers aggressively buying into dips."

        # Bearish Divergence (Exhaustion): Price makes Higher High, but CVD makes Lower High
        elif p_second_half_max > p_first_half_max and cvd_second_half_max < cvd_first_half_max:
            divergence = "BEARISH_DIVERGENCE"
            divergence_desc = "Bearish CVD Divergence (Exhaustion): Price made higher high while CVD made lower high. Lack of aggressive buying at highs."

    latest_cvd = float(data["cvd"].iloc[-1])
    latest_ema = float(data["cvd_ema"].iloc[-1])
    last_delta = float(data["bar_delta"].iloc[-1])

    return CVDResult(
        current_cvd=round(latest_cvd, 2),
        cvd_slope=round(slope_raw, 2),
        cvd_trend=cvd_trend,
        divergence=divergence,
        divergence_desc=divergence_desc,
        last_bar_delta=round(last_delta, 2),
        cvd_ema=round(latest_ema, 2),
        series=data
    )
