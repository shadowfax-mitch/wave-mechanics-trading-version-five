# V5 VALIDATION PROTOCOL - Rigorous Testing Requirements

**Version:** 1.0  
**Date:** 2026-02-07  
**Companion to:** V5_CONSTITUTION.md

---

## PURPOSE

**This protocol exists because:**
- V4 Zone Scalper: +$4,966 backtest → FAILED 10-week live test
- V2: 2,006 trades revealed break-even truth (1.02 PF)
- V1: Only 13 trades (too small to validate)

**V5 will NOT deploy without passing ALL validation gates.**

---

## PHASE 1: HISTORICAL BACKTEST (Weeks 1-4)

### Requirements:

**Data:**
- Minimum 6 months historical data
- Preferably 12 months for seasonal coverage
- MES or MNQ 5-minute bars (or higher timeframe)
- Include overnight sessions if strategy trades them

**Metrics to Track:**
- Total trades (target: 100+ minimum)
- Net P/L after commissions + slippage
- Win rate
- Profit factor (target: >2.0)
- Maximum drawdown
- Average trade
- Average time in market
- Sharpe ratio (target: >1.5)

**Transaction Costs:**
- Commission: $2.00 per round-turn
- Slippage: $2.50 per trade (0.25 points on MES, 1.0 point on MNQ)
- Must be profitable AFTER costs

**Pass Criteria:**
- ✅ 100+ trades executed
- ✅ Net P/L > $500 (after costs)
- ✅ Profit Factor > 2.0
- ✅ Win Rate > 50%
- ✅ Max drawdown < $1,000

**Fail Criteria:**
- ❌ <100 trades (insufficient sample)
- ❌ Unprofitable after costs
- ❌ Profit factor < 1.5
- ❌ Max drawdown > $2,000

**If Pass:** Proceed to Phase 2  
**If Fail:** Return to strategy design

---

## PHASE 2: WALK-FORWARD ANALYSIS (Week 5)

### Requirements:

**Split data into 3-4 periods:**
- Train on 60%, test on next 20%, validate on final 20%
- Example: 12 months = Train (7 months), Test (2.5 months), Validate (2.5 months)

**Metrics to Compare:**
- Does strategy maintain profit factor across all periods?
- Are drawdowns similar across periods?
- Does performance degrade over time?

**Pass Criteria:**
- ✅ Profitable in ALL periods (train, test, validate)
- ✅ Profit factor variance < 30% across periods
- ✅ No catastrophic failure in any period

**Fail Criteria:**
- ❌ Unprofitable in any period
- ❌ Profit factor drops >50% in test/validate
- ❌ Max drawdown increases >100% in out-of-sample

**If Pass:** Proceed to Phase 3  
**If Fail:** Strategy is overfit, return to design

---

## PHASE 3: NINJTRADER STRATEGY ANALYZER (Week 6)

### Requirements:

**Implementation:**
- Convert Python strategy to C# NinjaScript
- Implement exact same logic (no "improvements")
- Use same transaction cost assumptions

**Validation:**
- Run Strategy Analyzer on SAME data as Python backtest
- Compare metrics: trades, P/L, win rate, profit factor

**Pass Criteria:**
- ✅ NT trade count within 10% of Python
- ✅ NT P/L within 20% of Python
- ✅ NT win rate within 5% of Python
- ✅ NT profit factor within 0.3 of Python

**Fail Criteria:**
- ❌ Trade count differs >25%
- ❌ P/L differs >40%
- ❌ NT shows losses where Python shows profit

**If Significant Difference Found:**
1. Debug logic differences (order handling, fill assumptions, etc.)
2. Fix Python or C# to align
3. Re-validate

**If Pass:** Proceed to Phase 4  
**If Fail:** Fix alignment issues before continuing

---

## PHASE 4: PAPER TRADING (Weeks 7-10)

### Requirements:

**Duration:**
- Minimum 4 weeks (20 trading days)
- Target: 15-30 trades depending on frequency

**Setup:**
- NinjaTrader simulation account
- Live market data (not replay)
- Real-time signal generation
- Log every trade

**Metrics to Track:**
- Cumulative P/L (target: $400+ over 4 weeks = $100/week)
- Win rate
- Profit factor
- Slippage vs backtest expectations
- Signal generation timing (latency issues?)

**Weekly Check-ins:**
- Week 1: Is strategy generating signals? Frequency as expected?
- Week 2: Are fills realistic? P/L tracking backtest?
- Week 3: Any unexpected behavior? Drawdowns acceptable?
- Week 4: Final assessment vs backtest

**Pass Criteria:**
- ✅ Paper P/L ≥ 80% of backtest expectation
- ✅ No catastrophic losses (>$500 single trade)
- ✅ Slippage within expectations
- ✅ System runs reliably (no crashes, disconnects handled)

**Fail Criteria:**
- ❌ Paper P/L < 50% of backtest
- ❌ Unprofitable over 4 weeks
- ❌ System reliability issues
- ❌ Execution problems (missed fills, bad prices)

**If Pass:** Proceed to Phase 5  
**If Fail:** Diagnose issues, fix, re-paper trade 2 more weeks

---

## PHASE 5: MICRO-LIVE DEPLOYMENT (Weeks 11-22)

### Requirements:

**Account Setup:**
- $3,000 minimum capital
- 1 contract only (MES or MNQ)
- Circuit breakers ACTIVE (-$80 daily, -$150 weekly, 2 consecutive losses)

**Duration:**
- Minimum 12 weeks (3 months)
- Target: 40-80 trades

**Metrics to Track:**
- Weekly P/L (target: $100/week average)
- Cumulative P/L (target: $1,200+ over 12 weeks)
- Win rate
- Profit factor
- Drawdowns
- Circuit breaker activations

**Weekly Review:**
- Compare live vs paper vs backtest
- Track execution quality
- Monitor emotional discipline
- Check for system degradation

**Pass Criteria:**
- ✅ Profitable 9 out of 12 weeks
- ✅ Cumulative P/L > $1,000 (after costs)
- ✅ Profit factor > 1.5
- ✅ Max drawdown < $800
- ✅ Circuit breakers used < 5 times

**Fail Criteria:**
- ❌ Unprofitable after 12 weeks
- ❌ Profit factor < 1.2
- ❌ Max drawdown > $1,500
- ❌ Circuit breakers triggered >10 times
- ❌ Emotional breakdown (can't follow system)

**If Pass:** Strategy is VALIDATED, may scale to 2 contracts  
**If Fail:** Strategy does NOT work, return to design phase

---

## PHASE 6: SCALING (Week 23+)

### Requirements:

**Only after Phase 5 success:**
- Scale to 2 contracts
- Monitor for 4 more weeks
- Ensure P/L doubles (~$200/week target)

**If Scaling Successful:**
- Consider 3 contracts after 100+ profitable live trades
- Max 5 contracts on $10K account

**Risk Management:**
- Never risk >2% per trade
- Never exceed circuit breaker limits even with more contracts

---

## EMERGENCY STOP PROTOCOL

**Immediately halt live trading if:**
- 5 consecutive losses (regardless of $ amount)
- Single day loss > $200
- Weekly loss > $300
- Profit factor drops below 1.0 over any 20-trade window
- Unusual market conditions (circuit breakers, flash crash, etc.)

**Resume only after:**
- Root cause analysis completed
- Strategy re-validated in paper trading (2 weeks minimum)
- Confidence restored

---

## DOCUMENTATION REQUIREMENTS

**Each phase must produce:**

**Phase 1:** Backtest report (metrics, equity curve, trade log)  
**Phase 2:** Walk-forward analysis report (period-by-period breakdown)  
**Phase 3:** NT Strategy Analyzer comparison report  
**Phase 4:** Paper trading journal (weekly summaries)  
**Phase 5:** Live trading journal (weekly P/L, lessons learned)

**Store in:** `~/.openclaw/workspace/v5_validation_reports/`

---

## FINAL VALIDATION CHECKLIST

Before declaring V5 successful:

- [ ] 100+ backtest trades (>2.0 PF)
- [ ] Walk-forward analysis passed
- [ ] NT Strategy Analyzer validated
- [ ] 4 weeks paper trading successful
- [ ] 12 weeks live trading profitable
- [ ] Averaged $100/week in live trading
- [ ] Can explain WHY strategy works (not just that it does)
- [ ] System is robust (doesn't break with small changes)
- [ ] Emotional discipline maintained

**If ALL boxes checked: V5 IS VALIDATED.**

**If ANY box unchecked: V5 is incomplete.**

---

**Version History:**
- v1.0 (2026-02-07): Initial protocol based on V1-V4 lessons

**Authors:** Mitch & Sentinel

*"Validate rigorously. Deploy confidently. Scale carefully."*
