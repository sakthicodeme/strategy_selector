#!/usr/bin/env python3
"""
ETHUSD 5m Automatic Strategy Selection System.
Integrates Delta Exchange market data, Supertrend, Cumulative Volume Delta (CVD),
ADX Trend Filter, and Volatility Regime to dynamically construct and price option strategies.
"""

import sys
import time
import argparse
import logging
from config import config
from data.delta_client import DeltaClient
from data.mock_data import generate_mock_candles, generate_mock_option_tickers
from indicators.supertrend import calculate_supertrend
from indicators.cvd import calculate_cvd
from indicators.regime import calculate_market_regime
from strategy.selector import AutomaticStrategySelector
from messaging.formatter import format_strategy_message, format_strategy_dict
from messaging.console_printer import print_strategy_console
from messaging.telegram_notifier import send_telegram_alert
from messaging.discord_notifier import send_discord_alert

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_pipeline(
    symbol: str = "ETHUSD",
    resolution: str = "5m",
    exchange_env: str = "india",
    force_mock: bool = False,
    mock_regime: str = "bullish",
    send_telegram: bool = False,
    send_discord: bool = False,
    output_format: str = "console",
    alert_on_trend_change_only: bool = True
):
    """
    Executes a single cycle of the Automatic Strategy Selection pipeline.
    """
    base_url = "https://api.india.delta.exchange" if exchange_env == "india" else "https://api.delta.exchange"
    client = DeltaClient(base_url=base_url)
    selector = AutomaticStrategySelector(expiry_preference=config.EXPIRY_PREFERENCE)

    # 1. Fetch Market Data
    if force_mock:
        logger.info(f"Running in MOCK mode (simulated regime: '{mock_regime}').")
        candles_df = generate_mock_candles(symbol=symbol, resolution=resolution, regime=mock_regime)
        ticker_data = {"symbol": symbol, "mark_price": float(candles_df["close"].iloc[-1])}
        recent_trades = []
        option_tickers = generate_mock_option_tickers(spot_price=ticker_data["mark_price"])
    else:
        logger.info(f"Connecting to Delta Exchange ({base_url}) for {symbol} ({resolution})...")
        candles_df = client.get_candles(symbol=symbol, resolution=resolution, limit=120)
        ticker_data = client.get_spot_or_mark_ticker(symbol=symbol)
        recent_trades = client.get_recent_trades(symbol=symbol)
        option_tickers = client.get_option_tickers(underlying=config.UNDERLYING_ASSET)

    if candles_df.empty:
        logger.error("No candle data available. Exiting pipeline.")
        return None

    underlying_price = ticker_data.get("mark_price") or float(candles_df["close"].iloc[-1])

    # 2. Compute Indicators
    supertrend_res = calculate_supertrend(
        candles_df,
        period=config.SUPERTREND_PERIOD,
        multiplier=config.SUPERTREND_MULTIPLIER
    )

    cvd_res = calculate_cvd(
        candles_df,
        lookback=config.CVD_LOOKBACK,
        ema_period=config.CVD_EMA_PERIOD,
        recent_trades=recent_trades
    )

    regime_res = calculate_market_regime(
        candles_df,
        adx_period=config.ADX_PERIOD,
        trend_threshold=config.ADX_TREND_THRESHOLD,
        vol_high_pct=config.VOL_HIGH_PERCENTILE,
        vol_low_pct=config.VOL_LOW_PERCENTILE,
        options_tickers=option_tickers
    )

    # 3. Automatic Strategy Selection & Pricing
    strategy = selector.select_strategy(
        underlying_symbol=symbol,
        underlying_price=underlying_price,
        supertrend=supertrend_res,
        cvd=cvd_res,
        regime=regime_res,
        option_tickers=option_tickers
    )

    # 4. State & Trend Change Detection
    from strategy.state_manager import StateManager
    state_mgr = StateManager()
    trend_info = state_mgr.check_trend_change(supertrend_res.direction, strategy.strategy_name)

    if trend_info.get("trend_changed"):
        logger.info(
            f"🚨 TREND FLIP DETECTED: {trend_info.get('prev_trend')} -> {trend_info.get('current_trend')}! "
            f"Rotating to {strategy.strategy_name}."
        )

    # 5. Message Dispatch
    if output_format == "console":
        print_strategy_console(strategy)
    elif output_format == "text":
        print(format_strategy_message(strategy))
    elif output_format == "json":
        import json
        print(json.dumps(format_strategy_dict(strategy), indent=2))

    # Send Telegram alert if requested
    should_send_telegram = send_telegram
    if alert_on_trend_change_only and not (trend_info.get("trend_changed") or trend_info.get("is_first_run")):
        should_send_telegram = False
        logger.info("Trend has not flipped since last check. Skipping Telegram alert to avoid noise.")

    if should_send_telegram:
        send_telegram_alert(strategy, trend_change_info=trend_info)

    if send_discord:
        send_discord_alert(strategy)

    # Persist updated state
    state_mgr.save_state(
        trend_direction=supertrend_res.direction,
        trend_label=supertrend_res.trend_label,
        strategy_name=strategy.strategy_name,
        underlying_price=underlying_price,
        supertrend_line=supertrend_res.supertrend_line
    )

    return strategy


def main():
    parser = argparse.ArgumentParser(
        description="Automatic Strategy Selection for ETHUSD (5m) via Delta Exchange"
    )
    parser.add_argument("--symbol", default="ETHUSD", help="Underlying symbol (default: ETHUSD)")
    parser.add_argument("--timeframe", default="5m", help="Candle timeframe (default: 5m)")
    parser.add_argument(
        "--exchange",
        choices=["india", "global"],
        default="india",
        help="Delta Exchange environment (india or global)"
    )
    parser.add_argument("--mock", action="store_true", help="Force synthetic mock data")
    parser.add_argument(
        "--regime",
        choices=["bullish", "bearish", "ranging", "divergence"],
        default="bullish",
        help="Simulated regime when --mock is enabled"
    )
    parser.add_argument(
        "--output",
        choices=["console", "text", "json"],
        default="console",
        help="Output display format"
    )
    parser.add_argument("--send-telegram", action="store_true", help="Dispatch to Telegram bot")
    parser.add_argument(
        "--alert-on-trend-change-only",
        action="store_true",
        default=True,
        help="Only dispatch Telegram alert when Supertrend flips or strategy changes (default: True)"
    )
    parser.add_argument(
        "--always-alert",
        dest="alert_on_trend_change_only",
        action="store_false",
        help="Send Telegram alert on every 5m execution cycle even if trend hasn't changed"
    )
    parser.add_argument("--send-discord", action="store_true", help="Dispatch to Discord webhook")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run continuously every 5 minutes on candle close"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Interval in seconds when running with --watch (default: 300)"
    )

    args = parser.parse_args()

    if args.watch:
        logger.info(f"Starting continuous monitor every {args.interval}s for {args.symbol} {args.timeframe}...")
        while True:
            try:
                run_pipeline(
                    symbol=args.symbol,
                    resolution=args.timeframe,
                    exchange_env=args.exchange,
                    force_mock=args.mock,
                    mock_regime=args.regime,
                    send_telegram=args.send_telegram,
                    send_discord=args.send_discord,
                    output_format=args.output,
                    alert_on_trend_change_only=args.alert_on_trend_change_only
                )
                time.sleep(args.interval)
            except KeyboardInterrupt:
                logger.info("Exiting monitor.")
                sys.exit(0)
            except Exception as e:
                logger.error(f"Error in execution loop: {e}", exc_info=True)
                time.sleep(10)
    else:
        run_pipeline(
            symbol=args.symbol,
            resolution=args.timeframe,
            exchange_env=args.exchange,
            force_mock=args.mock,
            mock_regime=args.regime,
            send_telegram=args.send_telegram,
            send_discord=args.send_discord,
            output_format=args.output,
            alert_on_trend_change_only=args.alert_on_trend_change_only
        )


if __name__ == "__main__":
    main()
