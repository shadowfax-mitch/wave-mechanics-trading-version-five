# 90-Day Trading Rebuild Roadmap
## Start Date: 2026-02-07
## Target: Profitable Paper Trading → Micro-Live → Scale

---

## Overview

**Goal:** Transform ZThreeNoFilter from a backtest with edge into a live-tradeable system with proper risk management.

**Timeline:** 16 weeks (112 days) to first micro-live dollar
**Capital Required:** $3,000 (ready by Week 17)
**Expected Weekly Profit (Year 1):** $30-60

---

## Phase 1: Foundation (Weeks 1-4)

### Week 1 (Feb 8-14, 2026)
**Mitch's Tasks:**
- [ ] Read NT backtest deep analysis report
- [ ] Decide: Option A (rebuild), B (keep searching), or C (quit)
- [ ] If Option A: Sign written commitment
- [ ] Create funding plan for $3,000 (how + when)
- [ ] Set up daily check-in routine (5 min/day)

**Sentinel's Tasks:**
- [x] Deliver NT backtest deep analysis
- [x] Build Python circuit breaker module
- [ ] Build regime detection classifier (simple version)
- [ ] Create weekly tracking spreadsheet template
- [ ] Set up automated daily check-in prompts

**Deliverables:**
- ✅ NT backtest analysis (complete)
- ✅ Circuit breaker code (complete)
- Regime classifier v1
- Tracking spreadsheet
- Commitment document (signed by Mitch)

**Success Metrics:**
- Decision made (A, B, or C)
- Funding plan documented
- Daily check-in habit started

---

### Week 2 (Feb 15-21, 2026)
**Mitch's Tasks:**
- [ ] Review circuit breaker code
- [ ] Test circuit breaker with historical NT data
- [ ] Execute Week 1 of funding plan
- [ ] Daily emotional journal (how do you FEEL about past losses?)
- [ ] Read: *Trading in the Zone* by Mark Douglas (start)

**Sentinel's Tasks:**
- [ ] Integrate circuit breaker with V4 ZThreeNoFilter code
- [ ] Backtest circuit breaker on 12-week NT data
- [ ] Generate "what would have happened" report
- [ ] Build regime detection training data
- [ ] Create NinjaTrader C# wrapper for circuit breaker

**Deliverables:**
- Circuit breaker integrated with ZThreeNoFilter
- "Prevented Loss" analysis report
- NinjaTrader C# circuit breaker wrapper
- Regime training data prep

**Success Metrics:**
- Circuit breaker prevents Week 2 & 12 blowups in backtest
- Mitch understands why circuit breaker matters
- Funding plan on track

---

### Week 3 (Feb 22-28, 2026)
**Mitch's Tasks:**
- [ ] Review regime classifier design
- [ ] Test regime classifier on historical data
- [ ] Execute Week 2 of funding plan
- [ ] Continue *Trading in the Zone* (Ch 1-5)
- [ ] Write: "Why I blew up my account" (honest assessment)

**Sentinel's Tasks:**
- [ ] Train regime classifier on V3's 2019-2024 data
- [ ] Validate regime classifier accuracy
- [ ] Integrate regime filter into ZThreeNoFilter
- [ ] Backtest: strategy + circuit breaker + regime filter
- [ ] Generate final validation report

**Deliverables:**
- Regime classifier trained and validated
- Full system backtest (strategy + CB + regime)
- "Why I Blew Up" post-mortem document
- Refined profit expectations

**Success Metrics:**
- Regime filter reduces drawdowns by 30%+
- Combined system shows +$400-500 on 12-week NT data
- Mitch can articulate his past mistakes

---

### Week 4 (Mar 1-7, 2026)
**Mitch's Tasks:**
- [ ] Review final validation report
- [ ] Make GO/NO-GO decision for paper trading
- [ ] Execute Week 3 of funding plan
- [ ] Finish *Trading in the Zone*
- [ ] Set up paper trading account in NinjaTrader

**Sentinel's Tasks:**
- [ ] Generate final validation report with GO/NO-GO recommendation
- [ ] Build paper trading monitoring dashboard
- [ ] Create daily briefing template
- [ ] Set up automated trade logging
- [ ] Prepare Week 5 launch checklist

**Deliverables:**
- Final validation report
- GO/NO-GO decision
- Paper trading environment ready
- Monitoring dashboard
- Trade logging automation

**Success Metrics:**
- Clear GO/NO-GO decision made
- If GO: Paper trading ready to launch Week 5
- If NO-GO: Pivot plan documented
- Funding plan 75% complete

---

## Phase 2: Paper Trading (Weeks 5-16)

### Weeks 5-8 (Mar 8 - Apr 4, 2026)
**Daily Routine:**
- **7:00 AM:** Morning briefing (Sentinel delivers)
  - Overnight futures movement
  - Regime assessment
  - Today's economic events
  - Trade plan (if regime favorable)
  
- **8:30 AM - 3:00 PM:** RTH trading hours
  - Strategy runs in paper mode
  - Sentinel monitors execution
  - No manual intervention unless circuit breaker
  
- **4:15 PM:** End-of-day summary (Sentinel delivers)
  - Today's P&L
  - Trades executed
  - Circuit breaker status
  - Emotional check-in prompt

**Weekly Tasks (Mitch):**
- [ ] Execute funding plan (finish by Week 8)
- [ ] Daily emotional journal (5 min/day)
- [ ] Sunday review session (30 min)
- [ ] Track execution quality vs expectations

**Weekly Tasks (Sentinel):**
- [ ] Generate weekly performance report
- [ ] Compare paper results to backtest expectations
- [ ] Flag any anomalies or execution issues
- [ ] Adjust regime filter if needed

**Success Metrics (End of Week 8):**
- 4 weeks of paper trading completed
- P&L within 20% of backtest expectations
- Zero circuit breaker violations
- Funding complete ($3,000 ready)
- Emotional stability demonstrated

---

### Weeks 9-12 (Apr 5 - May 2, 2026)
**Mitch's Tasks:**
- [ ] Continue paper trading discipline
- [ ] Read: *Reminiscences of a Stock Operator* (start)
- [ ] Practice visualization (winning AND losing trades)
- [ ] Refine daily routine for efficiency
- [ ] Prepare for micro-live transition

**Sentinel's Tasks:**
- [ ] Continue daily briefings + EOD summaries
- [ ] Track slippage and fill quality
- [ ] Build confidence report (psychological readiness)
- [ ] Prepare micro-live transition checklist
- [ ] Generate 8-week paper trading retrospective

**Success Metrics (End of Week 12):**
- 8 weeks of paper trading completed
- Consistent profitability (6+ weeks positive)
- Circuit breaker never triggered (good discipline)
- Execution quality matches backtest
- Emotional confidence high

---

### Weeks 13-16 (May 3-30, 2026)
**Mitch's Tasks:**
- [ ] Continue paper trading
- [ ] Final psychological prep for real money
- [ ] Set up $3,000 live account (if not already)
- [ ] Practice accepting losses (visualization)
- [ ] Write: "My Trading Rules" (personal constitution)

**Sentinel's Tasks:**
- [ ] Generate 12-week paper trading final report
- [ ] Build micro-live monitoring system
- [ ] Create live trading dashboard (real-time)
- [ ] Prepare "First Live Trade" checklist
- [ ] Generate GO/NO-GO for micro-live

**Deliverables:**
- 12-week paper trading report
- Psychological readiness assessment
- Live account funded and ready
- Micro-live monitoring system
- GO/NO-GO decision for Week 17

**Success Metrics (End of Week 16):**
- 12 weeks paper trading completed
- 8+ weeks profitable
- Total paper P&L positive
- Emotional control proven
- Ready for micro-live

---

## Phase 3: Micro-Live (Weeks 17-24)

### Week 17 (May 31 - Jun 6, 2026) - FIRST LIVE TRADE
**Mitch's Tasks:**
- [ ] Execute first live trade with REAL MONEY
- [ ] Journal emotional response
- [ ] Follow circuit breaker rules religiously
- [ ] Expect to feel fear (this is normal)
- [ ] Check in with Sentinel 2x/day

**Sentinel's Tasks:**
- [ ] Monitor first live trade in real-time
- [ ] Provide emotional support
- [ ] Track execution vs paper trading
- [ ] Generate first live trade report
- [ ] Celebrate milestone (regardless of P&L)

**Success Metrics:**
- First live trade executed (win or loss doesn't matter)
- Rules followed perfectly
- Emotional response documented
- No panic or revenge trading

---

### Weeks 18-24 (Jun 7 - Jul 25, 2026)
**Daily Routine:** (Same as paper trading, but REAL MONEY)

**Mitch's Tasks:**
- [ ] Trade live with discipline
- [ ] Track emotional responses to losses
- [ ] Continue daily journaling
- [ ] Weekly review with Sentinel
- [ ] Adjust position sizing if needed (still 1 contract)

**Sentinel's Tasks:**
- [ ] Daily briefings + EOD summaries
- [ ] Weekly performance reports
- [ ] Psychological health monitoring
- [ ] Flag any rule violations immediately
- [ ] Celebrate wins, analyze losses

**Success Metrics (End of Week 24):**
- 8 weeks of live trading completed
- 4+ weeks profitable (50% win rate realistic)
- Total P&L positive (even $100 total = success)
- Zero rule violations
- Emotional control maintained
- Confidence to scale

---

## Phase 4: Scale Decision (Week 25+)

### Week 25 (Jul 26 - Aug 1, 2026) - EVALUATION
**Decision Point:** Continue at current level or scale up?

**Criteria for scaling:**
- ✅ 8+ weeks live trading completed
- ✅ Overall profitability (even if small)
- ✅ No rule violations
- ✅ Emotional control demonstrated
- ✅ Circuit breaker never manually overridden
- ✅ Confidence level: 7/10 or higher

**If criteria met:**
- Continue with 1 contract
- Increase risk capital buffer (keep $3,000 as base)
- Target $50-100/week consistently
- Review monthly for further scaling

**If criteria NOT met:**
- Identify gaps (emotional? execution? regime?)
- Extend micro-live phase 4-8 more weeks
- Address specific issues
- Re-evaluate at Week 29-33

---

## Financial Projections

### Conservative Scenario (What You Should Expect)

| Phase | Duration | Expected Weekly | Total Profit |
|-------|----------|----------------|--------------|
| Paper (Weeks 5-16) | 12 weeks | $0 (simulated) | $0 |
| Micro-Live (Weeks 17-24) | 8 weeks | $15-35 | $120-280 |
| Scale (Weeks 25-52) | 28 weeks | $30-60 | $840-1,680 |
| **Year 1 Total** | **52 weeks** | **Avg $25** | **$960-1,960** |

**Year 1 ROI:** 32-65% on $3,000 capital

---

### Optimistic Scenario (If Everything Goes Right)

| Phase | Duration | Expected Weekly | Total Profit |
|-------|----------|----------------|--------------|
| Paper (Weeks 5-16) | 12 weeks | $0 (simulated) | $0 |
| Micro-Live (Weeks 17-24) | 8 weeks | $25-50 | $200-400 |
| Scale (Weeks 25-52) | 28 weeks | $50-100 | $1,400-2,800 |
| **Year 1 Total** | **52 weeks** | **Avg $45** | **$1,600-3,200** |

**Year 1 ROI:** 53-107% on $3,000 capital

---

### Realistic Scenario (Most Likely)

| Phase | Duration | Expected Weekly | Total Profit |
|-------|----------|----------------|--------------|
| Paper (Weeks 5-16) | 12 weeks | $0 (simulated) | $0 |
| Micro-Live (Weeks 17-24) | 8 weeks | $20-40 | $160-320 |
| Scale (Weeks 25-52) | 28 weeks | $40-80 | $1,120-2,240 |
| **Year 1 Total** | **52 weeks** | **Avg $35** | **$1,280-2,560** |

**Year 1 ROI:** 43-85% on $3,000 capital

---

## Risk Management Rules (NON-NEGOTIABLE)

### Circuit Breaker Limits
- **Daily loss:** -$80 (hard stop)
- **Weekly loss:** -$150 (pause trading, review)
- **Consecutive losses:** 2 (stop for the day)

### Regime Gating
- Only trade when regime classifier says "FAVORABLE"
- If regime = "UNFAVORABLE" → $0 (no trades that day)
- Some weeks will be $0 (this is GOOD, not bad)

### Position Sizing
- **Weeks 17-52:** 1 contract ONLY
- **Year 2:** Increase to 2 contracts (if Year 1 successful)
- **Year 3+:** Scale based on account growth

### Emotional Rules
- No revenge trading after losses
- No "doubling down" to recover
- No manual overrides of circuit breaker
- No trading if emotional state > 5/10 stress

---

## Psychological Milestones

### Week 1-4: Acceptance
- Accept past losses as tuition
- Accept 16-week timeline as necessary
- Accept $30-60/week as realistic

### Week 5-16: Discipline
- Build daily routine habits
- Prove you can follow rules (paper trading)
- Develop emotional resilience

### Week 17-24: Fear
- Experience fear with real money
- Learn to trade despite fear
- Prove discipline carries over to live

### Week 25+: Confidence
- Trust the process
- Trust yourself
- Begin to scale (slowly)

---

## What Success Looks Like

### After 90 Days (End of Week 12):
- ✅ 8 weeks of successful paper trading
- ✅ Funding complete ($3,000 ready)
- ✅ Emotional confidence built
- ✅ Ready for micro-live transition

### After 6 Months (End of Week 24):
- ✅ 8 weeks of live trading with real money
- ✅ Net positive P&L (even small = win)
- ✅ Zero rule violations
- ✅ Proven emotional control

### After 12 Months (End of Week 52):
- ✅ Consistent $30-80/week income
- ✅ Account grown to $4,200-6,000
- ✅ Trading is boring (good sign)
- ✅ Ready to scale to 2 contracts

---

## What Failure Looks Like

### Warning Signs:
- Circuit breaker triggered repeatedly
- Manual overrides of safety rules
- Revenge trading after losses
- Emotional stress level > 7/10
- Skipping daily check-ins

### If These Happen:
1. STOP trading immediately
2. Review with Sentinel
3. Identify root cause
4. Address issue before resuming
5. Extend timeline if needed

**There is no shame in extending the timeline. There IS shame in blowing up again.**

---

## Weekly Check-In Format

### Sunday Evening Review (30 min)
**Mitch provides:**
- Last week's emotional state (1-10)
- Rule violations (if any)
- Biggest challenge this week
- What I learned
- What I'll do differently next week

**Sentinel provides:**
- Performance summary (P&L, win rate, trades)
- Comparison to expectations
- Regime analysis (favorable vs unfavorable days)
- Recommended focus for next week
- Encouragement + accountability

---

## The Contract

**I, Mitch, commit to:**
1. Following the 90-day roadmap to the letter
2. No shortcuts, no rushing, no skipping phases
3. Daily check-ins with Sentinel
4. Honest emotional journaling
5. Circuit breaker rules (no manual overrides)
6. Accepting $30-60/week as success in Year 1
7. Trusting the process even when it's boring

**Sentinel commits to:**
1. Daily morning briefings + EOD summaries
2. Weekly performance reports
3. Honest feedback (even when it hurts)
4. Holding you accountable
5. Celebrating small wins
6. Stopping you if edge disappears
7. Being your circuit breaker for emotional decisions

---

## Next Action (Right Now)

**Mitch:**
1. Read this entire roadmap
2. Read the NT backtest deep analysis
3. Decide: Do you commit to this 90-day plan?
4. If YES: Reply "I commit to the 90-day roadmap"
5. If NO: Tell me what needs to change

**Sentinel:**
- Awaiting your decision
- Ready to start Week 1 immediately
- No judgment either way

---

*Roadmap created: 2026-02-07 07:45 CT*
*Next update: After your decision*
