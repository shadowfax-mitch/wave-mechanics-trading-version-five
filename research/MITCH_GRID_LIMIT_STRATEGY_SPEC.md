# Mitch Grid Limit Strategy — Final Specification

**Created:** 2026-02-08
**Instrument:** MNQ (Micro E-mini Nasdaq-100 Futures), 5-minute bars
**Backtest Period:** 2019-05-05 to 2026-01-12 (6.69 years, ~470K bars)
**Status:** Research complete. Ready for NinjaTrader port.

---

## Performance Summary

| Metric | Value |
|--------|-------|
| Total Trades | 479 |
| Trades/Year | 72 |
| Trades/Day | 0.28 |
| Win Rate | 33.6% |
| Profit Factor | 1.33 |
| Total P&L | +$3,014 |
| Annual P&L | +$451 |
| Sharpe Ratio | 0.08 |
| Max Drawdown | $673 |
| Avg Bars Held | 20.7 (1h 43m at 5-min) |
| Avg Win | ~$22 (trail stop exits) |
| Avg Loss | ~-$36 (initial stop exits) |

### Exit Breakdown
| Exit Type | Count | % | Avg P&L |
|-----------|-------|---|---------|
| TRAIL_STOP | 278 | 58% | +$22.30 |
| STOP | 188 | 39% | -$35.60 |
| TIME | 13 | 3% | +$269.00 |

---

## Strategy Architecture

Three layers working in series:

```
Signal Generation → Grid Filter → Limit Order Entry → Trail-Only Exit
```

### Layer 1: Trend Structure Detection

Classifies market trend from swing point sequences using Al Brooks methodology.

**Swing Detection:**
- Swing strength = 2 (bar must be highest/lowest within +/- 2 bars)
- Confirmation delay: swing is confirmed `strength` bars after the actual pivot
- No look-ahead bias — swing at bar `i` is only visible at bar `i + strength`

**Trend Classification:**
- Track last 2 swing highs and last 2 swing lows
- `TREND_UP`: Higher High + Higher Low (most recent swing high > prior, most recent swing low > prior)
- `TREND_DOWN`: Lower High + Lower Low
- `TREND_RANGE`: Mixed (e.g. HH + LL, or LH + HL)
- `TREND_UNKNOWN`: Fewer than 2 swings of each type observed
- EMA confirmation is **disabled** (set `use_ema_confirmation: False`)

### Layer 2: Pullback Entry Signals

Counts pullbacks within a confirmed trend to generate entry signals.

**Long Signal (in TREND_UP):**
1. A new Higher High is confirmed → reset pullback counter
2. Count subsequent confirmed swing lows as pullbacks
3. First swing low = 1st entry signal (tagged `entry_type=1`)
4. Second swing low = 2nd entry signal (tagged `entry_type=2`, then counter is consumed)
5. Wait for next HH to restart the count

**Short Signal (in TREND_DOWN):**
- Mirror logic: new Lower Low resets counter, count swing highs as pullbacks
- 1st and 2nd pullback highs generate short signals

**Both first and second entries are traded.** Research showed neither consistently outperforms the other; the grid filter determines which have edge, not the entry number.

**Stop Level (set at signal time):**
- Below/above the swing point that triggered the signal
- Buffer: 1.5 x ATR(14)
- Cap: 2.0 x ATR(14) max distance from swing price

### Layer 3: Grid Probability Filter

Only trade signals that fall in historically validated grid cells. Cells are defined by market conditions at signal time.

**Grid Dimensions (Ultra mode, 4 axes):**

1. **EMA Distance** — how far price is from EMA(21), measured in ATR units:
   - `ema<-2`: price more than 2 ATR below EMA (extended bearish)
   - `ema-2..-1`: 1-2 ATR below
   - `ema-1..0`: 0-1 ATR below
   - `ema0..1`: 0-1 ATR above
   - `ema1..2`: 1-2 ATR above
   - `ema>2`: more than 2 ATR above EMA (extended bullish)

2. **Time of Day** (Central Time):
   - `open`: 8:30 - 9:30
   - `morning`: 9:30 - 12:00
   - `afternoon`: 12:00 - 15:00

3. **Direction**: `LONG` or `SHORT`

4. **Volatility Regime** — current ATR(14) / 50-bar rolling mean ATR:
   - `low_vol`: ratio < 0.9
   - `norm_vol`: ratio 0.9 - 1.2
   - `high_vol`: ratio >= 1.2

**Stable Ultra Cells (8 cells, split-half validated):**

These cells were profitable in BOTH the first half (2019-2022) and second half (2022-2026) of the dataset independently:

```
LONG:
  ema0..1|morning|LONG|norm_vol
  ema0..1|afternoon|LONG|norm_vol
  ema>2|open|LONG|high_vol
  ema>2|afternoon|LONG|low_vol

SHORT:
  ema<-2|open|SHORT|high_vol
  ema<-2|morning|SHORT|high_vol
  ema-2..-1|afternoon|SHORT|norm_vol
  ema-1..0|morning|SHORT|norm_vol
```

**Interpretation:** The edge is strongest when trading WITH the EMA extension during high or normal volatility. Short signals perform best when price is well below the EMA (bearish extension), long signals when at or above. The `open` session (8:30-9:30) is only viable during high-vol conditions with extreme EMA distance.

### Layer 4: Limit Order Entry

Instead of market-ordering at the next bar's open, place a limit order at the swing price level that generated the signal.

**Mechanics:**
- Signal fires on bar `i` (swing confirmed at bar `i`)
- Limit order placed at bar `i+1` at the swing price level:
  - Long signal → buy limit at the confirmed swing low price
  - Short signal → sell limit at the confirmed swing high price
- Order fills when the bar's wick reaches the limit price:
  - Long: fills if `low[bar] <= limit_price`
  - Short: fills if `high[bar] >= limit_price`
- Fill price = limit price exactly (no slippage on limit fills)
- **Timeout: 5 bars** — if unfilled after 5 bars, order is cancelled
- New signal replaces any existing pending order

**Why limit orders work here:**
- Better entry: filled at the structure level, not chasing the move
- Zero entry slippage (vs $2.00/side on market orders)
- Natural quality filter: ~38% fill rate means 62% of signals where price runs away are automatically skipped
- Avg stop loss reduced from ~$68 (market) to ~$36 (limit) because entries are closer to the stop level

### Layer 5: Trail-Only Exit

No fixed profit target. Positions are managed entirely by a structure-based trailing stop.

**Trail Stop Mechanics:**
1. **Initial stop:** set at signal time (swing point - 1.5 ATR buffer)
2. **Breakeven move:** when a new favorable swing forms beyond entry price, move stop to breakeven
   - Long: first swing low above entry → stop moves to entry price
   - Short: first swing high below entry → stop moves to entry price
3. **Trailing:** on each subsequent favorable swing, trail the stop to `swing_price - 0.8 ATR` (long) or `swing_price + 0.8 ATR` (short)
   - Trail only ratchets in the favorable direction (never widens)
4. **Time exit:** close at market after 90 bars (7.5 hours) if still open

**Why trail-only (no fixed target):**
- Research showed fixed targets cap winners while stops still take full losses
- Trail-only: PF 0.85 vs hybrid trail+target: PF 0.57
- The rare TIME exits (3% of trades) average +$269 — these are the big runners that a fixed target would have cut short

---

## Optimal Parameters

```python
{
    # Indicators
    'swing_strength': 2,
    'atr_period': 14,
    'ema_period': 21,
    'use_ema_confirmation': False,

    # Entry
    'track_first_entries': True,       # trade both 1st and 2nd entries
    'order_timeout': 5,                # limit order expires after 5 bars
    'slippage': 0.0,                   # no slippage on limit fills
    'commission': 2.0,                 # $2.00 round-trip

    # Stop
    'stop_buffer_atr': 1.5,            # stop distance from swing point
    'max_stop_atr': 2.0,               # max stop distance cap

    # Target (unused in trail-only, but kept for measured move calc)
    'target_atr_fallback': 3.0,
    'measured_move_cap_atr': 8.0,

    # Exit
    'trail_only': True,                # no fixed target
    'trail_buffer_atr': 0.8,           # trail stop buffer from swing
    'use_breakeven': True,             # move to BE on first favorable swing
    'max_hold': 90,                    # time exit after 90 bars (7.5h)

    # Risk
    'max_daily_loss': -200,            # circuit breaker: stop trading after -$200/day
    'max_consec_losses': 3,            # circuit breaker: pause after 3 consecutive losses

    # Session
    'rth_start': 8.5,                  # 8:30 AM CT
    'rth_end': 15.0,                   # 3:00 PM CT
    'point_value': 1.0,                # per-point P&L ($0.50 real MNQ, use 1.0 for backtest)
}
```

---

## Grid Cell Detail (Ultra mode, per-cell backtest)

| Cell | N | WR | PF | PnL |
|------|---|----|----|-----|
| ema<-2\|morning\|SHORT\|high_vol | 15 | 53.3% | 3.22 | +$629 |
| ema>2\|open\|LONG\|high_vol | 38 | 36.8% | 1.69 | +$689 |
| ema0..1\|afternoon\|LONG\|norm_vol | 115 | 36.5% | 1.38 | +$655 |
| ema<-2\|open\|SHORT\|high_vol | 26 | 38.5% | 1.35 | +$228 |
| ema0..1\|morning\|LONG\|norm_vol | 104 | 33.7% | 1.25 | +$494 |
| ema-2..-1\|afternoon\|SHORT\|norm_vol | 62 | 30.6% | 1.21 | +$234 |
| ema>2\|afternoon\|LONG\|low_vol | 28 | 28.6% | 1.18 | +$67 |
| ema-1..0\|morning\|SHORT\|norm_vol | 91 | 26.4% | 1.02 | +$18 |

---

## Research Journey & Key Findings

### What was tested and rejected

1. **Second entries only:** 0 of 72 parameter configs showed 2nd entry beating 1st. Second entries are too rare (5% of signals) because trend often shifts during the pullback sequence.

2. **Fixed targets:** Any fixed target (1x-4x ATR) caps the big winners. Trail-only lets winners run and was the single biggest improvement (PF 0.57 → 0.85).

3. **EMA confirmation for trend:** Demoting trend to RANGE when close is against EMA kills too many valid signals. Turned off.

4. **Tight stops (0.5 ATR buffer):** Get stopped out by noise. 1.5 ATR buffer dramatically outperforms 0.5 ATR.

5. **Market order entries:** Market orders at next bar's open chase the move and suffer slippage. Limit orders at structure levels were the breakthrough that pushed PF from 1.04 to 1.33.

6. **More grid cells (10 cells):** Adding 4 extra cells (ALL_PROFITABLE_FINE) nearly doubled trade count (167/yr) but diluted PF to 1.10. Not worth it.

7. **Longer timeouts:** timeout=10 gets 90 trades/yr at PF=1.18 — marginal improvement in sample size at cost to quality.

8. **MES data:** Same cells/params on MES: PF=0.62. Grid cells were mined on MNQ — they don't transfer. The strategy is instrument-specific.

9. **No grid filter:** Limit orders alone aren't enough — PF=0.96, net negative. The grid filter is doing real work.

### The retroactive bucketing trap

Early diagnostic analysis showed PF=1.81 for stable ultra cells. This was retroactive: tagging trades from an unfiltered backtest by their grid cell. Production proactive filtering showed PF=1.04 (market orders) because filtering changes position capacity — signals previously blocked by bad-cell trades now fire, diluting quality. Limit orders partially solve this by adding a second filter layer.

---

## Implementation Checklist (NinjaTrader C# Port)

### Data Structures
- [ ] Swing detection with confirmation delay (shift by `strength` bars)
- [ ] Rolling ATR(14) — simple average of true range
- [ ] EMA(21)
- [ ] 50-bar rolling mean of ATR (for volatility regime classification)
- [ ] Trend state machine (HH/HL/LH/LL tracking)
- [ ] Pullback counter per direction

### Entry Logic
- [ ] Signal generation on confirmed swing in trend
- [ ] Grid cell classification (EMA bucket + TOD + direction + vol regime)
- [ ] Grid filter against 8 hardcoded cells
- [ ] Place limit order at swing price
- [ ] 5-bar timeout on unfilled orders
- [ ] New signal replaces existing pending order

### Exit Logic
- [ ] Initial stop from signal (swing - 1.5 ATR, capped at 2.0 ATR)
- [ ] Breakeven move on first favorable swing beyond entry
- [ ] Trailing stop ratchet on subsequent favorable swings (swing - 0.8 ATR)
- [ ] Time exit at 90 bars
- [ ] No fixed profit target

### Risk Management
- [ ] RTH filter: only trade 8:30-15:00 CT
- [ ] Daily P&L circuit breaker: -$200
- [ ] Consecutive loss circuit breaker: 3 losses
- [ ] Both circuit breakers reset at start of each trading day
- [ ] Single position only (no pyramiding)

### Validation
- [ ] Compare first 100 trades between C# and Python backtests
- [ ] Verify swing detection matches (confirmation delay is the common bug)
- [ ] Verify grid cell classification matches
- [ ] Verify limit order fill logic matches (wick-based)
- [ ] Check that trailing stop only ratchets forward, never backward

---

## Source Files

| File | Purpose |
|------|---------|
| `modules/mitch_l1l2_strategy.py` | Core: indicators, trend state machine, signal generation |
| `modules/mitch_grid_strategy.py` | Production: grid filter, limit order backtest, stable cells |
| `modules/run_mitch_grid_limit.py` | Market vs limit order comparison |
| `modules/run_mitch_freq_boost.py` | Frequency boost experiments (4 options) |
| `analysis/mitch_grid_limit_results.json` | Limit order backtest results |
| `analysis/mitch_freq_boost_results.json` | Frequency boost results |

---

## Realistic Expectations

This is a thin, selective strategy. The edge exists precisely because it's selective.

- ~72 trades/year = ~1 trade every 3-4 trading days
- 33.6% win rate means 2 out of 3 trades lose
- $451/year P&L on 1 MNQ contract ($0.50/point) = $226 real
- The strategy is best understood as a supplementary edge, not a standalone system
- Statistical confidence is limited: 479 trades over 6.69 years is a small sample
- Grid cells were mined from this dataset — forward performance will degrade
