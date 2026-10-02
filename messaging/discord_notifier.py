"""
Discord Webhook Notifier for Automatic Strategy Selection.
"""

import logging
import requests
from typing import Optional
from config import config
from strategy.option_models import SelectedStrategy

logger = logging.getLogger(__name__)


def send_discord_alert(strat: SelectedStrategy, webhook_url: Optional[str] = None) -> bool:
    """
    Sends rich Discord Embed card to configured webhook URL.
    """
    url = webhook_url or config.DISCORD_WEBHOOK_URL
    if not url:
        return False

    color = 0x2ECC71 if "BULLISH" in strat.market_bias else (
        0xE74C3C if "BEARISH" in strat.market_bias else 0x3498DB
    )

    leg_lines = []
    for leg in strat.legs:
        bid_str = f"{leg.bid:.1f}" if leg.bid is not None else "-"
        ask_str = f"{leg.ask:.1f}" if leg.ask is not None else "-"
        leg_lines.append(
            f"**{leg.action}** `{leg.symbol}` (K: ${leg.strike:.0f}) | Px: ${leg.entry_price:.2f} | Δ: {leg.delta:+.2f}"
        )

    be_str = ", ".join(f"${b:,.2f}" for b in strat.breakevens) if strat.breakevens else "N/A"

    embed = {
        "title": f"🎯 {strat.strategy_name.upper()} ({strat.strategy_type})",
        "description": f"**Asset:** {strat.underlying_symbol} 5m | **Mark Price:** ${strat.underlying_price:,.2f}\n\n*{strat.rationale}*",
        "color": color,
        "fields": [
            {
                "name": "📊 Technical Signals",
                "value": f"• **Supertrend:** `{strat.supertrend_summary}`\n• **CVD:** `{strat.cvd_summary}`\n• **Regime:** `{strat.regime_summary}`",
                "inline": False
            },
            {
                "name": "📋 Option Legs (Delta Exchange)",
                "value": "\n".join(leg_lines) if leg_lines else "No legs available",
                "inline": False
            },
            {
                "name": "💰 Economics (Per ETH)",
                "value": f"• **Net Premium:** `${strat.net_premium:.2f}`\n• **Max Profit:** `${strat.max_profit:.2f}`\n• **Max Loss:** `${strat.max_loss:.2f}`\n• **R:R:** `{strat.risk_reward}`\n• **Breakeven:** `{be_str}`",
                "inline": True
            },
            {
                "name": "⚡ Greeks",
                "value": f"• **Delta:** `{strat.net_delta:+.3f}`\n• **Theta:** `${strat.net_theta:+.2f}/d`\n• **Vega:** `${strat.net_vega:+.2f}`",
                "inline": True
            }
        ],
        "footer": {
            "text": "Delta.exchange Automatic Strategy Selector • 5m Resolution"
        }
    }

    try:
        resp = requests.post(url, json={"embeds": [embed]}, timeout=10)
        return resp.status_code in (200, 204)
    except Exception as e:
        logger.warning(f"Failed to send Discord webhook: {e}")
        return False
