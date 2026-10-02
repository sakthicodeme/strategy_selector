# 🚀 ETHUSD Automatic Strategy Selection Project

An institutional-grade, automated options strategy selection system for **ETHUSD** on a **5-minute (5m)** timeframe, powered by **Delta.exchange** live market data.

The system combines **Supertrend**, **Cumulative Volume Delta (CVD)**, and **advanced volatility/trend filters (ADX, ATR% Percentile, and Implied Volatility)** to automatically determine market regime, select the mathematically optimal options strategy, price the option legs using live Delta Exchange order books, and dispatch formatted alert messages.

---

## 📌 Project Highlights

- **Underlying Asset**: `ETHUSD`
- **Timeframe**: `5m` (5-minute candlestick interval)
- **Data Provider**: **Delta.exchange** (`api.india.delta.exchange` and `api.delta.exchange`)
- **Key Indicators**:
  1. **Supertrend (10, 3.0)**: Directional trend filter with Wilder's ATR and trailing stops.
  2. **Cumulative Volume Delta (CVD)**: Aggressive buyer vs seller order flow aggression and divergence detection (absorption/exhaustion).
  3. **ADX Trend Strength Filter (Our Suggestion)**: Identifies trending vs range-bound chop to eliminate false breakouts.
  4. **Volatility Regime & IV Percentile (Our Suggestion)**: Categorizes volatility into High, Normal, or Low to choose between **Net Credit** (premium selling) and **Net Debit** (premium buying).
  5. **Session VWAP (Our Suggestion)**: Volume-Weighted Average Price anchor for mean-reversion boundaries.
- **Automatic Option Pricing**:
  - Automatically filters Delta Exchange option contracts for ETH.
  - Matches strikes dynamically based on Greek **Delta ($\Delta$)** targets ($50\Delta$ ATM, $25-35\Delta$ OTM, $10-15\Delta$ Wings).
  - Retrieves live `best_bid`, `best_ask`, `mark_price`, and option Greeks ($\Delta, \Theta, \mathcal{V}, \Gamma$).
  - Calculates net debit/credit, max profit, max risk, risk-reward ratio, and breakeven levels.
- **Multi-Channel Messaging**:
  - **Terminal / Console**: Styled dashboard via `rich` tables and status badges.
  - **Telegram Bot**: Ready-to-send HTML alert with monospace option leg table.
  - **Discord Webhook**: Color-coded Discord Embed card.
  - **Structured JSON**: For programmatic trading execution and API consumers.

---

## 🏛️ System Architecture

```
eth_strategy_selector/
├── .env.example                     # Environment configuration template
├── requirements.txt                 # Pinned dependencies
├── config.py                        # Central configuration dataclass
├── main.py                          # CLI runner, scheduler, and pipeline orchestrator
├── data/
│   ├── __init__.py
│   ├── delta_client.py              # Delta Exchange REST API client (candles, tickers, trades)
│   └── mock_data.py                 # Offline synthetic candle & option chain generator
├── indicators/
│   ├── __init__.py
│   ├── supertrend.py                # Supertrend calculation (Wilder ATR, trailing stop, trend flip)
│   ├── cvd.py                       # CVD calculation, slope, and divergence detection
│   └── regime.py                    # ADX, ATR% rank, IV percentile, and VWAP filter
├── strategy/
│   ├── __init__.py
│   ├── option_models.py             # OptionLeg and SelectedStrategy dataclasses & payoff math
│   ├── option_pricer.py             # Delta Exchange strike matcher and leg builder
│   └── selector.py                  # Decision matrix engine (Regime -> Strategy mapping)
├── messaging/
│   ├── __init__.py
│   ├── formatter.py                 # Text, HTML, and JSON formatters
│   ├── console_printer.py           # Rich terminal UI dashboard
│   ├── telegram_notifier.py         # Telegram bot message dispatcher
│   └── discord_notifier.py          # Discord webhook notifier
└── tests/
    ├── __init__.py
    └── test_strategy_selector.py    # Comprehensive test suite
```

---

## 🧠 Decision Matrix: Strategy Selection Rules

| Market Condition | Supertrend | CVD Order Flow | Volatility Regime (IV / ATR) | Trend Strength (ADX) | Selected Strategy | Recommended Option Legs |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **Bullish Absorption Reversal** | Any / Bearish | **Bullish Divergence** | Any | Any | **Bull Call Spread** | Buy $50\Delta$ Call, Sell $25\Delta$ Call |
| **Bearish Exhaustion Reversal** | Any / Bullish | **Bearish Divergence** | Any | Any | **Bear Put Spread** | Buy $-50\Delta$ Put, Sell $-25\Delta$ Put |
| **Strong Bullish (Normal/Low Vol)** | Bullish (+1) | Rising (Accumulation) | Low / Normal | Strong ($\text{ADX} \ge 22$) | **Bull Call Spread (Debit)** | Buy $50\Delta$ Call, Sell $25\Delta$ Call |
| **Strong Bullish (High Vol)** | Bullish (+1) | Rising (Accumulation) | High ($\ge 60\text{th pct}$) | Strong ($\text{ADX} \ge 22$) | **Bull Put Spread (Credit)** | Sell $-35\Delta$ Put, Buy $-15\Delta$ Put |
| **Strong Bearish (Normal/Low Vol)** | Bearish (-1) | Falling (Distribution) | Low / Normal | Strong ($\text{ADX} \ge 22$) | **Bear Put Spread (Debit)** | Buy $-50\Delta$ Put, Sell $-25\Delta$ Put |
| **Strong Bearish (High Vol)** | Bearish (-1) | Falling (Distribution) | High ($\ge 60\text{th pct}$) | Strong ($\text{ADX} \ge 22$) | **Bear Call Spread (Credit)** | Sell $35\Delta$ Call, Buy $15\Delta$ Call |
| **Range-Bound / Low ADX** | Any / Neutral | Flat / Mixed | Normal / High | Weak ($\text{ADX} < 22$) | **Iron Condor (Credit)** | Sell $20\Delta$ Call/Put + Buy $10\Delta$ Wings |
| **Volatility Squeeze / Compression** | Consolidating | Compressed | Low ($< 35\text{th pct}$) | Weak ($\text{ADX} < 18$) | **Long Straddle (Breakout)** | Buy $50\Delta$ Call + Buy $-50\Delta$ Put |

---

## ⚙️ Installation & Setup

### 1. Set Active Workspace
If you are running in the terminal:
```bash
cd /Users/sakthivel/.gemini/antigravity/scratch/eth_strategy_selector
```

### 2. Activate Virtual Environment & Install Dependencies
The project uses its isolated virtual environment:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables (Optional)
Copy `.env.example` to `.env` if you want to configure custom settings or messaging tokens:
```bash
cp .env.example .env
```
Inside `.env`, you can set:
- `EXCHANGE_ENV=india` (or `global`)
- `TELEGRAM_BOT_TOKEN=<your_token>`
- `TELEGRAM_CHAT_ID=<your_chat_id>`
- `DISCORD_WEBHOOK_URL=<your_webhook_url>`

---

## 💻 CLI Usage Guide

### 1. Run Live Market Strategy Selection
Fetches live ETHUSD 5m candles, mark price, and live options order book from Delta Exchange India:
```bash
./.venv/bin/python main.py
```
Or for Delta Global:
```bash
./.venv/bin/python main.py --exchange global
```

### 2. Run with Different Output Formats
- **Rich Terminal UI (Default)**:
  ```bash
  ./.venv/bin/python main.py --output console
  ```
- **Clean Markdown / Plain Text**:
  ```bash
  ./.venv/bin/python main.py --output text
  ```
- **Machine-Readable JSON**:
  ```bash
  ./.venv/bin/python main.py --output json
  ```

### 3. Simulate Market Regimes (Mock Mode)
Test the selector under synthetic market conditions without external API calls:
```bash
./.venv/bin/python main.py --mock --regime bullish
./.venv/bin/python main.py --mock --regime bearish
./.venv/bin/python main.py --mock --regime ranging
./.venv/bin/python main.py --mock --regime divergence
```

### 4. Dispatch Alerts to Telegram / Discord
```bash
./.venv/bin/python main.py --send-telegram --send-discord
```

### 5. Run Continuous 5m Monitor
Runs automatically on every 5-minute candle close:
```bash
./.venv/bin/python main.py --watch --interval 300
```

---

## 🧪 Running the Test Suite

Run the unit and integration tests:
```bash
./.venv/bin/python -m unittest discover -s tests
```

---

## 📬 Sample Strategy Message Output

```text
====================================================================
🎯 AUTOMATIC STRATEGY SELECTION REPORT: ETHUSD (5m)
⏰ Timestamp: 2026-10-02 13:17:42 UTC
💵 Underlying Mark Price: $2,749.61
====================================================================

📊 MARKET REGIME & SIGNALS:
  • Supertrend (10, 3.0): BULLISH (Stop: $2,738.17, Dist: +0.41%)
  • CVD (Cumulative Delta): FALLING (Delta: +11851.9 ETH, Div: BEARISH_DIVERGENCE)
  • Volatility & ADX:     WEAK_RANGE | ADX: 13.1 | HIGH_VOLATILITY

🚀 SELECTED STRATEGY:  BEAR PUT SPREAD (NET_DEBIT)
🧭 Market Bias:        BEARISH (Exhaustion Reversal)
💡 Strategy Rationale: Bearish CVD Exhaustion detected! Price pushed higher but
                       CVD failed to confirm (lower high). Selecting Bear Put Spread
                       to capture impending downward mean-reversion.

📋 RECOMMENDED OPTION LEGS (Delta.exchange):
--------------------------------------------------------------------
ACTION SYMBOL                 TYPE  STRIKE   DELTA   BID/ASK      MARK
--------------------------------------------------------------------
BUY    P-ETH-2750-031026      PUT   $2750    -0.491  22.8/23.3    $23.30
SELL   P-ETH-2710-031026      PUT   $2710    -0.235  7.9/8.2      $7.90
--------------------------------------------------------------------

💰 FINANCIAL METRICS & PAYOFF (Per ETH):
  • Net Strategy Cost:  $15.40 (NET_DEBIT)
  • Max Profit:         $24.60
  • Max Loss:           $15.40
  • Risk / Reward:      1 : 1.60
  • Breakeven Point(s): $2,734.60

⚡ NET POSITION GREEKS:
  • Net Delta: -0.255  |  Net Theta: $-2.97/day  |  Net Vega: $+0.13
====================================================================
```
