"""
Option Chain Selector and Strike Matcher for Delta Exchange ETH contracts.
Finds contracts based on target Delta, expiration date, and executable bid/ask quotes.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from strategy.option_models import OptionLeg


def extract_expiry_from_symbol(symbol: str) -> str:
    """
    Extracts date string from Delta symbol (e.g. 'C-ETH-2750-021026' -> '021026').
    """
    parts = symbol.split("-")
    if len(parts) >= 4:
        return parts[3]
    return "UNKNOWN"


def filter_by_optimal_expiry(
    options: List[Dict[str, Any]],
    preference: str = "nearest"
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Groups options by expiration date and selects the target expiry.
    Default selects the nearest active expiry date with liquid contracts.
    """
    if not options:
        return "", []

    by_expiry: Dict[str, List[Dict[str, Any]]] = {}
    for opt in options:
        sym = opt.get("symbol", "")
        exp = extract_expiry_from_symbol(sym)
        if exp not in by_expiry:
            by_expiry[exp] = []
        by_expiry[exp].append(opt)

    sorted_expiries = sorted(by_expiry.keys())

    if preference == "nearest" or not sorted_expiries:
        target_expiry = sorted_expiries[0] if sorted_expiries else ""
    elif preference == "weekly" and len(sorted_expiries) > 1:
        target_expiry = sorted_expiries[1]
    else:
        target_expiry = sorted_expiries[0]

    return target_expiry, by_expiry.get(target_expiry, [])


def find_option_by_delta(
    options: List[Dict[str, Any]],
    contract_type: str,     # 'call_options' or 'put_options'
    target_delta: float,    # positive for call (e.g. 0.50), negative for put (e.g. -0.50)
    exclude_strikes: Optional[List[float]] = None
) -> Optional[Dict[str, Any]]:
    """
    Finds the contract whose Greek delta is closest to target_delta.
    """
    exclude = set(exclude_strikes or [])
    filtered = [
        opt for opt in options
        if opt.get("contract_type") == contract_type
        and float(opt.get("strike_price", 0)) not in exclude
    ]

    if not filtered:
        return None

    def delta_dist(item):
        g = item.get("greeks", {})
        d = float(g.get("delta", 0.0) or 0.0)
        return abs(d - target_delta)

    return min(filtered, key=delta_dist)


def build_option_leg(
    raw_opt: Dict[str, Any],
    action: str,            # "BUY" or "SELL"
    expiry: str,
    quantity: int = 1
) -> OptionLeg:
    """
    Converts a raw Delta Exchange option dictionary into a structured OptionLeg.
    """
    symbol = raw_opt.get("symbol", "")
    strike = float(raw_opt.get("strike_price", 0.0))
    ctype = "CALL" if raw_opt.get("contract_type") == "call_options" else "PUT"

    best_bid = raw_opt.get("best_bid")
    best_ask = raw_opt.get("best_ask")
    mark_price = float(raw_opt.get("mark_price", 0.0))
    mark_iv = float(raw_opt.get("mark_iv", 0.0) or 0.0)

    # Greeks
    g = raw_opt.get("greeks", {})
    delta = float(g.get("delta", 0.0) or 0.0)
    theta = float(g.get("theta", 0.0) or 0.0)
    vega = float(g.get("vega", 0.0) or 0.0)

    # Executable price
    if action == "BUY":
        if best_ask is not None and best_ask > 0:
            entry_price = float(best_ask)
        else:
            entry_price = round(mark_price * 1.01, 2)
    else:  # SELL
        if best_bid is not None and best_bid > 0:
            entry_price = float(best_bid)
        else:
            entry_price = round(mark_price * 0.99, 2)

    return OptionLeg(
        symbol=symbol,
        action=action,
        contract_type=ctype,
        strike=strike,
        expiry=expiry,
        bid=best_bid,
        ask=best_ask,
        mark_price=round(mark_price, 2),
        entry_price=round(entry_price, 2),
        delta=round(delta, 4),
        theta=round(theta, 4),
        vega=round(vega, 4),
        iv=round(mark_iv * 100.0, 2),
        quantity=quantity
    )
