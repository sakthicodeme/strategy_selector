"""
Unit and Integration tests for ETHUSD Automatic Strategy Selection Project.
"""

import unittest
import pandas as pd
from data.mock_data import generate_mock_candles, generate_mock_option_tickers
from indicators.supertrend import calculate_supertrend
from indicators.cvd import calculate_cvd
from indicators.regime import calculate_market_regime
from strategy.selector import AutomaticStrategySelector
from strategy.option_models import OptionLeg, SelectedStrategy
from strategy.option_pricer import filter_by_optimal_expiry, find_option_by_delta, build_option_leg
from messaging.formatter import format_strategy_message, format_strategy_telegram, format_strategy_dict


class TestAutomaticStrategySelection(unittest.TestCase):

    def setUp(self):
        self.spot_price = 2750.0
        self.bull_candles = generate_mock_candles(count=100, regime="bullish", base_price=self.spot_price)
        self.bear_candles = generate_mock_candles(count=100, regime="bearish", base_price=self.spot_price)
        self.range_candles = generate_mock_candles(count=100, regime="ranging", base_price=self.spot_price)
        self.div_candles = generate_mock_candles(count=100, regime="divergence", base_price=self.spot_price)
        self.options = generate_mock_option_tickers(spot_price=self.spot_price)
        self.selector = AutomaticStrategySelector()

    def test_supertrend_bullish(self):
        st = calculate_supertrend(self.bull_candles, period=10, multiplier=3.0)
        self.assertIn(st.direction, [1, -1])
        self.assertGreater(st.supertrend_line, 0.0)
        self.assertGreater(st.atr, 0.0)

    def test_cvd_calculation(self):
        cvd = calculate_cvd(self.bull_candles, lookback=50)
        self.assertIn(cvd.cvd_trend, ["RISING", "FALLING", "FLAT"])
        self.assertIn(cvd.divergence, ["BULLISH_DIVERGENCE", "BEARISH_DIVERGENCE", "NONE"])
        self.assertIsInstance(cvd.current_cvd, float)

    def test_regime_calculation(self):
        regime = calculate_market_regime(self.range_candles, options_tickers=self.options)
        self.assertGreaterEqual(regime.adx, 0.0)
        self.assertIn(regime.trend_strength, ["STRONG_TREND", "MODERATE_TREND", "WEAK_RANGE"])
        self.assertIn(regime.volatility_regime, ["HIGH_VOLATILITY", "NORMAL_VOLATILITY", "LOW_VOLATILITY"])

    def test_option_expiry_and_delta_matching(self):
        expiry, exp_options = filter_by_optimal_expiry(self.options)
        self.assertTrue(len(expiry) > 0)
        self.assertTrue(len(exp_options) > 0)

        # Find ATM call ~0.50 delta
        atm_call = find_option_by_delta(exp_options, "call_options", target_delta=0.50)
        self.assertIsNotNone(atm_call)
        d = float(atm_call["greeks"]["delta"])
        self.assertAlmostEqual(d, 0.50, delta=0.20)

        # Build Option Leg
        leg = build_option_leg(atm_call, action="BUY", expiry=expiry)
        self.assertEqual(leg.action, "BUY")
        self.assertEqual(leg.contract_type, "CALL")
        self.assertGreater(leg.entry_price, 0.0)

    def test_bullish_strategy_selection(self):
        st = calculate_supertrend(self.bull_candles)
        cvd = calculate_cvd(self.bull_candles)
        regime = calculate_market_regime(self.bull_candles, options_tickers=self.options)

        strategy = self.selector.select_strategy(
            underlying_symbol="ETHUSD",
            underlying_price=self.spot_price,
            supertrend=st,
            cvd=cvd,
            regime=regime,
            option_tickers=self.options
        )

        self.assertIsNotNone(strategy)
        self.assertGreater(len(strategy.legs), 0)
        self.assertGreater(strategy.net_premium, 0.0)
        self.assertGreater(len(strategy.breakevens), 0)

    def test_divergence_strategy_trigger(self):
        st = calculate_supertrend(self.div_candles)
        cvd = calculate_cvd(self.div_candles)
        regime = calculate_market_regime(self.div_candles, options_tickers=self.options)

        strategy = self.selector.select_strategy(
            underlying_symbol="ETHUSD",
            underlying_price=self.spot_price,
            supertrend=st,
            cvd=cvd,
            regime=regime,
            option_tickers=self.options
        )

        self.assertIsNotNone(strategy.strategy_name)
        self.assertTrue(len(strategy.legs) >= 2)

    def test_message_formatting(self):
        st = calculate_supertrend(self.bull_candles)
        cvd = calculate_cvd(self.bull_candles)
        regime = calculate_market_regime(self.bull_candles, options_tickers=self.options)

        strategy = self.selector.select_strategy(
            underlying_symbol="ETHUSD",
            underlying_price=self.spot_price,
            supertrend=st,
            cvd=cvd,
            regime=regime,
            option_tickers=self.options
        )

        # Text Report
        text_msg = format_strategy_message(strategy)
        self.assertIn("AUTOMATIC STRATEGY SELECTION REPORT", text_msg)
        self.assertIn("ETHUSD", text_msg)
        self.assertIn("RECOMMENDED OPTION LEGS", text_msg)

        # Telegram Report
        tg_msg = format_strategy_telegram(strategy)
        self.assertIn("<b>STRATEGY ALERT:", tg_msg)
        self.assertIn("Option Legs (Delta Exchange):", tg_msg)

        # JSON Dict
        json_dict = format_strategy_dict(strategy)
        self.assertEqual(json_dict["underlying"], "ETHUSD")
        self.assertEqual(len(json_dict["legs"]), len(strategy.legs))

    def test_state_manager_trend_flip(self):
        import os
        from strategy.state_manager import StateManager
        test_state_file = "/tmp/test_eth_state.json"
        if os.path.exists(test_state_file):
            os.remove(test_state_file)

        mgr = StateManager(state_file=test_state_file)

        # 1. First run: Initial state
        res1 = mgr.check_trend_change(current_direction=1, current_strategy="Bull Call Spread")
        self.assertTrue(res1["is_first_run"])
        self.assertTrue(res1["trend_changed"])

        mgr.save_state(
            trend_direction=1,
            trend_label="BULLISH",
            strategy_name="Bull Call Spread",
            underlying_price=2750.0,
            supertrend_line=2720.0
        )

        # 2. Same trend: No flip
        res2 = mgr.check_trend_change(current_direction=1, current_strategy="Bull Call Spread")
        self.assertFalse(res2["is_first_run"])
        self.assertFalse(res2["trend_changed"])

        # 3. Trend Flip: Bullish -> Bearish
        res3 = mgr.check_trend_change(current_direction=-1, current_strategy="Bear Put Spread")
        self.assertTrue(res3["trend_changed"])
        self.assertEqual(res3["prev_trend"], "BULLISH")
        self.assertEqual(res3["current_trend"], "BEARISH")

        if os.path.exists(test_state_file):
            os.remove(test_state_file)


if __name__ == "__main__":
    unittest.main()
