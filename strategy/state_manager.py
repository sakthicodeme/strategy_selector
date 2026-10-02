"""
State manager for tracking indicator trends and strategy changes between runs.
Enables alerting only when the trend flips (e.g. Bullish -> Bearish) to avoid Telegram spam.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "state.json")


class StateManager:
    def __init__(self, state_file: str = DEFAULT_STATE_FILE):
        self.state_file = state_file

    def load_state(self) -> Dict[str, Any]:
        """Loads previous state from disk."""
        if not os.path.exists(self.state_file):
            return {}
        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read state file {self.state_file}: {e}")
            return {}

    def save_state(
        self,
        trend_direction: int,
        trend_label: str,
        strategy_name: str,
        underlying_price: float,
        supertrend_line: float
    ):
        """Saves current state to disk."""
        state = {
            "last_trend_direction": trend_direction,
            "last_trend_label": trend_label,
            "last_strategy_name": strategy_name,
            "last_underlying_price": underlying_price,
            "last_supertrend_line": supertrend_line,
            "updated_at": datetime.utcnow().isoformat()
        }
        try:
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write state file {self.state_file}: {e}")

    def check_trend_change(self, current_direction: int, current_strategy: str) -> Dict[str, Any]:
        """
        Compares current run with previous state.
        Returns whether trend or strategy has flipped.
        """
        prev = self.load_state()
        if not prev:
            # First run: treated as initialization
            return {
                "is_first_run": True,
                "trend_changed": True,
                "strategy_changed": True,
                "prev_trend": None,
                "current_trend": "BULLISH" if current_direction == 1 else "BEARISH"
            }

        prev_dir = prev.get("last_trend_direction")
        prev_label = prev.get("last_trend_label")
        prev_strat = prev.get("last_strategy_name")

        trend_changed = (prev_dir is not None and prev_dir != current_direction)
        strategy_changed = (prev_strat is not None and prev_strat != current_strategy)

        return {
            "is_first_run": False,
            "trend_changed": trend_changed,
            "strategy_changed": strategy_changed,
            "prev_trend": prev_label,
            "current_trend": "BULLISH" if current_direction == 1 else "BEARISH",
            "prev_strategy": prev_strat,
            "current_strategy": current_strategy
        }
