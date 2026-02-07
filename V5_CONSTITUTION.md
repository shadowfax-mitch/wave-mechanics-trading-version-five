# V5 CONSTITUTION - The Law for Trading System Development

**Ratified:** 2026-02-07  
**Authors:** Mitch & Sentinel  
**Purpose:** Prevent repeating V1-V4 mistakes. Build ONE profitable system.

---

## PREAMBLE

After 10 months and 4 system iterations (V1-V4), we learned:
- **Complexity destroys edge** (V2/V3 worse than V1)
- **Scalping doesn't work** (V3: 0%, V4: failed live)
- **Small samples deceive** (backtests lie, live reveals truth)
- **V1's simplicity had merit** (best per-trade quality)

**This Constitution exists to protect V5 from these mistakes.**

This is LAW. Not guidelines. Not suggestions. **LAW.**

---

## ARTICLE 1: Simplicity is Mandatory

> *"ONE strategy. Not 8. Not 28. ONE."*

- V5 will have EXACTLY ONE core trading strategy
- No additional strategies until the first proves profitable over 100+ trades
- Every feature must justify its existence with measurable edge
- When in doubt, leave it out
- **Violation:** Automatic V5 failure, return to planning

---

## ARTICLE 2: Evidence Over Theory

> *"The data decides. Not our beliefs."*

- No deployment without 100+ trades validation
- Backtest results must match forward test results
- If live trading disagrees with backtest, trust live trading
- Exotic theories (quantum, Heisenberg, entropy) require proof like any other approach
- **Measurement:** Does it make money? Yes/No. Nothing else matters.

---

## ARTICLE 3: No Scalping Until Proven

> *"V3 proved: 1-min bars don't work. V4 proved: scalps fail live."*

- Minimum timeframe: 5-minute bars
- Higher timeframes (10-min, 15-min, 2000-tick) are acceptable
- Scalping (1-sec, 1-min) is BANNED until someone proves it works elsewhere
- **Exception:** If 100+ trades on 5-min fail, may test higher timeframes first

---

## ARTICLE 4: Sample Size Discipline

> *"21 trades isn't enough. 8 trades is a joke. 100+ minimum."*

**Before Strategy Analyzer:** 100+ backtest trades over 6-12 months
**Before Paper Trading:** Strategy Analyzer validation passes
**Before Live Trading:** 4+ weeks paper trading successful
**Before Scaling:** 100+ live trades profitable

**No shortcuts. No "looks good after 20 trades" exceptions.**

---

## ARTICLE 5: Realistic Transaction Costs

> *"If it only works without commissions, it doesn't work."*

- Commission: $2.00 per round-turn minimum (MNQ/MES)
- Slippage: $2.50 minimum per trade (0.25 points MES)
- Backtest must be profitable AFTER costs
- If edge disappears with realistic costs, strategy is invalid

---

## ARTICLE 6: NinjaTrader Validation Required

> *"Python backtest ≠ NinjaTrader reality."*

- Every strategy MUST pass Strategy Analyzer validation
- Python results and NT results must align (<20% difference)
- If NT disagrees with Python, trust NinjaTrader (it's closer to live)
- No live trading without NT validation

---

## ARTICLE 7: Paper Trading is Not Optional

> *"V4 Zone Scalper: great backtest, failed live. Paper trading catches this."*

- Minimum 4 weeks paper trading
- Compare paper results to backtest expectations
- If paper performance < 80% of backtest, do NOT go live
- If significant deviation found, return to validation phase

---

## ARTICLE 8: Circuit Breakers are Mandatory

> *"V4 proved: circuit breakers work (-$1,539 → -$22)"*

**Every live strategy must have:**
- Daily loss limit: -$80
- Weekly loss limit: -$150
- Consecutive loss limit: 2 trades
- System halts automatically when limits hit
- Manual override requires written justification

---

## ARTICLE 9: Resist Complexity Creep

> *"V2 added 20 strategies to V1. Result: 1.02 PF (break-even)."*

**Before adding ANYTHING to V5:**
1. Ask: "Does this add measurable edge?"
2. If yes: Prove it with A/B test (with vs without)
3. If no measurable improvement: DO NOT ADD
4. One feature added = consider removing another

**Complexity budget:** Each addition requires documented justification

---

## ARTICLE 10: Goal is $100/Week, Not Perfection

> *"$100/week = $5,200/year. Achievable. Scalable."*

- **Success metric:** Consistent $100/week profit (not $1,000/day dreams)
- 1 contract on MES/MNQ is sufficient
- Scale ONLY after 100+ profitable live trades
- Perfection is the enemy of profitability

---

## ARTICLE 11: Timeframe and Instrument are Flexible

> *"Evidence decides. Not preferences."*

- Start with what V1 used: 5-minute bars (proven 2.38 PF)
- If 5-min fails: test 10-min, 15-min, or 2000-tick bars
- MES and MNQ are both acceptable
- Let profitability guide decisions, not assumptions

---

## ARTICLE 12: V1 is the Baseline

> *"V1 had best per-trade quality. Start there."*

- V5's first candidate strategy: V1's approach (or simplified version)
- Prove V1 doesn't work at scale BEFORE trying something exotic
- If V1 works: use it. Don't "improve" it into failure.
- Only if V1 fails 100+ trade validation, try V4 Z-score as backup

---

## ARTICLE 13: Discipline Over Enthusiasm

> *"10 months of work. 4 failed systems. V5 must be different."*

**When tempted to add features, revisit this Constitution**

**Red flags:**
- "Let's just add one more strategy..."
- "This parameter sweep will find the edge..."
- "Quantum theory might work..."
- "20 trades looks good, let's go live..."

**Correct response:** "Does this violate the Constitution?" If yes, DON'T DO IT.

---

## ENFORCEMENT

**Sentinel's role:** Constitutional Guardian (like V2, but with teeth)

**Sentinel MUST:**
- Challenge any violation
- Demand evidence for additions
- Remind Mitch of V1-V4 lessons
- Block deployment if validation incomplete

**Mitch's commitment:** Listen to challenges, even when frustrated

---

## AMENDMENTS

Changes require:
1. Written justification
2. Evidence from V5 data
3. Agreement from both Mitch and Sentinel

**Amendments are appended, not edited** (preserve history)

---

## SUCCESS CRITERIA

**V5 is successful when:**
- ✅ 100+ backtest trades profitable (>2.0 PF)
- ✅ Strategy Analyzer validation passes
- ✅ 4+ weeks paper trading successful
- ✅ 100+ live trades averaging $100/week
- ✅ Can scale to 2-3 contracts without breaking

**Until ALL criteria met, V5 is incomplete.**

---

**Signatures:**

**Mitch** - Trader, 10 months of experience, committed to discipline  
**Sentinel** - AI Partner, Constitutional Guardian, evidence-focused

*"Simple. Validated. Profitable. In that order."*

---

**Ratified:** 2026-02-07 12:05 CST
