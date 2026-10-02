"""
Mock data generator for ETHUSD 5m candles and Delta Exchange options chain.
Useful for offline testing, unit tests, and sandboxed environments.
"""

import time
import math
import numpy as np
import pandas as pd
from typing import List, Dict, Any


def generate_mock_candles(
    symbol: str = "ETHUSD",
    resolution: str = "5m",
    count: int = 120,
    regime: str = "bullish",  # 'bullish', 'bearish', 'ranging', 'divergence'
    base_price: float = 2750.0,
) -> pd.DataFrame:
    """
    Generates synthetic 5m OHLCV data with realistic properties and CVD dynamics.
    """
    now = int(time.time())
    step_sec = 300  # 5 minutes in seconds
    timestamps = [now - (count - i) * step_sec for i in range(count)]

    prices = []
    current_price = base_price

    np.random.seed(42)

    # Drift based on chosen regime
    if regime == "bullish":
        drift = 0.0008
    elif regime == "bearish":
        drift = -0.0008
    elif regime == "ranging":
        drift = 0.0
    elif regime == "divergence":
        # Price drifts down slightly while CVD will rise (absorption)
        drift = -0.0004
    else:
        drift = 0.0

    candles = []
    for i, t in enumerate(timestamps):
        noise = np.random.normal(0, 0.002)
        ret = drift + noise
        open_p = current_price
        close_p = open_p * (1 + ret)
        
        # Bias the wick based on regime to simulate authentic order flow delta
        if regime == "bullish":
            high_p = max(open_p, close_p) * (1 + abs(np.random.normal(0, 0.0006)))
            low_p = min(open_p, close_p) * (1 - abs(np.random.normal(0, 0.0018)))
        elif regime == "bearish":
            high_p = max(open_p, close_p) * (1 + abs(np.random.normal(0, 0.0018)))
            low_p = min(open_p, close_p) * (1 - abs(np.random.normal(0, 0.0006)))
        elif regime == "divergence":
            # Early candles: heavy sell. Late candles: aggressive buying on low price
            progress = i / max(1, count - 1)
            high_p = max(open_p, close_p) * (1 + abs(np.random.normal(0, 0.001 + 0.001 * progress)))
            low_p = min(open_p, close_p) * (1 - abs(np.random.normal(0, 0.002 - 0.0015 * progress)))
        else:
            high_p = max(open_p, close_p) * (1 + abs(np.random.normal(0, 0.0015)))
            low_p = min(open_p, close_p) * (1 - abs(np.random.normal(0, 0.0015)))

        vol = float(np.random.uniform(500, 4000))

        candles.append({
            "time": t,
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": round(vol, 2)
        })
        current_price = close_p

    df = pd.DataFrame(candles)
    return df


def generate_mock_option_tickers(spot_price: float = 2750.0) -> List[Dict[str, Any]]:
    """
    Generates synthetic Delta Exchange option tickers around spot_price.
    Strikes spaced at $50 intervals, matching Delta Exchange schema.
    """
    today_str = time.strftime("%d%m%y")
    atm_strike = int(round(spot_price / 50.0) * 50)
    strikes = [atm_strike + i * 50 for i in range(-8, 9)]

    options = []
    r = 0.05  # risk free rate
    t = 1.0 / 365.0  # 1 day to expiry
    sigma = 0.40  # 40% IV

    for strike in strikes:
        moneyness = math.log(spot_price / strike)
        d1 = (moneyness + (r + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)

        # Standard normal cdf approximation
        def norm_cdf(x):
            return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

        # Normal pdf
        def norm_pdf(x):
            return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

        nd1 = norm_cdf(d1)
        nd2 = norm_cdf(d2)

        # Call price & Greeks
        call_price = max(0.5, spot_price * nd1 - strike * math.exp(-r * t) * nd2)
        call_delta = nd1
        call_gamma = norm_pdf(d1) / (spot_price * sigma * math.sqrt(t))
        call_vega = (spot_price * norm_pdf(d1) * math.sqrt(t)) / 100.0
        call_theta = (-(spot_price * norm_pdf(d1) * sigma) / (2 * math.sqrt(t)) - r * strike * math.exp(-r * t) * nd2) / 365.0

        # Put price & Greeks
        put_price = max(0.5, strike * math.exp(-r * t) * norm_cdf(-d2) - spot_price * norm_cdf(-d1))
        put_delta = nd1 - 1.0
        put_gamma = call_gamma
        put_vega = call_vega
        put_theta = (-(spot_price * norm_pdf(d1) * sigma) / (2 * math.sqrt(t)) + r * strike * math.exp(-r * t) * norm_cdf(-d2)) / 365.0

        # Call option object
        call_symbol = f"C-ETH-{strike}-{today_str}"
        c_mark = round(call_price, 2)
        c_bid = max(0.1, round(c_mark * 0.98, 2))
        c_ask = round(c_mark * 1.02, 2)

        options.append({
            "symbol": call_symbol,
            "strike_price": strike,
            "contract_type": "call_options",
            "mark_price": c_mark,
            "mark_vol": round(sigma, 4),
            "quotes": {
                "best_bid": str(c_bid),
                "best_ask": str(c_ask),
                "bid_iv": str(round(sigma * 0.98, 4)),
                "ask_iv": str(round(sigma * 1.02, 4)),
                "mark_iv": str(round(sigma, 4)),
            },
            "greeks": {
                "delta": str(round(call_delta, 4)),
                "gamma": str(round(call_gamma, 6)),
                "theta": str(round(call_theta, 4)),
                "vega": str(round(call_vega, 4)),
                "spot": str(round(spot_price, 2)),
            },
            "open_interest": 1500,
            "volume": 280
        })

        # Put option object
        put_symbol = f"P-ETH-{strike}-{today_str}"
        p_mark = round(put_price, 2)
        p_bid = max(0.1, round(p_mark * 0.98, 2))
        p_ask = round(p_mark * 1.02, 2)

        options.append({
            "symbol": put_symbol,
            "strike_price": strike,
            "contract_type": "put_options",
            "mark_price": p_mark,
            "mark_vol": round(sigma, 4),
            "quotes": {
                "best_bid": str(p_bid),
                "best_ask": str(p_ask),
                "bid_iv": str(round(sigma * 0.98, 4)),
                "ask_iv": str(round(sigma * 1.02, 4)),
                "mark_iv": str(round(sigma, 4)),
            },
            "greeks": {
                "delta": str(round(put_delta, 4)),
                "gamma": str(round(put_gamma, 6)),
                "theta": str(round(put_theta, 4)),
                "vega": str(round(put_vega, 4)),
                "spot": str(round(spot_price, 2)),
            },
            "open_interest": 1200,
            "volume": 240
        })

    return options
