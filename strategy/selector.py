"""
Automatic Strategy Selection Engine.
Synthesizes Supertrend, Cumulative Volume Delta (CVD), ADX Trend Strength,
and Volatility Regime to automatically construct the optimal options strategy
using live Delta Exchange option contracts.
"""

from typing import List, Dict, Any
from indicators.supertrend import SupertrendResult
from indicators.cvd import CVDResult
from indicators.regime import RegimeResult
from strategy.option_models import SelectedStrategy, OptionLeg
from strategy.option_pricer import (
    filter_by_optimal_expiry,
    find_option_by_delta,
    build_option_leg
)


class AutomaticStrategySelector:
    """
    Evaluates market conditions on 5m ETHUSD and creates complete multi-leg option strategies.
    """

    def __init__(self, expiry_preference: str = "nearest"):
        self.expiry_preference = expiry_preference

    def select_strategy(
        self,
        underlying_symbol: str,
        underlying_price: float,
        supertrend: SupertrendResult,
        cvd: CVDResult,
        regime: RegimeResult,
        option_tickers: List[Dict[str, Any]]
    ) -> SelectedStrategy:
        """
        Main decision engine: selects strategy name, pulls option legs, and computes pricing.
        """
        expiry, expiry_options = filter_by_optimal_expiry(option_tickers, self.expiry_preference)

        # 1. Determine Bias and Strategy Blueprint
        is_bullish = supertrend.direction == 1
        is_bearish = supertrend.direction == -1
        cvd_rising = cvd.cvd_trend == "RISING"
        cvd_falling = cvd.cvd_trend == "FALLING"
        is_trending = regime.trend_strength in ("STRONG_TREND", "MODERATE_TREND")
        high_vol = regime.volatility_regime == "HIGH_VOLATILITY"
        low_vol = regime.volatility_regime == "LOW_VOLATILITY"

        # Check Divergences first (Leading Reversal Signals)
        if cvd.divergence == "BULLISH_DIVERGENCE":
            strategy_name = "Bull Call Spread"
            market_bias = "BULLISH (Absorption Reversal)"
            rationale = (
                f"Bullish CVD Absorption detected! Despite 5m price dips, aggressive buyers are soaking up sell "
                f"orders (CVD higher low). Selecting Bull Call Spread for high-asymmetry upside recovery."
            )
            legs = self._build_bull_call_spread(expiry_options, expiry)

        elif cvd.divergence == "BEARISH_DIVERGENCE":
            strategy_name = "Bear Put Spread"
            market_bias = "BEARISH (Exhaustion Reversal)"
            rationale = (
                f"Bearish CVD Exhaustion detected! Price pushed higher but CVD failed to confirm (lower high). "
                f"Selecting Bear Put Spread to capture impending downward mean-reversion."
            )
            legs = self._build_bear_put_spread(expiry_options, expiry)

        # Trending Regimes
        elif is_bullish and not cvd_falling and is_trending:
            if high_vol:
                strategy_name = "Bull Put Spread (Credit)"
                market_bias = "BULLISH"
                rationale = (
                    f"Supertrend is BULLISH with CVD confirmation in an elevated volatility environment "
                    f"(IV/ATR Rank: {regime.vol_percentile:.1f}%). Selecting Bull Put Credit Spread to harvest "
                    f"rich options premium and positive Theta decay while keeping defined downside risk."
                )
                legs = self._build_bull_put_credit_spread(expiry_options, expiry)
            else:
                strategy_name = "Bull Call Spread (Debit)"
                market_bias = "BULLISH"
                rationale = (
                    f"Supertrend is BULLISH with aggressive buyer accumulation (CVD: {cvd.cvd_trend}) in a "
                    f"trending market (ADX: {regime.adx:.1f}). Selecting Bull Call Spread to leverage upward "
                    f"momentum with capped capital risk."
                )
                legs = self._build_bull_call_spread(expiry_options, expiry)

        elif is_bearish and not cvd_rising and is_trending:
            if high_vol:
                strategy_name = "Bear Call Spread (Credit)"
                market_bias = "BEARISH"
                rationale = (
                    f"Supertrend is BEARISH with CVD distribution in an elevated volatility environment "
                    f"(IV/ATR Rank: {regime.vol_percentile:.1f}%). Selecting Bear Call Credit Spread to monetize "
                    f"high call premium with rapid Theta decay."
                )
                legs = self._build_bear_call_credit_spread(expiry_options, expiry)
            else:
                strategy_name = "Bear Put Spread (Debit)"
                market_bias = "BEARISH"
                rationale = (
                    f"Supertrend is BEARISH with aggressive seller distribution (CVD: {cvd.cvd_trend}) in a "
                    f"trending market (ADX: {regime.adx:.1f}). Selecting Bear Put Spread for directional downside."
                )
                legs = self._build_bear_put_spread(expiry_options, expiry)

        # Range-bound / Choppy / Low ADX Regimes
        else:
            if low_vol:
                strategy_name = "Long Straddle (Volatility Breakout)"
                market_bias = "VOLATILITY_EXPANSION"
                rationale = (
                    f"Consolidation with compressed volatility detected (ADX: {regime.adx:.1f}, Low Vol Regime). "
                    f"A major directional volatility breakout is imminent. Selecting Long Straddle to profit from "
                    f"large move in either direction."
                )
                legs = self._build_long_straddle(expiry_options, expiry)
            else:
                strategy_name = "Iron Condor (Delta-Neutral Credit)"
                market_bias = "NEUTRAL_RANGE"
                if not is_trending:
                    rationale = (
                        f"Market is non-trending / range-bound (ADX: {regime.adx:.1f} < 22). "
                        f"Directional momentum is absent. Selecting Iron Condor to collect premium from both wings "
                        f"while ETH remains inside support/resistance bounds."
                    )
                else:
                    rationale = (
                        f"Directional conflict detected: Supertrend is {supertrend.trend_label} but CVD order flow is "
                        f"{cvd.cvd_trend} (divergent taker volume). Market lacks directional consensus. Selecting "
                        f"Iron Condor to capture range-bound Theta decay."
                    )
                legs = self._build_iron_condor(expiry_options, expiry)

        st_sum = f"{supertrend.trend_label} (Stop: ${supertrend.trailing_stop:,.2f}, Dist: {supertrend.distance_pct:+.2f}%)"
        cvd_sum = f"{cvd.cvd_trend} (Delta: {cvd.last_bar_delta:+.1f} ETH, Div: {cvd.divergence})"
        reg_sum = f"{regime.trend_strength} | ADX: {regime.adx:.1f} | {regime.volatility_regime}"

        strategy = SelectedStrategy(
            strategy_name=strategy_name,
            market_bias=market_bias,
            strategy_type="NET_DEBIT",
            rationale=rationale,
            underlying_symbol=underlying_symbol,
            underlying_price=round(underlying_price, 2),
            supertrend_summary=st_sum,
            cvd_summary=cvd_sum,
            regime_summary=reg_sum,
            legs=legs
        )

        strategy.compute_payoffs()
        return strategy

    # Leg Construction Helpers
    def _build_bull_call_spread(self, options: List[Dict[str, Any]], expiry: str) -> List[OptionLeg]:
        legs = []
        buy_call = find_option_by_delta(options, "call_options", target_delta=0.50)
        if buy_call:
            legs.append(build_option_leg(buy_call, action="BUY", expiry=expiry))
            sell_call = find_option_by_delta(
                options, "call_options", target_delta=0.25,
                exclude_strikes=[buy_call.get("strike_price")]
            )
            if sell_call:
                legs.append(build_option_leg(sell_call, action="SELL", expiry=expiry))
        return legs

    def _build_bear_put_spread(self, options: List[Dict[str, Any]], expiry: str) -> List[OptionLeg]:
        legs = []
        buy_put = find_option_by_delta(options, "put_options", target_delta=-0.50)
        if buy_put:
            legs.append(build_option_leg(buy_put, action="BUY", expiry=expiry))
            sell_put = find_option_by_delta(
                options, "put_options", target_delta=-0.25,
                exclude_strikes=[buy_put.get("strike_price")]
            )
            if sell_put:
                legs.append(build_option_leg(sell_put, action="SELL", expiry=expiry))
        return legs

    def _build_bull_put_credit_spread(self, options: List[Dict[str, Any]], expiry: str) -> List[OptionLeg]:
        legs = []
        sell_put = find_option_by_delta(options, "put_options", target_delta=-0.35)
        if sell_put:
            legs.append(build_option_leg(sell_put, action="SELL", expiry=expiry))
            buy_put = find_option_by_delta(
                options, "put_options", target_delta=-0.15,
                exclude_strikes=[sell_put.get("strike_price")]
            )
            if buy_put:
                legs.append(build_option_leg(buy_put, action="BUY", expiry=expiry))
        return legs

    def _build_bear_call_credit_spread(self, options: List[Dict[str, Any]], expiry: str) -> List[OptionLeg]:
        legs = []
        sell_call = find_option_by_delta(options, "call_options", target_delta=0.35)
        if sell_call:
            legs.append(build_option_leg(sell_call, action="SELL", expiry=expiry))
            buy_call = find_option_by_delta(
                options, "call_options", target_delta=0.15,
                exclude_strikes=[sell_call.get("strike_price")]
            )
            if buy_call:
                legs.append(build_option_leg(buy_call, action="BUY", expiry=expiry))
        return legs

    def _build_iron_condor(self, options: List[Dict[str, Any]], expiry: str) -> List[OptionLeg]:
        legs = []
        # Put spread wing (Credit)
        sp = find_option_by_delta(options, "put_options", target_delta=-0.20)
        if sp:
            legs.append(build_option_leg(sp, action="SELL", expiry=expiry))
            lp = find_option_by_delta(options, "put_options", target_delta=-0.10, exclude_strikes=[sp.get("strike_price")])
            if lp:
                legs.append(build_option_leg(lp, action="BUY", expiry=expiry))

        # Call spread wing (Credit)
        sc = find_option_by_delta(options, "call_options", target_delta=0.20)
        if sc:
            legs.append(build_option_leg(sc, action="SELL", expiry=expiry))
            lc = find_option_by_delta(options, "call_options", target_delta=0.10, exclude_strikes=[sc.get("strike_price")])
            if lc:
                legs.append(build_option_leg(lc, action="BUY", expiry=expiry))

        return legs

    def _build_long_straddle(self, options: List[Dict[str, Any]], expiry: str) -> List[OptionLeg]:
        legs = []
        c = find_option_by_delta(options, "call_options", target_delta=0.50)
        p = find_option_by_delta(options, "put_options", target_delta=-0.50)
        if c:
            legs.append(build_option_leg(c, action="BUY", expiry=expiry))
        if p:
            legs.append(build_option_leg(p, action="BUY", expiry=expiry))
        return legs
