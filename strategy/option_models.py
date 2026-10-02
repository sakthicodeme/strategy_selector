"""
Data models for Option Legs and Constructed Multi-Leg Strategies.
Calculates net premium, max profit, max loss, breakevens, and aggregate Greeks.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class OptionLeg:
    symbol: str
    action: str              # "BUY" or "SELL"
    contract_type: str       # "CALL" or "PUT"
    strike: float
    expiry: str
    bid: Optional[float]
    ask: Optional[float]
    mark_price: float
    entry_price: float       # Executable price (ask if BUY, bid if SELL, fallback to mark)
    delta: float
    theta: float
    vega: float
    iv: float
    quantity: int = 1

    def leg_cashflow(self) -> float:
        """
        Positive value represents cash outlay (Debit/Buy).
        Negative value represents cash inflow (Credit/Sell).
        """
        return self.entry_price * self.quantity if self.action == "BUY" else -self.entry_price * self.quantity


@dataclass
class SelectedStrategy:
    strategy_name: str
    market_bias: str         # "BULLISH", "BEARISH", "NEUTRAL_RANGE", "VOLATILITY_EXPANSION"
    strategy_type: str       # "NET_DEBIT" or "NET_CREDIT"
    rationale: str
    underlying_symbol: str
    underlying_price: float
    supertrend_summary: str
    cvd_summary: str
    regime_summary: str
    legs: List[OptionLeg] = field(default_factory=list)
    net_premium: float = 0.0      # In USD per ETH
    max_profit: float = 0.0       # Max profit in USD per ETH
    max_loss: float = 0.0         # Max loss in USD per ETH
    risk_reward: str = "N/A"
    breakevens: List[float] = field(default_factory=list)
    net_delta: float = 0.0
    net_theta: float = 0.0
    net_vega: float = 0.0

    def compute_payoffs(self):
        """
        Computes aggregate economics and Greeks across all option legs.
        """
        if not self.legs:
            return

        total_cashflow = sum(leg.leg_cashflow() for leg in self.legs)
        self.net_premium = round(abs(total_cashflow), 2)
        self.strategy_type = "NET_DEBIT" if total_cashflow > 0 else "NET_CREDIT"

        # Aggregate Greeks
        tot_delta = 0.0
        tot_theta = 0.0
        tot_vega = 0.0
        for leg in self.legs:
            sign = 1 if leg.action == "BUY" else -1
            tot_delta += sign * leg.delta * leg.quantity
            tot_theta += sign * leg.theta * leg.quantity
            tot_vega += sign * leg.vega * leg.quantity

        self.net_delta = round(tot_delta, 3)
        self.net_theta = round(tot_theta, 2)
        self.net_vega = round(tot_vega, 2)

        # Strategy Specific Payoff Calculation
        name = self.strategy_name.upper()

        if "BULL CALL SPREAD" in name:
            # Buy lower strike call (K1), Sell higher strike call (K2)
            k_buy = next((l.strike for l in self.legs if l.action == "BUY" and l.contract_type == "CALL"), 0.0)
            k_sell = next((l.strike for l in self.legs if l.action == "SELL" and l.contract_type == "CALL"), 0.0)
            spread_width = abs(k_sell - k_buy)
            self.max_loss = self.net_premium
            self.max_profit = round(max(0.0, spread_width - self.net_premium), 2)
            self.breakevens = [round(k_buy + self.net_premium, 2)]

        elif "BEAR PUT SPREAD" in name:
            # Buy higher strike put (K1), Sell lower strike put (K2)
            k_buy = next((l.strike for l in self.legs if l.action == "BUY" and l.contract_type == "PUT"), 0.0)
            k_sell = next((l.strike for l in self.legs if l.action == "SELL" and l.contract_type == "PUT"), 0.0)
            spread_width = abs(k_buy - k_sell)
            self.max_loss = self.net_premium
            self.max_profit = round(max(0.0, spread_width - self.net_premium), 2)
            self.breakevens = [round(k_buy - self.net_premium, 2)]

        elif "BULL PUT SPREAD" in name:
            # Credit Spread: Sell higher put (K_short), Buy lower put (K_long)
            k_short = next((l.strike for l in self.legs if l.action == "SELL" and l.contract_type == "PUT"), 0.0)
            k_long = next((l.strike for l in self.legs if l.action == "BUY" and l.contract_type == "PUT"), 0.0)
            spread_width = abs(k_short - k_long)
            self.max_profit = self.net_premium
            self.max_loss = round(max(0.0, spread_width - self.net_premium), 2)
            self.breakevens = [round(k_short - self.net_premium, 2)]

        elif "BEAR CALL SPREAD" in name:
            # Credit Spread: Sell lower call (K_short), Buy higher call (K_long)
            k_short = next((l.strike for l in self.legs if l.action == "SELL" and l.contract_type == "CALL"), 0.0)
            k_long = next((l.strike for l in self.legs if l.action == "BUY" and l.contract_type == "CALL"), 0.0)
            spread_width = abs(k_long - k_short)
            self.max_profit = self.net_premium
            self.max_loss = round(max(0.0, spread_width - self.net_premium), 2)
            self.breakevens = [round(k_short + self.net_premium, 2)]

        elif "IRON CONDOR" in name:
            # Sell OTM Put (K_sp) + Buy lower Put wing (K_lp)
            # Sell OTM Call (K_sc) + Buy higher Call wing (K_lc)
            k_sp = next((l.strike for l in self.legs if l.action == "SELL" and l.contract_type == "PUT"), 0.0)
            k_lp = next((l.strike for l in self.legs if l.action == "BUY" and l.contract_type == "PUT"), 0.0)
            wing_width = abs(k_sp - k_lp)
            self.max_profit = self.net_premium
            self.max_loss = round(max(0.0, wing_width - self.net_premium), 2)
            k_sc = next((l.strike for l in self.legs if l.action == "SELL" and l.contract_type == "CALL"), 0.0)
            self.breakevens = [
                round(k_sp - self.net_premium, 2),
                round(k_sc + self.net_premium, 2)
            ]

        elif "LONG STRADDLE" in name or "LONG STRANGLE" in name:
            # Buy ATM/OTM Call & Put
            self.max_loss = self.net_premium
            self.max_profit = 99999.0  # Unlimited
            k_call = next((l.strike for l in self.legs if l.contract_type == "CALL"), 0.0)
            k_put = next((l.strike for l in self.legs if l.contract_type == "PUT"), 0.0)
            self.breakevens = [
                round(k_put - self.net_premium, 2),
                round(k_call + self.net_premium, 2)
            ]

        else:
            # Generic
            self.max_loss = self.net_premium
            self.max_profit = self.net_premium

        # Compute Risk / Reward string
        if self.max_loss > 0 and self.max_profit < 90000:
            ratio = self.max_profit / self.max_loss
            self.risk_reward = f"1 : {ratio:.2f}"
        elif self.max_profit >= 90000:
            self.risk_reward = "Asymmetric (Unlimited Upside)"
        else:
            self.risk_reward = "Defined"
