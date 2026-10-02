"""
Telegram Notification Sender for Automatic Strategy Selection.
"""

import logging
import requests
from typing import Optional
from config import config
from strategy.option_models import SelectedStrategy
from messaging.formatter import format_strategy_telegram

logger = logging.getLogger(__name__)


def send_telegram_alert(
    strat: SelectedStrategy,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    trend_change_info: Optional[dict] = None
) -> bool:
    """
    Sends strategy message to Telegram bot.
    Returns True if sent successfully, False otherwise.
    """
    token = bot_token or config.TELEGRAM_BOT_TOKEN
    cid = chat_id or config.TELEGRAM_CHAT_ID

    if not token or not cid:
        logger.debug("Telegram credentials not configured. Skipping Telegram dispatch.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": cid,
        "text": format_strategy_telegram(strat, trend_change_info=trend_change_info),
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("ok"):
            logger.info(f"Telegram strategy alert delivered to chat {cid}.")
            return True
        logger.warning(f"Telegram API error: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.warning(f"Failed to send Telegram alert: {e}")

    return False
