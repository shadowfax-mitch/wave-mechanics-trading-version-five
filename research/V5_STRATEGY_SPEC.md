# V5 STRATEGY SPECIFICATION - Fractal Regime Reversion

**Created:** 2026-02-07 12:33 CT  
**Status:** DESIGN PHASE  
**Version:** 1.0

---

## 🎯 STRATEGY OVERVIEW

**Name:** Fractal Regime Reversion (FRR)

**Hypothesis:** Market structure at fractal swing extremes combined with statistical Z-score extremes (Z≥5.0) in high-volatility choppy regimes (R1) creates mean-reversion edge when filtered by wave direction alignment.

**Core Logic:** Enter mean-reversion trades at extreme price deviations from swing-point-anchored means when market structure indicates high-probability reversal conditions.

**Target Market:** MNQ/MES futures, 5-minute bars, RTH session (8:30 AM - 3:00 PM CT)

**Trade Frequency:** Low-frequency (expect 1-5 trades per week, not scalping)

**Risk Profile:** Conservative (1 contract, tight stops, circuit breakers)

---

## 📐 COMPONENT DEFINITIONS

### 1. Swing Points (Fractals) - V1 Heritage
**Purpose:** Structural anchors for price analysis (NOT indicators)

**Definition:**
- **Swing High:** Bar where High[0] > High[-1] AND High[0] > High[-2] AND High[0] > High[1] AND High[0] > High[2]
- **Swing Low:** Bar where Low[0] < Low[-1] AND Low[0] < Low[-2] AND Low[0] < Low[1] AND Low[0] < Low[2]

**Parameters:**
- `swing_strength`: 2 (fixed, standard fractal definition)

**Justification:** V1 used this exact definition. Fractals represent market structure turning points, not statistical artifacts.

---

### 2. Regime Classification (R1 High-Vol Chop) - V2 Heritage
**Purpose:** Identify market conditions where mean reversion has 86% WR

**Definition:**
- Calculate wave metrics over `regime_window` bars:
  - **Amplitude:** `(High - Low) / ATR(14)`
  - **Energy:** `Volume × |Close - Open|`
  - **Chop:** `1 - |Trend| where Trend = (Close - Open) / (High - Low)`

**R1 Regime Criteria:**
- Amplitude > `amp_threshold` (high volatility)
- Chop > `chop_threshold` (no clear trend)
- Energy > `energy_threshold` (sufficient participation)

**Parameters:**
- `regime_window`: 20 bars (rolling window for regime classification)
- `amp_threshold`: 1.5 (amplitude must exceed 1.5× ATR)
- `chop_threshold`: 0.6 (60%+ choppiness)
- `energy_threshold`: 50th percentile (median energy)

**Justification:** V2 validated R1 regime had 86% WR for mean reversion. These thresholds isolate that specific market structure.

---

### 3. Z-Score Extremes - V4 Heritage
**Purpose:** Identify statistical price deviations ripe for reversion

**Definition:**
- Calculate `EMA(Close, ema_period)` as mean
- Calculate `StdDev(Close, ema_period)` as standard deviation
- `Z-Score = (Close - EMA) / StdDev`

**Extreme Criteria:**
- **Overbought:** Z-Score ≥ `z_threshold` (default 5.0)
- **Oversold:** Z-Score ≤ `-z_threshold` (default -5.0)

**Parameters:**
- `ema_period`: 50 bars (adaptive mean)
- `z_threshold`: 5.0 (extreme deviation, V4's validated level)

**Justification:** V4 showed Z≥5.0 had positive results ($1,178 over 21 trades, 3.23 PF). 5-sigma events are rare and mean-reverting.

---

### 4. Wave Direction Filter - V1 Heritage
**Purpose:** Align entries with underlying wave structure (reduces false signals)

**Definition:**
- Calculate wave direction based on swing point sequence:
  - **Bullish Wave:** Most recent swing low is HIGHER than prior swing low
  - **Bearish Wave:** Most recent swing high is LOWER than prior swing high
  - **Neutral Wave:** No clear wave structure

**Entry Alignment:**
- **SHORT entries:** Only when Z-Score overbought AND bearish wave structure
- **LONG entries:** Only when Z-Score oversold AND bullish wave structure

**Parameters:**
- None (derived from swing points)

**Justification:** V1's wave direction reduced signal spam. Aligning mean reversion with wave structure improves win rate.

---

### 5. Circuit Breakers - V4 Heritage
**Purpose:** Prevent catastrophic losses (98.6% loss reduction in V4)

**Criteria:**
- **Daily Loss Limit:** -$200 (20 trades × $10 avg risk)
- **Max Position:** 1 contract (micro-live constraint)
- **Consecutive Losses:** 3 in a row = pause trading for rest of session

**Parameters:**
- `daily_loss_limit`: -200 (dollars)
- `max_consecutive_losses`: 3 (trades)

**Justification:** V4 proved circuit breakers work (-$1,539 → -$22). Non-negotiable safety net.

---

## 🎯 ENTRY RULES

### LONG Entry Conditions (ALL must be TRUE):
1. ✅ **Regime:** Currently in R1 (high-vol chop)
2. ✅ **Z-Score:** Close ≤ EMA - (5.0 × StdDev) [oversold]
3. ✅ **Wave Direction:** Bullish wave structure (higher swing lows)
4. ✅ **Swing Confirmation:** Current bar within 2 bars of recent swing low
5. ✅ **Circuit Breakers:** Not at daily loss limit, <3 consecutive losses

### SHORT Entry Conditions (ALL must be TRUE):
1. ✅ **Regime:** Currently in R1 (high-vol chop)
2. ✅ **Z-Score:** Close ≥ EMA + (5.0 × StdDev) [overbought]
3. ✅ **Wave Direction:** Bearish wave structure (lower swing highs)
4. ✅ **Swing Confirmation:** Current bar within 2 bars of recent swing high
5. ✅ **Circuit Breakers:** Not at daily loss limit, <3 consecutive losses

**Entry Execution:**
- Market order on next bar open (no limit orders)
- 1 contract only (per V5 Constitution)

---

## 🚪 EXIT RULES

### Profit Targets
- **Target 1:** EMA (mean reversion complete)
- **Target 2:** Opposite swing point (full structure reversal)

**Execution:** Exit at market when price crosses target

### Stop Loss
- **LONG Stop:** Swing low - (1.0 × ATR)
- **SHORT Stop:** Swing high + (1.0 × ATR)

**Justification:** Allow for volatility beyond swing point but prevent runaway losses

### Time-Based Exit
- **Max Hold Time:** 20 bars (100 minutes on 5-min chart)
- If neither target nor stop hit, exit at market after 20 bars

**Justification:** Mean reversion should happen quickly. Holding beyond 100 min indicates failed hypothesis.

### Regime Exit
- **Forced Exit:** If regime changes FROM R1 TO any other regime while in trade
- Execute at market immediately

**Justification:** Strategy edge is regime-specific. Exit when edge disappears.

---

## 📊 PARAMETER SUMMARY

| # | Parameter | Value | Range | Justification |
|---|-----------|-------|-------|---------------|
| 1 | `swing_strength` | 2 | Fixed | Standard fractal definition |
| 2 | `regime_window` | 20 | 15-30 | Regime assessment horizon |
| 3 | `amp_threshold` | 1.5 | 1.2-2.0 | High-vol identification |
| 4 | `chop_threshold` | 0.6 | 0.5-0.7 | Choppiness filter |
| 5 | `energy_threshold` | 50th pctl | 40-60th | Participation filter |
| 6 | `ema_period` | 50 | 30-100 | Adaptive mean window |
| 7 | `z_threshold` | 5.0 | 4.0-6.0 | Extreme deviation |
| 8 | `stop_atr_mult` | 1.0 | 0.5-2.0 | Stop distance |
| 9 | `max_hold_bars` | 20 | 10-30 | Time-based exit |
| 10 | `daily_loss_limit` | -200 | Fixed | Circuit breaker |

**Total Parameters:** 10 (exactly at V5 Constitution limit)

**Sensitivity Requirement:** ±20% change in any parameter should not break strategy profitability (to be validated in Phase 2).

---

## 🧪 THEORETICAL JUSTIFICATION

### Why This Should Work

**1. Structural Edge (Fractals)**
- Swing points represent actual market structure, not statistical smoothing
- Markets respect prior swing levels (support/resistance psychology)
- Fractals are objective (not subject to parameter tuning)

**2. Statistical Edge (Z-Score)**
- 5-sigma events are statistically rare (p < 0.0001)
- Price tends to revert to mean over time (statistical gravity)
- V4 validated Z≥5.0 had positive results

**3. Regime Edge (R1 High-Vol Chop)**
- V2 validated 86% WR in this specific regime
- High volatility creates large deviations (opportunity)
- Choppiness indicates no dominant trend (mean reversion favorable)

**4. Directional Edge (Wave Filter)**
- V1 showed wave direction reduces false signals
- Aligning with wave structure improves probability
- Prevents counter-trend trades in strong waves

**5. Risk Edge (Circuit Breakers)**
- V4 proved 98.6% loss reduction
- Prevents single-day disasters
- Allows strategy to "live to trade another day"

### Why This Might Fail

**1. Regime Rarity**
- R1 high-vol chop may be infrequent (low trade count)
- If regime occurs <20% of time, insufficient opportunities

**2. Execution Costs**
- Mean reversion requires tight stops (frequent small losses)
- Slippage + commissions may erode edge
- 1-contract trading has proportionally higher costs

**3. Regime Misclassification**
- If R1 identification is noisy, enter in wrong conditions
- V1's regime classifier was unvalidated (see system study)

**4. Overfitting to V2 Sample**
- 86% WR in R1 may be sample-specific
- Different data period might not replicate

**5. Compounding Filters**
- 5 entry conditions (regime + Z-score + wave + swing + circuit breakers)
- May filter out ALL trades (signal drought)

**Falsification Plan:** If IC < 0.05 or PF < 1.5 over 100+ trades, hypothesis is rejected.

---

## 📝 PSEUDOCODE

```python
# INITIALIZATION
swing_strength = 2
regime_window = 20
amp_threshold = 1.5
chop_threshold = 0.6
energy_threshold = 50  # percentile
ema_period = 50
z_threshold = 5.0
stop_atr_mult = 1.0
max_hold_bars = 20
daily_loss_limit = -200

daily_pnl = 0
consecutive_losses = 0
in_position = False
entry_bar = None
position_type = None  # 'LONG' or 'SHORT'

# MAIN LOOP (per bar)
for bar in bars:
    
    # CIRCUIT BREAKER CHECK
    if daily_pnl <= daily_loss_limit:
        continue  # No trading today
    if consecutive_losses >= 3:
        continue  # No trading until reset
    
    # CALCULATE SWING POINTS
    swing_highs = detect_swing_highs(bars, swing_strength)
    swing_lows = detect_swing_lows(bars, swing_strength)
    
    # CALCULATE REGIME (R1 check)
    amplitude = calculate_amplitude(bars[-regime_window:])
    chop = calculate_chop(bars[-regime_window:])
    energy = calculate_energy(bars[-regime_window:])
    
    is_R1 = (amplitude > amp_threshold and 
             chop > chop_threshold and 
             energy > percentile(energy_history, energy_threshold))
    
    # CALCULATE Z-SCORE
    ema = EMA(close[-ema_period:])
    std = StdDev(close[-ema_period:])
    z_score = (close - ema) / std
    
    # CALCULATE WAVE DIRECTION
    bullish_wave = (swing_lows[-1] > swing_lows[-2])
    bearish_wave = (swing_highs[-1] < swing_highs[-2])
    
    # EXIT LOGIC (if in position)
    if in_position:
        bars_held = current_bar_index - entry_bar
        
        # Profit target: EMA reversion
        if position_type == 'LONG' and close >= ema:
            exit_trade('TARGET_HIT')
        elif position_type == 'SHORT' and close <= ema:
            exit_trade('TARGET_HIT')
        
        # Stop loss
        elif position_type == 'LONG' and close <= (swing_lows[-1] - stop_atr_mult * ATR):
            exit_trade('STOP_LOSS')
        elif position_type == 'SHORT' and close >= (swing_highs[-1] + stop_atr_mult * ATR):
            exit_trade('STOP_LOSS')
        
        # Time-based exit
        elif bars_held >= max_hold_bars:
            exit_trade('TIME_EXIT')
        
        # Regime exit
        elif not is_R1:
            exit_trade('REGIME_CHANGE')
    
    # ENTRY LOGIC (if not in position)
    else:
        # LONG ENTRY
        if (is_R1 and 
            z_score <= -z_threshold and 
            bullish_wave and
            bars_since_swing_low(bar) <= 2):
            
            enter_trade('LONG', bar)
        
        # SHORT ENTRY
        elif (is_R1 and 
              z_score >= z_threshold and 
              bearish_wave and
              bars_since_swing_high(bar) <= 2):
            
            enter_trade('SHORT', bar)

# HELPER FUNCTIONS
def enter_trade(direction, bar):
    global in_position, entry_bar, position_type
    in_position = True
    entry_bar = current_bar_index
    position_type = direction
    # Execute market order next bar

def exit_trade(reason):
    global in_position, daily_pnl, consecutive_losses
    pnl = calculate_pnl()
    daily_pnl += pnl
    
    if pnl < 0:
        consecutive_losses += 1
    else:
        consecutive_losses = 0
    
    in_position = False
    # Execute market order next bar

def detect_swing_highs(bars, strength):
    # Identify bars where high > surrounding bars
    pass

def detect_swing_lows(bars, strength):
    # Identify bars where low < surrounding bars
    pass

def calculate_amplitude(window):
    # (High - Low) / ATR(14)
    pass

def calculate_chop(window):
    # 1 - |Trend|
    pass

def calculate_energy(window):
    # Volume × |Close - Open|
    pass
```

---

## ✅ DESIGN CHECKLIST

- [x] Strategy name and hypothesis defined
- [x] All components from V1/V2/V4 integrated
- [x] Entry rules precisely specified (5 conditions)
- [x] Exit rules precisely specified (4 types)
- [x] Parameters documented (10 total, at limit)
- [x] Theoretical justification provided
- [x] Falsification criteria defined
- [x] Pseudocode created
- [x] Sensitivity analysis plan noted

---

## 📋 NEXT STEPS

**Phase 1 Remaining:**
- [ ] Set up validation infrastructure (Alphalens, walk-forward, splits)
- [ ] Implement strategy in Python (production-ready code)
- [ ] Prepare for Phase 2 (backtesting)

**Estimated Time to Phase 2:** 2-3 hours

---

**Status:** SPECIFICATION COMPLETE - Ready for implementation review
