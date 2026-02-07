# System Analysis Template

*Copy this template for each system studied*

---

## 📋 System Identity

- **System Name:**
- **Study Date:**
- **Source Path:**
- **File Type:** (C#, Python, CSV results, etc.)
- **Study Duration:** (hours spent)

---

## 🧠 Core Logic

### High-Level Approach
*(What is this system trying to do? What's the thesis?)*

### Entry Conditions
*(Step-by-step logic for opening positions)*

### Exit Conditions
*(Stop loss, profit target, time-based, trailing, etc.)*

### Filters & Qualifiers
*(What conditions must be met before signals are considered?)*

---

## 🔬 Novel Components

### What Makes This Unique?
*(Not "uses RSI" but "uses RSI divergence against wave amplitude decay")*

### Technical Innovation
*(Any custom indicators, calculations, or approaches?)*

### Regime Awareness
*(Does it adapt to market conditions? How?)*

---

## 📊 Performance Analysis

### Backtesting Results
- **Test Period:**
- **Total Trades:**
- **Net P&L:**
- **Win Rate:**
- **Profit Factor:**
- **Avg Win / Avg Loss:**
- **Max Drawdown:**
- **Sharpe Ratio:**

### Profitable Windows
*(Specific date ranges where system showed edge)*

| Period | Trades | P&L | Win Rate | Regime Type |
|--------|--------|-----|----------|-------------|
| | | | | |

### Failure Windows
*(When did it break down? Why?)*

| Period | Trades | P&L | Loss Rate | Regime Type |
|--------|--------|-----|-----------|-------------|
| | | | | |

---

## 🎯 Regime Mapping

**Best Performance In:**
- [ ] Trending up
- [ ] Trending down
- [ ] Ranging/choppy
- [ ] High volatility
- [ ] Low volatility
- [ ] Market open (8:30-10:00)
- [ ] Mid-day (10:00-14:00)
- [ ] Market close (14:00-15:00)
- [ ] Specific conditions: _______________

**Fails In:**
- [ ] Trending up
- [ ] Trending down
- [ ] Ranging/choppy
- [ ] High volatility
- [ ] Low volatility
- [ ] Market open (8:30-10:00)
- [ ] Mid-day (10:00-14:00)
- [ ] Market close (14:00-15:00)
- [ ] Specific conditions: _______________

---

## ⚠️ Weaknesses & Failure Modes

### Critical Flaws
1.
2.
3.

### Parameter Sensitivity
*(Which settings are fragile? Which are robust?)*

### Overtrading Issues
*(Does it generate too many signals in certain conditions?)*

---

## ✅ Salvageable Components

### Worth Preserving:
1. **Component:** [name]
   - **Function:** [what it does]
   - **Why valuable:** [edge source]
   - **Potential use:** [where to deploy]

2. **Component:** [name]
   - **Function:** [what it does]
   - **Why valuable:** [edge source]
   - **Potential use:** [where to deploy]

### Modular Extraction Plan:
*(How to isolate these components for testing?)*

---

## 🔗 Integration Ideas

### Compatible With:
- **System(s):** [which other systems might synergize?]
- **Why:** [complementary logic]

### Conflicts With:
- **System(s):** [which systems would conflict?]
- **Why:** [incompatible assumptions]

### Ensemble Role:
- **Primary strategy** in [regime type]
- **Secondary filter** for [other system]
- **Risk manager** for [trading approach]
- **Signal confirmation** for [entry logic]

---

## 📝 Deep Observations

*(Detailed notes, insights, questions, hypotheses)*

### What I Noticed:

### Questions Raised:

### Hypotheses to Test:

---

## ⭐ Overall Assessment

**Edge Score:** [1-10]  
**Novelty Score:** [1-10]  
**Robustness Score:** [1-10]  
**Salvage Value:** [1-10]

**Final Verdict:**
- [ ] Keep as standalone strategy for specific regime
- [ ] Extract components for ensemble
- [ ] Use as filter/qualifier for other systems
- [ ] Discard entirely (no edge found)
- [ ] Requires further investigation

**Priority for Integration:** [HIGH / MEDIUM / LOW]

---

*Study completed: [Date]*
