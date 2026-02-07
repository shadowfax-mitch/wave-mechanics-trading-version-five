# HEARTBEAT.md - Proactive Monitoring Checklist

*Run every 30 minutes during market hours (8:00 AM - 4:00 PM CT). Every 2 hours outside market hours.*

## 🔴 Critical — Alert Immediately
- [ ] Is the trading system process running? If crashed or unresponsive, alert immediately.
- [ ] Are there any NinjaTrader connection issues (disconnected from data feed or broker)?
- [ ] Has the daily loss limit been hit or is it within 20% of being hit?
- [ ] Are there any open positions with unrealized losses exceeding normal stop levels?
- [ ] Are there any file locking errors between Python and NinjaTrader C# bridge?

## ⚠️ Warning — Alert Within 15 Minutes
- [ ] Has the regime classification changed significantly? (e.g., low-vol to high-vol, trending to choppy)
- [ ] Are there unusual signal generation patterns? (sudden spike or drought in signals)
- [ ] Is the win rate for the current session significantly below the historical average?
- [ ] Are any log files showing repeated errors or warnings?
- [ ] Is disk space running low on the trading machine?
- [ ] Are S&P 500 futures (ES/MES) showing moves > 1% since last check?

## 📊 Bundle Into Daily Briefings

### Morning Briefing (7:30 AM CT)
- [ ] Overnight futures movement summary (MES, MNQ)
- [ ] Current regime assessment from wave mechanics (amplitude, frequency, energy)
- [ ] Key economic events scheduled for today (FOMC, NFP, CPI, etc.)
- [ ] Yesterday's trading performance recap (P&L, win rate, number of trades)
- [ ] Any system updates or patches that ran overnight
- [ ] Open issues or bugs from previous development sessions

### End-of-Day Summary (4:15 PM CT)
- [ ] Today's trading performance (P&L, trades, win rate, avg win vs avg loss)
- [ ] Regime summary — how did the market behave today vs. classification?
- [ ] Any anomalies or notable patterns detected
- [ ] System health status
- [ ] Suggested focus areas for evening development work

## 🛠️ Weekly (Sunday Evening, 7:00 PM CT)
- [ ] Weekly P&L summary and performance metrics
- [ ] Week-over-week comparison of key trading statistics
- [ ] Regime distribution for the week (% trending, % choppy, % volatile)
- [ ] Any parameter drift or model degradation signals
- [ ] Upcoming week's economic calendar highlights
- [ ] Code/system maintenance items that need attention
