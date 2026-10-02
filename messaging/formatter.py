"""
Message formatting engine for created option strategies.
Generates clear, human-readable text, Markdown, Telegram HTML, and JSON payloads.
"""

import html
from typing import Dict, Any, Optional
from datetime import datetime
from strategy.option_models import SelectedStrategy


def format_strategy_message(strat: SelectedStrategy) -> str:
    """
    Standard formatted strategy report (Clean Markdown/Text).
    """
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "=" * 68,
        f"🎯 AUTOMATIC STRATEGY SELECTION REPORT: {strat.underlying_symbol} (5m)",
        f"⏰ Timestamp: {now_str}",
        f"💵 Underlying Mark Price: ${strat.underlying_price:,.2f}",
        "=" * 68,
        "",
        "📊 MARKET REGIME & SIGNALS:",
        f"  • Supertrend (10, 3.0): {strat.supertrend_summary}",
        f"  • CVD (Cumulative Delta): {strat.cvd_summary}",
        f"  • Volatility & ADX:     {strat.regime_summary}",
        "",
        f"🚀 SELECTED STRATEGY:  {strat.strategy_name.upper()} ({strat.strategy_type})",
        f"🧭 Market Bias:        {strat.market_bias}",
        f"💡 Strategy Rationale: {strat.rationale}",
        "",
        "📋 RECOMMENDED OPTION LEGS (Delta.exchange):",
        "-" * 68,
        f"{'ACTION':<6} {'SYMBOL':<22} {'TYPE':<5} {'STRIKE':<8} {'DELTA':<7} {'BID/ASK':<12} {'MARK'}",
        "-" * 68,
    ]

    for leg in strat.legs:
        bid_str = f"{leg.bid:.1f}" if leg.bid is not None else "-"
        ask_str = f"{leg.ask:.1f}" if leg.ask is not None else "-"
        quotes_str = f"{bid_str}/{ask_str}"
        lines.append(
            f"{leg.action:<6} {leg.symbol:<22} {leg.contract_type:<5} ${leg.strike:<7.0f} "
            f"{leg.delta:<+7.3f} {quotes_str:<12} ${leg.entry_price:.2f}"
        )

    lines.extend([
        "-" * 68,
        "",
        "💰 FINANCIAL METRICS & PAYOFF (Per ETH):",
        f"  • Net Strategy Cost:  ${strat.net_premium:.2f} ({strat.strategy_type})",
        f"  • Max Profit:         ${strat.max_profit:.2f}",
        f"  • Max Loss:           ${strat.max_loss:.2f}",
        f"  • Risk / Reward:      {strat.risk_reward}",
        f"  • Breakeven Point(s): {', '.join(f'${be:,.2f}' for be in strat.breakevens) if strat.breakevens else 'N/A'}",
        "",
        "⚡ NET POSITION GREEKS:",
        f"  • Net Delta: {strat.net_delta:+.3f}  |  Net Theta: ${strat.net_theta:+.2f}/day  |  Net Vega: ${strat.net_vega:+.2f}",
        "=" * 68,
    ])

    return "\n".join(lines)


def format_strategy_telegram(strat: SelectedStrategy, trend_change_info: Optional[Dict[str, Any]] = None) -> str:
    """
    HTML-formatted message tailored for Telegram messaging.
    """
    bias_emoji = "🟢" if "BULLISH" in strat.market_bias else ("🔴" if "BEARISH" in strat.market_bias else "🟡")
    now_str = datetime.utcnow().strftime("%H:%M:%S UTC")

    flip_banner = ""
    if trend_change_info and trend_change_info.get("trend_changed"):
        prev_t = trend_change_info.get("prev_trend", "PREVIOUS")
        curr_t = trend_change_info.get("current_trend", "CURRENT")
        flip_banner = (
            f"🚨 <b>TREND FLIP DETECTED: {prev_t} ➡️ {curr_t}</b> 🚨\n"
            f"⚡ <i>5m Supertrend has reversed! Rotating strategy immediately:</i>\n\n"
        )

    text = (
        f"{flip_banner}"
        f"{bias_emoji} <b>STRATEGY ALERT: {strat.underlying_symbol} 5m</b>\n"
        f"⏱ <i>{now_str}</i> | Mark: <b>${strat.underlying_price:,.2f}</b>\n\n"
        f"🎯 <b>Strategy:</b> <u>{html.escape(strat.strategy_name)}</u> ({strat.strategy_type})\n"
        f"🧭 <b>Bias:</b> {html.escape(strat.market_bias)}\n"
        f"💡 <i>{html.escape(strat.rationale)}</i>\n\n"
        f"📊 <b>Technical Diagnostics:</b>\n"
        f"• Supertrend: <code>{html.escape(strat.supertrend_summary)}</code>\n"
        f"• CVD Flow: <code>{html.escape(strat.cvd_summary)}</code>\n"
        f"• Regime: <code>{html.escape(strat.regime_summary)}</code>\n\n"
        f"📋 <b>Option Legs (Delta Exchange):</b>\n<pre>"
    )

    for leg in strat.legs:
        bid_str = f"{leg.bid:.1f}" if leg.bid is not None else "-"
        ask_str = f"{leg.ask:.1f}" if leg.ask is not None else "-"
        text += f"{leg.action:<4} {leg.symbol} (K: {leg.strike:.0f}) | Px: ${leg.entry_price:.2f} | Δ:{leg.delta:+.2f}\n"

    text += (
        f"</pre>\n"
        f"💵 <b>Net Premium:</b> ${strat.net_premium:.2f} ({strat.strategy_type})\n"
        f"📈 <b>Max Profit:</b> ${strat.max_profit:.2f}\n"
        f"📉 <b>Max Loss:</b> ${strat.max_loss:.2f}\n"
        f"⚖️ <b>Risk/Reward:</b> {strat.risk_reward}\n"
        f"🎯 <b>Breakeven(s):</b> {', '.join(f'${b:,.2f}' for b in strat.breakevens)}\n"
        f"⚡ <b>Greeks:</b> Δ:{strat.net_delta:+.2f} | Θ:${strat.net_theta:+.2f}/d | 𝒱:${strat.net_vega:+.2f}"
    )

    return text


def format_strategy_dict(strat: SelectedStrategy) -> Dict[str, Any]:
    """
    Returns full JSON-serializable dictionary.
    """
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "underlying": strat.underlying_symbol,
        "underlying_price": strat.underlying_price,
        "strategy_name": strat.strategy_name,
        "strategy_type": strat.strategy_type,
        "market_bias": strat.market_bias,
        "rationale": strat.rationale,
        "diagnostics": {
            "supertrend": strat.supertrend_summary,
            "cvd": strat.cvd_summary,
            "regime": strat.regime_summary,
        },
        "legs": [
            {
                "symbol": leg.symbol,
                "action": leg.action,
                "type": leg.contract_type,
                "strike": leg.strike,
                "expiry": leg.expiry,
                "entry_price": leg.entry_price,
                "best_bid": leg.bid,
                "best_ask": leg.ask,
                "delta": leg.delta,
                "theta": leg.theta,
                "vega": leg.vega,
                "iv_pct": leg.iv,
            }
            for leg in strat.legs
        ],
        "economics": {
            "net_premium_usd": strat.net_premium,
            "max_profit_usd": strat.max_profit,
            "max_loss_usd": strat.max_loss,
            "risk_reward": strat.risk_reward,
            "breakevens": strat.breakevens,
            "net_delta": strat.net_delta,
            "net_theta": strat.net_theta,
            "net_vega": strat.net_vega,
        }
    }
