# Mitch's Price Action System - Complete Architecture Specification

**Created:** 2026-02-08 12:20 CT  
**Status:** 🔥 ACTIVE DEVELOPMENT - Idea Taking Root  
**Goal:** Code Mitch's discretionary edge into algorithmic form  

---

## 🎯 CORE PHILOSOPHY

**"What I see on the chart = what the algorithm trades"**

This system codifies Mitch's actual discretionary trading method:
- Structure-based (not indicator-based)
- Price action patterns (not derivatives)
- Al Brooks methodology (second entries, measured moves)
- Mean reversion overlay (EMA21 stretch opportunity)
- Novel grid probability weighting

**NOT another indicator cocktail. This is YOUR method, algorithmic.**

---

## 📊 SYSTEM ARCHITECTURE

### **Layer 1: Structure Detection**

**Purpose:** Identify market structure (trending vs ranging)

**Components:**

1. **Trend State Classification**
   - Input: Price bars, EMA(21)
   - Logic:
     - TREND_UP: Higher highs + higher lows
     - TREND_DOWN: Lower highs + lower lows
     - RANGE: Oscillating around EMA21, no clear direction
   - Output: `trend_state` enum

2. **Swing Point Detection**
   - Input: Price bars
   - Logic: 5-bar fractal (bar[2] highest/lowest within ±2 bars)
   - Output: Array of swing highs/lows with timestamps
   - **Borrow from:** V1/FRR existing code

3. **Trendline Fitting (Al Brooks Method)**
   - Input: Overnight swings (first 2 swing points)
   - Logic:
     - Fit line through swing points
     - Target ~45-degree angle
     - Validate with multiple touches (3+ confirmations)
   - Output: `upper_trendline`, `lower_trendline` (slope + intercept)

4. **Channel Creation**
   - Input: One validated trendline
   - Logic: Clone parallel line at channel width (measured from swing range)
   - Output: `channel_upper`, `channel_lower`

5. **Key Entry Point Identification**
   - Input: Current price, trendlines, EMA21
   - Logic:
     - Distance to upper trendline < 0.5 ATR
     - Distance to lower trendline < 0.5 ATR
     - Distance to EMA21 < 0.5 ATR
   - Output: Boolean `at_key_entry_point`

---

### **Layer 2: Pattern Recognition (Al Brooks Price Action)**

**Purpose:** Detect high-probability entry patterns

**Components:**

1. **Two-Legged Move Detector**
   - Input: Price bars, trend_state
   - Logic:
     ```
     Leg 1: Initial swing in trend direction
     Pullback: Counter-trend retracement (1-3 bars)
     Leg 2: Resumption in trend direction (second entry)
     ```
   - Count tracking:
     - New extreme (high/low) = reset count to 0
     - First attempt after pullback = first entry
     - Second attempt after pullback = **second entry** (SIGNAL)
   - Output: `second_entry_signal` (LONG/SHORT/NONE)

2. **Measured Move Calculator**
   - Input: First leg swing (start, end prices)
   - Logic:
     - Measure distance: `leg1_distance = abs(end - start)`
     - From pullback low/high, project: `target = pullback_price ± leg1_distance`
   - Output: `measured_target` price level
   - **Validation signal:**
     - If price reaches target → reversal expected
     - If price falls short → weakness signal (potential sell-off)

3. **Second Entry Confirmation**
   - Input: Current bar, second_entry_signal, key_entry_point
   - Logic: ALL must be true:
     ```python
     at_key_entry_point == True
     second_entry_signal != NONE
     two_legged_pattern_complete == True
     ```
   - Output: Boolean `pattern_confirmed`

---

### **Layer 3: Mean Reversion Filter (Mitch's 3-5x/Day Edge)**

**Purpose:** Identify high-probability EMA21 snap-back opportunities

**Components:**

1. **EMA21 Stretch Detector**
   - Input: Current price, EMA21, ATR
   - Logic:
     ```python
     distance = abs(current_price - ema21)
     stretched = distance > 1.5 * atr
     ```
   - Output: Boolean `ema21_stretched`
   - **Expected frequency:** 3-5 occurrences per day

2. **Snap-Back Opportunity**
   - Input: ema21_stretched, second_entry_signal
   - Logic: If stretched AND second entry forms → BOOST confidence
   - Output: `high_confidence_setup` flag

---

### **Layer 4: Grid Probability Weighting (NOVEL - Mitch's Innovation)**

**Purpose:** Spatial probability heatmap based on historical success

**Components:**

1. **Grid Space Definition**
   - **X-axis:** Distance from EMA21 (in ATR units, -5 to +5)
   - **Y-axis:** Position in channel (0% = bottom, 100% = top)
   - **Grid resolution:** 20 × 20 cells = 400 cells
   - **Context dimensions:**
     - Time of day (first hour, mid-day, afternoon)
     - Volume profile (low, medium, high)
     - Recent volatility (ATR expanding vs contracting)
     - Momentum (trending vs choppy)

2. **Historical Probability Calculation**
   - Input: Past trades database (entry conditions + outcomes)
   - Logic:
     ```python
     For each historical trade:
         cell_x = (entry_price - ema21) / atr
         cell_y = position_in_channel(entry_price, channel_lines)
         context = (time_of_day, volume_level, volatility, momentum)
         
         if trade_won:
             grid[cell_x][cell_y][context] += 1
         
     probabilities = grid / total_trades_per_cell
     ```
   - Output: 4D probability matrix `grid_weights[x][y][time][volume]`

3. **Real-Time Grid Lookup**
   - Input: Current position, current context
   - Logic:
     ```python
     current_cell = get_cell(current_price, ema21, channel, atr)
     current_context = get_context(time, volume, volatility, momentum)
     probability = grid_weights[current_cell][current_context]
     ```
   - Output: Float `win_probability` (0.0 - 1.0)

4. **Confidence Adjustment**
   - Input: win_probability, pattern_confirmed
   - Logic:
     ```python
     if win_probability > 0.65:
         confidence = HIGH
     elif win_probability > 0.55:
         confidence = MEDIUM
     else:
         confidence = LOW  # Skip trade
     ```
   - Output: Trade confidence level

---

### **Layer 5: Live Data Integration (REAL-TIME)**

**Purpose:** Consume live OHLCV feed for dynamic grid weighting

**Components:**

1. **CSV Data Consumer**
   - Input: Mitch's indicator → live OHLCV CSV file
   - File format:
     ```
     timestamp,open,high,low,close,volume
     2026-02-08 09:35:00,18500.25,18505.50,18498.75,18502.00,1250
     ```
   - Logic:
     - Watch file for new rows (polling every 5 seconds)
     - Parse latest bar
     - Update current state
   - Output: `latest_bar` object

2. **Intraday Grid Updates**
   - Input: Latest bars (last 20), outcomes of recent trades
   - Logic:
     ```python
     # As trades complete during session:
     if trade_closed:
         update_grid_cell(entry_cell, trade_result)
         recalculate_probabilities()
     
     # Grid adapts to TODAY's behavior
     ```
   - Output: Updated `grid_weights` (session-specific overlay)

3. **Volume Spike Detection**
   - Input: Current volume, rolling average volume (20 bars)
   - Logic:
     ```python
     avg_volume = mean(last_20_bars.volume)
     spike = current_volume > avg_volume * 1.5
     ```
   - Output: Boolean `volume_confirmation`
   - **Purpose:** Hedge fund footprint detection (large player activity)

4. **Real-Time Probability Adjustment**
   - Input: Grid probabilities, intraday performance
   - Logic:
     ```python
     # If cell winning today → boost confidence
     # If cell losing today → reduce confidence
     adjusted_prob = base_probability * session_multiplier
     ```
   - Output: Session-adjusted `live_win_probability`

---

### **Layer 6: Entry Logic (The Decision Engine)**

**Purpose:** Combine all layers into go/no-go decision

**Entry Conditions (ALL must be TRUE):**

```python
def should_enter_trade(state):
    # Layer 1: Structure
    structure_valid = (
        state.trend_state != UNKNOWN and
        state.at_key_entry_point == True
    )
    
    # Layer 2: Pattern
    pattern_valid = (
        state.second_entry_signal != NONE and
        state.pattern_confirmed == True
    )
    
    # Layer 3: Mean Reversion (optional boost)
    mean_reversion_edge = state.ema21_stretched == True
    
    # Layer 4: Grid Probability
    grid_valid = state.win_probability > 0.55  # Minimum threshold
    
    # Layer 5: Volume Confirmation
    volume_valid = state.volume_confirmation == True
    
    # COMBINED DECISION
    if structure_valid and pattern_valid and grid_valid and volume_valid:
        if mean_reversion_edge:
            return ENTER_HIGH_CONFIDENCE
        else:
            return ENTER_MEDIUM_CONFIDENCE
    else:
        return NO_TRADE
```

---

### **Layer 7: Trade Management**

**Purpose:** Entry, stops, targets

**Components:**

1. **Entry Price**
   - Market order at current bar close (or limit at key level)

2. **Stop Loss**
   - **In trend:** Recent swing point (opposite side)
   - **At channel:** Just beyond channel line (0.5 ATR buffer)
   - **Maximum:** 2 ATR from entry

3. **Target**
   - **Primary:** Measured move target (from two-legged move calculation)
   - **Secondary:** Opposite channel line
   - **EMA21 reversion:** EMA21 price (if stretched setup)

4. **Time Exit**
   - **Maximum hold:** 30 bars (2.5 hours on 5-min chart)
   - **Session close:** 3:45 PM CT (no overnight holds)

---

## 🔧 TECHNICAL IMPLEMENTATION

### **Module Structure**

```
research/
├── modules/
│   ├── mitch_price_action_system.py       # Main strategy
│   ├── structure_detector.py               # Layer 1: Trend/channels
│   ├── pattern_recognizer.py               # Layer 2: Second entries
│   ├── mean_reversion_filter.py            # Layer 3: EMA21 stretch
│   ├── grid_probability_engine.py          # Layer 4: Probability matrix
│   ├── live_data_consumer.py               # Layer 5: CSV feed integration
│   ├── entry_logic.py                      # Layer 6: Decision engine
│   └── trade_manager.py                    # Layer 7: Execution
│
├── data/
│   └── live_ohlcv.csv                      # Mitch's live feed
│
├── config/
│   └── mitch_system_config.json            # Parameters
│
└── analysis/
    ├── backtest_results.json
    ├── grid_heatmap.png
    └── performance_report.md
```

---

### **Configuration Parameters**

```json
{
  "structure": {
    "swing_strength": 2,
    "ema_period": 21,
    "trendline_angle_target": 45,
    "min_trendline_touches": 3,
    "key_entry_threshold_atr": 0.5
  },
  "pattern": {
    "max_pullback_bars": 3,
    "measured_move_tolerance": 0.1
  },
  "mean_reversion": {
    "stretch_threshold_atr": 1.5,
    "expected_daily_occurrences": 5
  },
  "grid": {
    "x_resolution": 20,
    "y_resolution": 20,
    "ema_distance_range": [-5, 5],
    "min_probability_threshold": 0.55,
    "high_confidence_threshold": 0.65
  },
  "live_data": {
    "csv_path": "data/live_ohlcv.csv",
    "poll_interval_seconds": 5,
    "volume_spike_multiplier": 1.5
  },
  "trade_management": {
    "max_stop_atr": 2.0,
    "max_hold_bars": 30,
    "session_close_time": "15:45"
  },
  "backtest": {
    "commission_per_trade": 2.0,
    "slippage_ticks": 1
  }
}
```

---

## 📈 BACKTEST PROTOCOL

### **Phase 1: Historical Validation**

**Dataset:** MNQ 5-minute bars, 2019-2026 (6.7 years)

**Test conditions:**
1. All layers enabled
2. No lookahead bias
3. Realistic transaction costs

**Metrics to capture:**
- Total trades
- Win rate (overall, by setup type)
- Profit factor
- Average $/trade
- Sharpe ratio
- Max drawdown
- **Trades per day** (must hit 3-5 target)

**Success criteria:**
- Win rate ≥ 55%
- Profit factor ≥ 1.5
- Trades per week ≥ 15 (3/day × 5 days)
- Average trade ≥ $10 after costs

---

### **Phase 2: Grid Validation**

**Test:** Does grid probability improve performance?

**A/B test:**
- Strategy WITH grid filter (only enter if prob > 0.55)
- Strategy WITHOUT grid filter (enter on pattern alone)

**Comparison:**
- Win rate delta
- Profit factor delta
- Trade count delta

**If grid HELPS:** Keep it  
**If grid HURTS:** Drop it (pattern recognition sufficient)

---

### **Phase 3: Live Data Simulation**

**Simulate:** Real-time CSV consumption

**Test:**
- Parse live_ohlcv.csv file
- Update state every 5 seconds
- Execute entries in real-time mode

**Validate:**
- No data leakage (only use past bars)
- Timing realistic (entry delays, fills)

---

## 🎨 VISUALIZATION & ANALYSIS

### **Charts to Generate**

1. **Structure Overlay**
   - Price bars
   - Detected trendlines (with validation points)
   - Channels (shaded regions)
   - Swing points marked
   - EMA21 line

2. **Pattern Detection**
   - Two-legged moves highlighted
   - First entry vs second entry labels
   - Measured move targets (projected lines)
   - Actual reversal points

3. **Grid Heatmap**
   - 20×20 cells (X: EMA distance, Y: channel position)
   - Color intensity = win probability
   - Hot zones (red) = high success
   - Cold zones (blue) = low success

4. **Entry/Exit Markers**
   - Green arrows: Entries
   - Red X: Stop hits
   - Blue checkmark: Target hits
   - Yellow circle: Time exits

5. **Equity Curve**
   - Cumulative P&L
   - Drawdown shading
   - Trade markers

---

## 🧪 TESTING SCENARIOS

### **Scenario 1: Trending Day**
- Strong directional move
- Multiple second entries in trend direction
- Channel widening
- Expected: High win rate, good R:R

### **Scenario 2: Ranging Day**
- Price oscillating between support/resistance
- Horizontal channels
- EMA21 mean reversions frequent
- Expected: More trades, smaller wins

### **Scenario 3: Choppy/Whipsaw Day**
- False breakouts
- Weak two-legged moves
- Grid should flag low probability
- Expected: Fewer trades (filter saves us)

### **Scenario 4: First Hour Focus**
- 8:30-9:30 AM CT (like WickSwing's sweet spot)
- Does this system also work best in first hour?
- Or does it work all day?

---

## 🚀 DEPLOYMENT PATH

### **Step 1: Python Prototype (Tonight)**
- Build all modules
- Backtest on historical data
- Generate performance report

### **Step 2: Refinement (This Week)**
- Mitch reviews output
- Tunes parameters
- Validates against what he sees on charts

### **Step 3: NinjaTrader Port (Week 2)**
- Convert Python → C# NinjaScript
- Integrate with live_ohlcv.csv feed
- Strategy Analyzer validation

### **Step 4: Paper Trading (Week 3-6)**
- Deploy to Sim101
- Monitor live performance
- Compare to backtest expectations

### **Step 5: Micro-Live Decision (Week 7)**
- If paper trading successful → 1 contract live
- Circuit breakers active
- Daily monitoring

---

## 💡 INNOVATION HIGHLIGHTS (What Makes This Different)

### **1. Structure-First Approach**
- Most algos start with indicators
- This starts with structure (channels, support/resistance)
- **Matches discretionary trader thinking**

### **2. Al Brooks Price Action**
- Second entries, two-legged moves
- Measured move targets
- **Proven discretionary methodology**

### **3. Grid Probability Overlay**
- **NOVEL** - not in any standard library
- Spatial reasoning (where am I on the chart?)
- Historical probability matrix
- **Mitch's original innovation**

### **4. Live Adaptation**
- Grid updates during session
- Today's behavior informs today's trades
- **Responsive to current market state**

### **5. Mean Reversion Overlay**
- EMA21 stretch = Mitch's 3-5x/day edge
- Known high-probability setup
- **Boosts confidence when present**

---

## 🔍 KEY QUESTIONS TO ANSWER

### **For Mitch (Review Tonight/Tomorrow):**

1. **Trendline detection:**
   - Use overnight swings (first 2)?
   - Or any swing points once validated?

2. **Channel width:**
   - Parallel to trendline
   - Distance = average swing range?
   - Or fixed ATR multiple?

3. **Second entry count:**
   - Does count reset ONLY on new extreme?
   - Or also on trendline touch?

4. **Measured move:**
   - First leg measured bar-to-bar?
   - Or swing point to swing point?

5. **Grid weighting:**
   - Start with historical probabilities?
   - Or build from scratch during live trading?

6. **Live CSV format:**
   - Confirm column names/order
   - Timestamp format?

---

## 📋 DEVELOPMENT CHECKLIST

### **Tonight (Sentinel):**
- [ ] Build structure_detector.py
- [ ] Build pattern_recognizer.py (Al Brooks logic)
- [ ] Build mean_reversion_filter.py
- [ ] Build grid_probability_engine.py (basic version)
- [ ] Build live_data_consumer.py (CSV parser)
- [ ] Integrate into mitch_price_action_system.py
- [ ] Run backtest on MNQ 5-min data
- [ ] Generate performance report + charts

### **Tomorrow (Mitch Review):**
- [ ] Does detected structure match your charts?
- [ ] Are second entries flagged correctly?
- [ ] Do measured moves make sense?
- [ ] Grid heatmap intuitive?
- [ ] Ready for refinement or needs fixes?

### **This Week (Refinement):**
- [ ] Parameter tuning
- [ ] Add missing logic
- [ ] Validate on recent data (2025-2026)
- [ ] Prepare for NinjaTrader port

---

## 🎯 SUCCESS DEFINITION

**This system is "working" when:**

1. ✅ Backtest shows ≥55% WR, ≥1.5 PF, 15+ trades/week
2. ✅ Detected patterns match what Mitch sees on charts
3. ✅ Grid probabilities align with Mitch's intuition
4. ✅ Live CSV integration works smoothly
5. ✅ Mitch feels: "Yes, this IS my discretionary method coded"

**Then and only then:** Port to NinjaTrader and paper trade.

---

## 📝 NOTES & REFINEMENTS

### **Ideas to Explore:**

- **Multi-timeframe structure:** 5-min entries, 15-min trend confirmation?
- **Volume profile integration:** High-volume nodes as support/resistance
- **Time-of-day weighting:** First hour vs mid-day vs close
- **Regime handoff:** When to switch from trending to ranging logic
- **Failure pattern recognition:** What does a "bad" second entry look like?

### **Questions for Later:**

- Optimize grid resolution (20×20 vs 30×30 vs 10×10)?
- Machine learning for grid weights (vs rule-based)?
- Real-time adjustment speed (how fast to adapt to today's behavior)?

---

## 🔒 CONFIDENTIALITY

**This is Mitch's proprietary method.**

- Do not share this specification externally
- Grid probability approach is novel (potential IP)
- Al Brooks methodology is public, but combination is unique

---

**Status:** Ready for overnight build  
**Next Update:** Tomorrow morning briefing with results  

---

*"This is YOUR edge, Mitch. Let's prove it works algorithmically."*

**— Sentinel, 2026-02-08 12:20 CT**
