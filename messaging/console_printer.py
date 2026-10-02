"""
Rich Console Printer for Automatic Strategy Selection Dashboard.
Renders stylized tables and status cards in the terminal.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from strategy.option_models import SelectedStrategy

console = Console()


def print_strategy_console(strat: SelectedStrategy):
    """
    Renders the selected strategy and its option legs with rich terminal formatting.
    """
    # Determine accent color
    if "BULLISH" in strat.market_bias:
        color = "green"
        emoji = "📈"
    elif "BEARISH" in strat.market_bias:
        color = "red"
        emoji = "📉"
    elif "VOLATILITY" in strat.market_bias:
        color = "yellow"
        emoji = "⚡"
    else:
        color = "cyan"
        emoji = "⚖️"

    header_text = Text()
    header_text.append(f"{emoji} {strat.underlying_symbol} 5m | Live Mark: ", style="bold white")
    header_text.append(f"${strat.underlying_price:,.2f}\n", style=f"bold {color}")
    header_text.append(f"Strategy: ", style="bold white")
    header_text.append(f"{strat.strategy_name.upper()} ", style=f"bold underline {color}")
    header_text.append(f"({strat.strategy_type})\n", style="italic")
    header_text.append(f"Bias: {strat.market_bias}\n", style=f"bold {color}")
    header_text.append(f"Rationale: {strat.rationale}", style="dim")

    console.print(Panel(header_text, title="🎯 Delta.exchange Automatic Strategy Selection", border_style=color))

    # Diagnostics Table
    diag_table = Table(title="🔍 Market Diagnostics & Signals", show_header=True, header_style="bold magenta")
    diag_table.add_column("Indicator / Filter", style="cyan", width=24)
    diag_table.add_column("Current Reading / Status", style="white")

    diag_table.add_row("Supertrend (10, 3.0)", strat.supertrend_summary)
    diag_table.add_row("Cumulative Volume Delta (CVD)", strat.cvd_summary)
    diag_table.add_row("Market Regime & ADX", strat.regime_summary)
    console.print(diag_table)

    # Option Legs Table
    legs_table = Table(title=f"📋 Option Legs ({len(strat.legs)} Legs)", show_header=True, header_style="bold green")
    legs_table.add_column("Action", style="bold", justify="center")
    legs_table.add_column("Contract Symbol", style="white")
    legs_table.add_column("Type", justify="center")
    legs_table.add_column("Strike", justify="right")
    legs_table.add_column("Expiry", justify="center")
    legs_table.add_column("Delta (Δ)", justify="right")
    legs_table.add_column("Bid / Ask", justify="center")
    legs_table.add_column("Exec Price", justify="right", style="bold yellow")

    for leg in strat.legs:
        act_style = "bold green" if leg.action == "BUY" else "bold red"
        bid_str = f"{leg.bid:.1f}" if leg.bid is not None else "-"
        ask_str = f"{leg.ask:.1f}" if leg.ask is not None else "-"
        quotes = f"{bid_str} / {ask_str}"
        type_style = "green" if leg.contract_type == "CALL" else "magenta"

        legs_table.add_row(
            Text(leg.action, style=act_style),
            leg.symbol,
            Text(leg.contract_type, style=type_style),
            f"${leg.strike:,.0f}",
            leg.expiry,
            f"{leg.delta:+.3f}",
            quotes,
            f"${leg.entry_price:.2f}"
        )

    console.print(legs_table)

    # Payoff and Greeks Table
    payoff_table = Table(title="💰 Financial Metrics & Position Greeks", show_header=True, header_style="bold blue")
    payoff_table.add_column("Metric", style="cyan", width=24)
    payoff_table.add_column("Value", style="bold white")

    payoff_table.add_row("Net Premium (Cost)", f"${strat.net_premium:.2f} per ETH ({strat.strategy_type})")
    payoff_table.add_row("Max Profit Potential", f"${strat.max_profit:.2f} per ETH")
    payoff_table.add_row("Max Defined Risk / Loss", f"${strat.max_loss:.2f} per ETH")
    payoff_table.add_row("Risk / Reward Ratio", strat.risk_reward)
    be_str = ", ".join(f"${b:,.2f}" for b in strat.breakevens) if strat.breakevens else "N/A"
    payoff_table.add_row("Breakeven Price(s)", be_str)
    payoff_table.add_row(
        "Net Position Greeks",
        f"Delta: {strat.net_delta:+.3f}  |  Theta: ${strat.net_theta:+.2f}/day  |  Vega: ${strat.net_vega:+.2f}"
    )

    console.print(payoff_table)
    console.print()
