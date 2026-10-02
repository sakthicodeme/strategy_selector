"""
Market Regime and Volatility Filter (Suggestions for Options Strategy Selection).
Calculates ADX (Trend Strength), ATR% / IV Percentile (Volatility Regime), and Session VWAP.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import numpy as np
import pandas as pd


@dataclass
class RegimeResult:
    adx: float
    trend_strength: str          # "STRONG_TREND", "MODERATE_TREND", "WEAK_RANGE"
    atr_pct: float               # ATR as % of Close price
    volatility_regime: str       # "HIGH_VOLATILITY", "NORMAL_VOLATILITY", "LOW_VOLATILITY"
    vol_percentile: float        # 0.0 to 100.0 percentile rank
    implied_vol_avg: float       # Average IV from options chain (if available)
    vwap: float                  # Volume-Weighted Average Price
    vwap_distance_pct: float     # Deviation from VWAP in %
    summary_reason: str          # Human-readable rationale for options structuring


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Computes Average Directional Index (ADX) over 5m candles.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    if not tr.empty:
        tr.iloc[0] = high.iloc[0] - low.iloc[0]

    tr_smoothed = tr.ewm(alpha=1.0 / period, min_periods=1, adjust=False).mean()
    plus_di = 100.0 * pd.Series(plus_dm, index=df.index).ewm(alpha=1.0 / period, min_periods=1, adjust=False).mean() / (tr_smoothed + 1e-9)
    minus_di = 100.0 * pd.Series(minus_dm, index=df.index).ewm(alpha=1.0 / period, min_periods=1, adjust=False).mean() / (tr_smoothed + 1e-9)

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
    adx = dx.ewm(alpha=1.0 / period, min_periods=1, adjust=False).mean().fillna(15.0)

    return adx


def calculate_market_regime(
    df: pd.DataFrame,
    adx_period: int = 14,
    trend_threshold: float = 22.0,
    vol_high_pct: float = 60.0,
    vol_low_pct: float = 35.0,
    options_tickers: Optional[List[Dict[str, Any]]] = None
) -> RegimeResult:
    """
    Determines whether the market is trending vs ranging, and high-vol vs low-vol.
    This dictates whether to choose Credit vs Debit, Directional vs Delta-Neutral.
    """
    if df.empty or len(df) < adx_period + 2:
        return RegimeResult(
            adx=15.0,
            trend_strength="WEAK_RANGE",
            atr_pct=1.5,
            volatility_regime="NORMAL_VOLATILITY",
            vol_percentile=50.0,
            implied_vol_avg=40.0,
            vwap=float(df["close"].iloc[-1]) if not df.empty else 2750.0,
            vwap_distance_pct=0.0,
            summary_reason="Default neutral baseline"
        )

    data = df.copy()

    # 1. ADX for Trend Strength
    adx_series = calculate_adx(data, period=adx_period)
    curr_adx = float(adx_series.iloc[-1])

    if curr_adx >= 28.0:
        trend_strength = "STRONG_TREND"
    elif curr_adx >= trend_threshold:
        trend_strength = "MODERATE_TREND"
    else:
        trend_strength = "WEAK_RANGE"

    # 2. Volatility Analysis (ATR% and Options IV)
    tr = (data["high"] - data["low"]).rolling(10).mean()
    atr_pct_series = (tr / data["close"]) * 100.0
    curr_atr_pct = float(atr_pct_series.iloc[-1])

    # Compute rolling percentile rank over the candle window
    rolling_ranks = atr_pct_series.rank(pct=True) * 100.0
    vol_percentile = float(rolling_ranks.iloc[-1]) if not rolling_ranks.empty else 50.0

    # Read live IV from options tickers if present
    implied_vols = []
    if options_tickers:
        for opt in options_tickers:
            iv = opt.get("mark_iv") or 0.0
            if iv > 0.05 and iv < 3.0:
                implied_vols.append(iv * 100.0)

    avg_iv = float(np.mean(implied_vols)) if implied_vols else 42.0

    # Classify Volatility Regime
    if vol_percentile >= vol_high_pct or avg_iv >= 55.0:
        volatility_regime = "HIGH_VOLATILITY"
        vol_note = "Elevated volatility favors NET CREDIT (Selling high premium / Theta decay)."
    elif vol_percentile <= vol_low_pct or avg_iv <= 32.0:
        volatility_regime = "LOW_VOLATILITY"
        vol_note = "Compressed volatility favors NET DEBIT (Buying cheap gamma / Breakout leverage)."
    else:
        volatility_regime = "NORMAL_VOLATILITY"
        vol_note = "Moderate volatility allows balanced spreads or delta-defined plays."

    # 3. Session VWAP
    typical_price = (data["high"] + data["low"] + data["close"]) / 3.0
    cum_vol_price = (typical_price * data["volume"]).cumsum()
    cum_vol = data["volume"].cumsum()
    vwap_series = cum_vol_price / (cum_vol + 1e-9)

    curr_close = float(data["close"].iloc[-1])
    curr_vwap = float(vwap_series.iloc[-1])
    vwap_distance_pct = round(((curr_close - curr_vwap) / curr_vwap) * 100.0, 2)

    summary_reason = f"{trend_strength} (ADX: {curr_adx:.1f}) with {volatility_regime} (ATR: {curr_atr_pct:.2f}%, IV: {avg_iv:.1f}%). {vol_note}"

    return RegimeResult(
        adx=round(curr_adx, 2),
        trend_strength=trend_strength,
        atr_pct=round(curr_atr_pct, 2),
        volatility_regime=volatility_regime,
        vol_percentile=round(vol_percentile, 1),
        implied_vol_avg=round(avg_iv, 1),
        vwap=round(curr_vwap, 2),
        vwap_distance_pct=vwap_distance_pct,
        summary_reason=summary_reason
    )
