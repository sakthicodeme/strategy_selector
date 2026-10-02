"""
Configuration settings for ETHUSD Automatic Strategy Selection Project.
Supports live Delta Exchange (India & Global) API and notification webhooks.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


@dataclass
class Config:
    # Asset & Timeframe
    SYMBOL: str = os.getenv("SYMBOL", "ETHUSD")
    TIMEFRAME: str = os.getenv("TIMEFRAME", "5m")
    UNDERLYING_ASSET: str = os.getenv("UNDERLYING_ASSET", "ETH")

    # Delta Exchange API endpoints
    # Supports 'india' (api.india.delta.exchange) or 'global' (api.delta.exchange)
    EXCHANGE_ENV: str = os.getenv("EXCHANGE_ENV", "india").lower()
    DELTA_BASE_URL: str = os.getenv(
        "DELTA_BASE_URL",
        "https://api.india.delta.exchange" if os.getenv("EXCHANGE_ENV", "india").lower() == "india"
        else "https://api.delta.exchange"
    )
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "10"))
    USE_MOCK_FALLBACK: bool = os.getenv("USE_MOCK_FALLBACK", "true").lower() in ("true", "1", "yes")

    # Indicator Parameters
    SUPERTREND_PERIOD: int = int(os.getenv("SUPERTREND_PERIOD", "10"))
    SUPERTREND_MULTIPLIER: float = float(os.getenv("SUPERTREND_MULTIPLIER", "3.0"))

    CVD_LOOKBACK: int = int(os.getenv("CVD_LOOKBACK", "50"))
    CVD_EMA_PERIOD: int = int(os.getenv("CVD_EMA_PERIOD", "10"))

    # Suggested Filter Parameters
    ADX_PERIOD: int = int(os.getenv("ADX_PERIOD", "14"))
    ADX_TREND_THRESHOLD: float = float(os.getenv("ADX_TREND_THRESHOLD", "22.0"))

    # Volatility / IV Regime Thresholds (in percentile)
    VOL_HIGH_PERCENTILE: float = float(os.getenv("VOL_HIGH_PERCENTILE", "60.0"))
    VOL_LOW_PERCENTILE: float = float(os.getenv("VOL_LOW_PERCENTILE", "35.0"))

    # Options Chain & Expiry Selection
    EXPIRY_PREFERENCE: str = os.getenv("EXPIRY_PREFERENCE", "nearest")  # 'nearest', 'weekly', or 'monthly'
    MIN_DTE_HOURS: float = float(os.getenv("MIN_DTE_HOURS", "2.0"))      # Skip options expiring in less than 2 hours

    # Messaging / Notification Config
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")


# Global singleton configuration
config = Config()
