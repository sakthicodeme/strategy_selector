"""
Delta Exchange API Client for market data, 5m candles, and options tickers.
Supports Delta India (api.india.delta.exchange) and Delta Global (api.delta.exchange).
"""

import time
import logging
import requests
import pandas as pd
from typing import List, Dict, Any, Optional

from config import config
from data.mock_data import generate_mock_candles, generate_mock_option_tickers

logger = logging.getLogger(__name__)


class DeltaClient:
    def __init__(self, base_url: Optional[str] = None, timeout: int = 10):
        self.base_url = (base_url or config.DELTA_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DeltaOptionStrategySelector/1.0",
            "Accept": "application/json"
        })

    def get_candles(
        self,
        symbol: str = "ETHUSD",
        resolution: str = "5m",
        limit: int = 120
    ) -> pd.DataFrame:
        """
        Fetch historical candles from Delta Exchange.
        Resolution can be '1m', '5m', '15m', '1h', etc.
        """
        now = int(time.time())
        # resolution 5m = 300 seconds
        res_seconds = 300 if resolution == "5m" else 60
        start = now - (limit * res_seconds)

        url = f"{self.base_url}/v2/history/candles"
        params = {
            "symbol": symbol,
            "resolution": resolution,
            "start": start,
            "end": now
        }

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                raw_candles = data.get("result", [])
                if raw_candles:
                    df = pd.DataFrame(raw_candles)
                    # Ensure numeric types
                    for col in ["open", "high", "low", "close", "volume"]:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors="coerce")
                    # Sort chronological (oldest to newest)
                    df = df.sort_values("time").reset_index(drop=True)
                    return df
            logger.warning(f"Failed to fetch candles from {url}: status={resp.status_code}, response={resp.text[:150]}")
        except Exception as e:
            logger.warning(f"Network error accessing Delta Exchange API ({self.base_url}): {e}")

        if config.USE_MOCK_FALLBACK:
            logger.info("Using synthetic fallback 5m candles for ETHUSD.")
            return generate_mock_candles(symbol=symbol, resolution=resolution, count=limit)
        
        return pd.DataFrame()

    def get_spot_or_mark_ticker(self, symbol: str = "ETHUSD") -> Dict[str, Any]:
        """
        Fetch underlying ticker for ETHUSD to retrieve live mark price and spot price.
        """
        url = f"{self.base_url}/v2/tickers/{symbol}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                result = data.get("result", {})
                if result:
                    return {
                        "symbol": symbol,
                        "mark_price": float(result.get("mark_price", 0.0) or 0.0),
                        "spot_price": float(result.get("spot_price", 0.0) or result.get("mark_price", 0.0) or 0.0),
                        "close": float(result.get("close", 0.0) or 0.0),
                        "high_24h": float(result.get("mark_high_24h", 0.0) or 0.0),
                        "low_24h": float(result.get("mark_low_24h", 0.0) or 0.0),
                        "volume_24h": float(result.get("volume", 0.0) or 0.0),
                    }
        except Exception as e:
            logger.warning(f"Could not fetch ticker for {symbol}: {e}")

        # Fallback
        return {
            "symbol": symbol,
            "mark_price": 2750.0,
            "spot_price": 2750.0,
            "close": 2750.0,
            "high_24h": 2800.0,
            "low_24h": 2700.0,
            "volume_24h": 50000.0,
        }

    def get_option_tickers(self, underlying: str = "ETH") -> List[Dict[str, Any]]:
        """
        Fetch all active options for underlying asset (e.g. ETH).
        Parses Greeks, strike prices, quotes, and contract types.
        """
        url = f"{self.base_url}/v2/tickers"
        params = {
            "contract_types": "call_options,put_options"
        }

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("result", [])
                eth_options = []
                for item in results:
                    symbol = item.get("symbol", "")
                    if underlying in symbol:
                        quotes = item.get("quotes") or {}
                        greeks = item.get("greeks") or {}

                        # Best bid and ask parsing
                        best_bid = quotes.get("best_bid") or item.get("best_bid")
                        best_ask = quotes.get("best_ask") or item.get("best_ask")
                        mark_price = item.get("mark_price")
                        mark_iv = quotes.get("mark_iv") or item.get("mark_vol")

                        parsed = {
                            "symbol": symbol,
                            "strike_price": float(item.get("strike_price", 0.0) or 0.0),
                            "contract_type": item.get("contract_type"),  # 'call_options' or 'put_options'
                            "best_bid": float(best_bid) if best_bid is not None else None,
                            "best_ask": float(best_ask) if best_ask is not None else None,
                            "mark_price": float(mark_price) if mark_price is not None else 0.0,
                            "mark_iv": float(mark_iv) if mark_iv is not None else 0.0,
                            "greeks": {
                                "delta": float(greeks.get("delta", 0.0) or 0.0),
                                "gamma": float(greeks.get("gamma", 0.0) or 0.0),
                                "theta": float(greeks.get("theta", 0.0) or 0.0),
                                "vega": float(greeks.get("vega", 0.0) or 0.0),
                            },
                            "open_interest": float(item.get("oi") or item.get("oi_contracts") or 0.0),
                            "volume": float(item.get("volume", 0.0) or 0.0)
                        }
                        eth_options.append(parsed)

                if eth_options:
                    return eth_options
        except Exception as e:
            logger.warning(f"Could not fetch options tickers from Delta Exchange: {e}")

        if config.USE_MOCK_FALLBACK:
            logger.info("Using synthetic fallback option chain.")
            return generate_mock_option_tickers()

        return []

    def get_recent_trades(self, symbol: str = "ETHUSD") -> List[Dict[str, Any]]:
        """
        Fetch recent public trades for order flow analysis.
        """
        url = f"{self.base_url}/v2/trades/{symbol}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result", [])
        except Exception as e:
            logger.warning(f"Could not fetch recent trades for {symbol}: {e}")
        return []
