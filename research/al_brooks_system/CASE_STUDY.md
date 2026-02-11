# Case Study: Al Brooks Second-Entry Strategy
## From Broken Backtest to Walk-Forward Validated Edge

---

### The Challenge

A trader came to us with an Al Brooks-inspired price action strategy for MNQ (Micro Nasdaq) futures on 5-minute bars. The strategy was built around **second-entry patterns** (H2/L2) — a well-known concept from Al Brooks' price action methodology where you wait for a pullback, a failed first entry, and then take the second attempt in the direction of the trend.

The problem? **The strategy didn't work.** An initial backtest showed just 52 trades over 6 months with inconsistent results. On the full MNQ dataset (2019-2026), it was barely breaking even with a profit factor of 0.88 — meaning it was actually *losing* money.

The trader had already run 252 parameter combinations trying to optimize it. Nothing worked. They were ready to abandon the idea entirely.

---

### What We Found: Three Critical Bugs

Before touching a single parameter, we audited the code. What we found was striking — the strategy had **three fundamental bugs** that were sabotaging it from the inside:

**Bug #1: Everything Was "Sideways"**
The trend detection system was supposed to classify the market as trending up, trending down, or sideways. Instead, due to a mathematical error in how it compared price ranges to volatility, it classified **virtually every bar as sideways**. The strategy could never identify a trend, which meant it could never take with-trend entries — the entire foundation of the Al Brooks approach.

**Bug #2: The Circuit Breaker Never Reset**
The strategy had a safety mechanism: after 4 consecutive losing trades, stop trading for the day. Good idea — except the daily reset was comparing the wrong timestamps. It was checking the current bar against the previous raw data bar (which was often from the same calendar date but a different session), so it thought every bar was the same day. After 4 losses early in the dataset, the circuit breaker engaged and **the strategy permanently stopped trading**. On 470,000 bars of data spanning 7 years, it produced just 19 trades.

**Bug #3: Losses Were 2-3x Larger Than Wins**
Stop losses were placed at the signal bar's extreme, which could be 30+ ticks away. But targets were fixed at just 8 ticks. The risk-reward ratio was inverted — the strategy was risking $15 to make $4.

These bugs had nothing to do with the trader's idea being bad. The *concept* was sound. The *implementation* was broken.

---

### The Rebuild: V2 Strategy Engine

We rebuilt the strategy from scratch, keeping the core Al Brooks methodology but fixing the infrastructure:

- **Trend detection**: Replaced the broken range-based classifier with a normalized EMA slope approach. Now the strategy correctly identifies uptrends, downtrends, and sideways markets.
- **Circuit breakers**: Fixed the daily reset to properly track RTH (Regular Trading Hours) session boundaries.
- **Risk management**: Added ATR-capped stops (no stop wider than 1.5x the Average True Range) and R:R-based targets (target = risk x reward ratio).
- **Pattern state machines**: Separated H2 (long) and L2 (short) tracking into independent state machines so they don't interfere with each other.

First run of the rebuilt engine: **14,477 trades with a profit factor of 0.94.** Not profitable yet, but a massive improvement — we went from 19 trades to 14,000. The plumbing worked. Now we could actually *research* the strategy.

---

### The Research: Finding Where the Edge Lives

With a working engine, we ran deep diagnostics on every dimension of the strategy:

**Time of Day Analysis**
- The 8:30-9:00 AM open was toxic (profit factor 0.74). Too much noise and whipsaw.
- The core trading hours (9:00-14:00) held the edge.

**Pattern Analysis**
- H2 (second entry long) in uptrends: **profit factor 1.18** — real edge.
- L2 (second entry short) in downtrends: profit factor 0.97 — breakeven.
- Sideways entries: profit factor 0.78 — net negative.
- The edge was concentrated in **one specific pattern in one specific context**: H2 longs in confirmed uptrends.

**Trade Duration Analysis**
- 1-bar trades (stopped out immediately): profit factor 0.62 — disaster.
- 3-5 bar trades: profit factor 1.18 — solid.
- 6+ bar trades: profit factor 1.70 — the strategy's best work needed *time* to develop.

This last finding was the key insight: **the strategy's entries were good, but the exits were killing it.** Trades that survived the initial noise after entry went on to be highly profitable. Trades that got stopped out in the first few bars were overwhelmingly losers — not because the trade idea was wrong, but because normal market noise was triggering the stops prematurely.

---

### The Breakthrough: Grace Period + Trailing Stop

Armed with the diagnostic data, we tested a simple but powerful idea: **what if we don't check the stop for the first few bars after entry?**

The logic: Al Brooks second-entry patterns identify a spot where the market is likely to resume its trend. But right after entry, there's often one last wave of counter-trend pressure — the same selling that created the pullback in the first place. A tight stop gets hunted. A patient stop survives.

We called this the **grace period** — a configurable number of bars after entry where the stop is not active. After the grace period, we activate an ATR-based trailing stop that follows the trade as it moves in our favor.

The results across our systematic sweep were dramatic:

| Configuration | Profit Factor | Win Rate | Trades/Day |
|---|---|---|---|
| Baseline (no grace, fixed target) | 1.18 | 38% | 2.0 |
| 3-bar grace, fixed target | 1.48 | 55% | 2.0 |
| 3-bar grace + ATR trail | 2.11 | 63% | 2.0 |
| 5-bar grace + ATR trail | 2.88 | 70% | 2.0 |
| **7-bar grace + ATR trail** | **3.18** | **74%** | **2.0** |

The profit factor went from 1.18 to 3.18 — **a 2.7x improvement** — without changing the entry logic at all. Same patterns, same trend detection, same signal bar quality filter. The only change was *how we managed the trade after entry*.

---

### Validation: Is It Real?

A backtest result means nothing if it's overfit to historical data. We subjected the best configuration to rigorous out-of-sample testing:

**Split-Sample Test (Train on 2019-2022, Test on 2023-2026)**

| Period | Profit Factor | Win Rate | Trades |
|---|---|---|---|
| Training (2019-2022) | 2.98 | 72.7% | 1,367 |
| **Testing (2023-2026)** | **3.35** | **75.3%** | **1,167** |

The strategy performed *better* out of sample than in sample. This is rare and suggests a genuine, robust edge rather than curve-fitting.

**Walk-Forward Validation (4 rolling 2-year folds)**

| In-Sample Period | Out-of-Sample Period | OOS Profit Factor |
|---|---|---|
| 2019-2020 | 2021-2022 | 2.72 |
| 2020-2021 | 2022-2023 | 2.89 |
| 2021-2022 | 2023-2024 | 3.54 |
| 2023-2024 | 2025-2026 | 3.10 |

**Every single out-of-sample fold was profitable** with a minimum profit factor of 2.72. The average out-of-sample profit factor was 3.06.

---

### Year-by-Year Performance

The best configuration produced consistent results across all market regimes — the post-COVID recovery, the 2022 bear market, and the 2023-2025 bull run:

| Year | Trades | Win Rate | Profit Factor | Net P&L | Max Drawdown |
|---|---|---|---|---|---|
| 2019 | 255 | 66.7% | 2.91 | $2,471 | -$234 |
| 2020 | 420 | 74.3% | 3.76 | $10,395 | -$262 |
| 2021 | 372 | 75.5% | 3.44 | $8,566 | -$638 |
| 2022 | 321 | 72.3% | 2.41 | $9,943 | -$909 |
| 2023 | 409 | 75.6% | 3.72 | $11,342 | -$462 |
| 2024 | 357 | 75.1% | 3.39 | $11,382 | -$634 |
| 2025 | 384 | 74.5% | 3.01 | $13,866 | -$1,446 |

**Seven consecutive profitable years.** Total net P&L of $68,727 on a single MNQ contract ($50 day-trade margin). Maximum drawdown of $1,446.

---

### Delivered to the Trader

The final deliverables included:

1. **Complete Python backtesting engine** with all V2-V6 research iterations
2. **Walk-forward validation report** proving out-of-sample robustness
3. **NinjaTrader 8 C# strategy** ready to load into Strategy Analyzer or deploy live
4. **All parameters exposed** as NinjaTrader properties so the trader can experiment without touching code
5. **Full sweep results** (JSON) for every configuration tested, so the trader can see the entire research landscape

The trader went from a broken strategy they were about to abandon to a walk-forward validated system with a 3.18 profit factor, ready for NinjaTrader paper trading.

---

### Key Takeaways

**The strategy idea was never the problem.** Al Brooks' second-entry methodology has real edge in trending markets. The problems were all in the implementation — bugs that silently destroyed performance, and exit management that didn't match the entry thesis.

**Diagnostics before optimization.** We didn't start by tweaking parameters. We started by auditing the code and understanding *why* trades were losing. The data told us exactly where the edge was (H2 longs in uptrends) and what was killing it (premature stops in the first few bars).

**Exit management is everything.** The entire 2.7x improvement in profit factor came from changing how we managed trades *after* entry. The entries stayed the same. This is a common pattern — traders obsess over entries and neglect the exit strategy, which is often where the real alpha lives.

**Validation isn't optional.** A profit factor of 3.18 in-sample means nothing without out-of-sample confirmation. Our walk-forward testing showed the edge holds across multiple time periods and market regimes, giving the trader real confidence to move forward.

---

*This case study represents actual research performed on historical MNQ futures data (May 2019 - January 2026). Past performance does not guarantee future results. All trading involves risk. The profit/loss figures shown are based on backtesting with a single MNQ contract and do not account for commissions, slippage, or fees.*
