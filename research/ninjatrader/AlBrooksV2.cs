#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    /// <summary>
    /// Al Brooks V2 Strategy — NinjaTrader 8 port of Python backtest
    ///
    /// Architecture:
    ///   1. Trend detection via normalized EMA slope
    ///   2. H2/L2 second-entry pattern state machines
    ///   3. Signal bar quality scoring
    ///   4. Market entry at bar close
    ///   5. Grace period (N bars, no stop) + ATR trailing stop
    ///
    /// Python reference: research/al_brooks_system/src/al_brooks_v2_strategy.py
    /// Best config (g7_a0.5_d0.5): PF=3.18, 73.9% WR, 2535 trades (2019-2026 MNQ 5-min)
    /// Walk-forward validated: OOS avg PF=3.06, min=2.72
    /// </summary>
    public class AlBrooksV2 : Strategy
    {
        #region Private Fields

        // ── Indicators ──
        private EMA emaIndicator;
        private Series<double> trSeries;
        private Series<double> smaAtr;

        // ── H2 state machine (second entry long) ──
        private int    h2ExtremeBar;
        private double h2ExtremePrice;
        private int    h2PullbackBar;
        private int    h2FirstEntryBar;
        private int    h2EntryCount;
        private int    h2SecondEntryBar;

        // ── L2 state machine (second entry short) ──
        private int    l2ExtremeBar;
        private double l2ExtremePrice;
        private int    l2PullbackBar;
        private int    l2FirstEntryBar;
        private int    l2EntryCount;
        private int    l2SecondEntryBar;

        // ── Trend ──
        private int currentTrend;  // 1=UP, -1=DOWN, 0=SIDEWAYS

        // ── Position tracking ──
        private int    myEntryBar;
        private double myEntryPrice;
        private double myStopPrice;
        private double myOriginalStop;
        private bool   stopIsActive;   // false during grace period
        private int    lastExitBar;

        // ── Circuit breakers ──
        private double   dailyPnl;
        private int      consecutiveLosses;
        private DateTime lastDate;

        // ── Pending stop for OnExecutionUpdate ──
        private double pendingStopPrice;

        #endregion

        #region OnStateChange

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Al Brooks V2 — H2/L2 second entries + grace period + ATR trailing stop";
                Name = "AlBrooksV2";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = false;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 30;

                // === VALIDATED BEST CONFIG (g7_a0.5_d0.5) ===
                // Trend
                EmaPeriod            = 20;
                TrendSlopeLookback   = 10;
                TrendSlopeThreshold  = 0.03;

                // Pattern
                PullbackMinAtr       = 0.3;
                PatternTimeout       = 30;
                PatternValidity      = 3;

                // Signal bar
                MinSignalQuality     = 60;
                MinBodyRatio         = 0.30;
                MaxWickRatio         = 0.70;
                MinBarSizeAtr        = 0.2;
                MaxBarSizeAtr        = 3.0;

                // Risk
                AtrPeriod            = 14;
                StopOffsetTicks      = 1;
                MaxStopAtr           = 1.5;

                // Grace period + ATR trail (the key edge)
                GracePeriodBars      = 7;
                UseAtrTrail          = true;
                AtrTrailActivation   = 0.5;
                AtrTrailDistance      = 0.5;

                // Fixed target (used when UseAtrTrail = false)
                RewardRiskRatio      = 1.5;
                MinTargetTicks       = 6;

                // Time
                MaxHoldBars          = 80;
                RthStartHour         = 8;
                RthStartMinute       = 30;
                RthEndHour           = 15;
                RthEndMinute         = 0;

                // Circuit breakers
                DailyLossLimit       = -200;
                MaxConsecLosses      = 4;

                // Entry modes
                AllowShorts          = false;
                AllowSidewaysEntries = false;
            }
            else if (State == State.Configure)
            {
            }
            else if (State == State.DataLoaded)
            {
                emaIndicator = EMA(EmaPeriod);
                trSeries = new Series<double>(this);
                smaAtr = new Series<double>(this);

                ResetH2State();
                ResetL2State();
                currentTrend = 0;

                myEntryBar = 0;
                myEntryPrice = 0;
                myStopPrice = 0;
                myOriginalStop = 0;
                stopIsActive = false;
                lastExitBar = -1;

                dailyPnl = 0;
                consecutiveLosses = 0;
                lastDate = DateTime.MinValue;
                pendingStopPrice = 0;
            }
        }

        #endregion

        #region State Machine Reset

        private void ResetH2State()
        {
            h2ExtremeBar = -1;
            h2ExtremePrice = double.NaN;
            h2PullbackBar = -1;
            h2FirstEntryBar = -1;
            h2EntryCount = 0;
            h2SecondEntryBar = -1;
        }

        private void ResetL2State()
        {
            l2ExtremeBar = -1;
            l2ExtremePrice = double.NaN;
            l2PullbackBar = -1;
            l2FirstEntryBar = -1;
            l2EntryCount = 0;
            l2SecondEntryBar = -1;
        }

        #endregion

        #region OnBarUpdate

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade)
                return;

            // ── 1. Compute SMA-based ATR ──
            ComputeAtr();
            double atrVal = smaAtr[0];
            if (double.IsNaN(atrVal) || atrVal <= 0)
                return;

            // ── 2. Daily reset ──
            DateTime today = Time[0].Date;
            if (today != lastDate)
            {
                lastDate = today;
                dailyPnl = 0;
                consecutiveLosses = 0;

                // Close overnight position
                if (Position.MarketPosition == MarketPosition.Long)
                {
                    ExitLong("NewDay", "LongEntry");
                    return;
                }
                else if (Position.MarketPosition == MarketPosition.Short)
                {
                    ExitShort("NewDay", "ShortEntry");
                    return;
                }
            }

            // ── 3. RTH filter ──
            double timeF = Time[0].Hour + Time[0].Minute / 60.0;
            double rthStart = RthStartHour + RthStartMinute / 60.0;
            double rthEnd = RthEndHour + RthEndMinute / 60.0;
            if (timeF < rthStart || timeF >= rthEnd)
                return;

            // ── 4. Detect trend ──
            currentTrend = DetectTrend(atrVal);

            // ── 5. Update pattern state machines ──
            if (currentTrend != -1)  // H2 in UP or SIDEWAYS
                UpdateH2State(atrVal);
            if (currentTrend != 1)   // L2 in DOWN or SIDEWAYS
                UpdateL2State(atrVal);

            // ── 6. Manage position ──
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                ManagePosition(atrVal);
                return;
            }

            // ── 7. Skip entry on same bar as exit ──
            if (CurrentBar == lastExitBar)
                return;

            // ── 8. Circuit breakers ──
            if (dailyPnl <= DailyLossLimit)
                return;
            if (consecutiveLosses >= MaxConsecLosses)
                return;

            // ── 9. Check for entry ──
            CheckEntrySignals(atrVal);
        }

        #endregion

        #region ATR Calculation

        /// <summary>
        /// SMA-based ATR matching Python's rolling mean of True Range.
        /// </summary>
        private void ComputeAtr()
        {
            if (CurrentBar == 0)
                trSeries[0] = High[0] - Low[0];
            else
                trSeries[0] = Math.Max(High[0] - Low[0],
                    Math.Max(Math.Abs(High[0] - Close[1]),
                             Math.Abs(Low[0] - Close[1])));

            if (CurrentBar >= AtrPeriod - 1)
            {
                double sum = 0;
                for (int i = 0; i < AtrPeriod; i++)
                    sum += trSeries[i];
                smaAtr[0] = sum / AtrPeriod;
            }
            else
            {
                smaAtr[0] = double.NaN;
            }
        }

        #endregion

        #region Trend Detection

        /// <summary>
        /// Normalized EMA slope trend detection.
        /// slope = (EMA_now - EMA_lookback) / (lookback * ATR)
        /// UP if close > EMA and slope > threshold
        /// DOWN if close < EMA and slope < -threshold
        /// </summary>
        private int DetectTrend(double atrVal)
        {
            if (CurrentBar < Math.Max(EmaPeriod, TrendSlopeLookback))
                return 0;

            double emaNow = emaIndicator[0];
            double emaPrev = emaIndicator[TrendSlopeLookback];

            if (double.IsNaN(emaNow) || double.IsNaN(emaPrev) || atrVal <= 0)
                return 0;

            double slope = (emaNow - emaPrev) / (TrendSlopeLookback * atrVal);

            if (Close[0] > emaNow && slope > TrendSlopeThreshold)
                return 1;   // UP
            else if (Close[0] < emaNow && slope < -TrendSlopeThreshold)
                return -1;  // DOWN
            else
                return 0;   // SIDEWAYS
        }

        #endregion

        #region H2 State Machine

        /// <summary>
        /// H2 second-entry long state machine.
        /// 1. New 20-bar high → start tracking
        /// 2. Pullback from high ≥ pullback_min * ATR
        /// 3. First bounce (high > prev high) → count = 1
        /// 4. Second bounce (high > prev high, no new extreme) → count = 2 → H2 signal
        /// </summary>
        private void UpdateH2State(double atrVal)
        {
            // Expire second entry signal after PatternValidity bars
            if (h2SecondEntryBar >= 0 && CurrentBar - h2SecondEntryBar >= PatternValidity)
            {
                h2SecondEntryBar = -1;
                h2EntryCount = 0;
            }

            // New 20-bar high resets tracking
            int lookbackBars = Math.Min(20, CurrentBar);
            double recentHigh = double.MinValue;
            for (int i = 1; i <= lookbackBars; i++)
                recentHigh = Math.Max(recentHigh, High[i]);

            if (High[0] > recentHigh)
            {
                h2ExtremeBar = CurrentBar;
                h2ExtremePrice = High[0];
                h2PullbackBar = -1;
                h2FirstEntryBar = -1;
                h2EntryCount = 0;
                h2SecondEntryBar = -1;
                return;
            }

            // Need an extreme to track
            if (h2ExtremeBar < 0)
                return;

            // Timeout
            if (CurrentBar - h2ExtremeBar > PatternTimeout)
            {
                h2ExtremeBar = -1;
                return;
            }

            // Detect pullback from high
            if (h2PullbackBar < 0)
            {
                double pullbackSize = h2ExtremePrice - Low[0];
                if (pullbackSize >= PullbackMinAtr * atrVal)
                    h2PullbackBar = CurrentBar;
                return;
            }

            // First entry: first bounce after pullback
            if (h2EntryCount == 0 && h2FirstEntryBar < 0)
            {
                if (CurrentBar > h2PullbackBar && High[0] > High[1])
                {
                    h2FirstEntryBar = CurrentBar;
                    h2EntryCount = 1;
                }
                return;
            }

            // Second entry
            if (h2EntryCount == 1)
            {
                if (CurrentBar - h2FirstEntryBar > PatternTimeout)
                {
                    h2EntryCount = 0;
                    h2FirstEntryBar = -1;
                    return;
                }

                if (High[0] > High[1] && CurrentBar > h2FirstEntryBar)
                {
                    // Verify no new high beyond original extreme
                    int barsAgoFirst = CurrentBar - h2FirstEntryBar;
                    double maxSinceFirst = double.MinValue;
                    for (int i = 1; i <= barsAgoFirst; i++)
                        maxSinceFirst = Math.Max(maxSinceFirst, High[i]);

                    if (maxSinceFirst <= h2ExtremePrice)
                    {
                        h2EntryCount = 2;
                        h2SecondEntryBar = CurrentBar;
                    }
                }
            }
        }

        #endregion

        #region L2 State Machine

        /// <summary>
        /// L2 second-entry short state machine (mirror of H2).
        /// </summary>
        private void UpdateL2State(double atrVal)
        {
            if (l2SecondEntryBar >= 0 && CurrentBar - l2SecondEntryBar >= PatternValidity)
            {
                l2SecondEntryBar = -1;
                l2EntryCount = 0;
            }

            int lookbackBars = Math.Min(20, CurrentBar);
            double recentLow = double.MaxValue;
            for (int i = 1; i <= lookbackBars; i++)
                recentLow = Math.Min(recentLow, Low[i]);

            if (Low[0] < recentLow)
            {
                l2ExtremeBar = CurrentBar;
                l2ExtremePrice = Low[0];
                l2PullbackBar = -1;
                l2FirstEntryBar = -1;
                l2EntryCount = 0;
                l2SecondEntryBar = -1;
                return;
            }

            if (l2ExtremeBar < 0)
                return;

            if (CurrentBar - l2ExtremeBar > PatternTimeout)
            {
                l2ExtremeBar = -1;
                return;
            }

            if (l2PullbackBar < 0)
            {
                double pullbackSize = High[0] - l2ExtremePrice;
                if (pullbackSize >= PullbackMinAtr * atrVal)
                    l2PullbackBar = CurrentBar;
                return;
            }

            if (l2EntryCount == 0 && l2FirstEntryBar < 0)
            {
                if (CurrentBar > l2PullbackBar && Low[0] < Low[1])
                {
                    l2FirstEntryBar = CurrentBar;
                    l2EntryCount = 1;
                }
                return;
            }

            if (l2EntryCount == 1)
            {
                if (CurrentBar - l2FirstEntryBar > PatternTimeout)
                {
                    l2EntryCount = 0;
                    l2FirstEntryBar = -1;
                    return;
                }

                if (Low[0] < Low[1] && CurrentBar > l2FirstEntryBar)
                {
                    int barsAgoFirst = CurrentBar - l2FirstEntryBar;
                    double minSinceFirst = double.MaxValue;
                    for (int i = 1; i <= barsAgoFirst; i++)
                        minSinceFirst = Math.Min(minSinceFirst, Low[i]);

                    if (minSinceFirst >= l2ExtremePrice)
                    {
                        l2EntryCount = 2;
                        l2SecondEntryBar = CurrentBar;
                    }
                }
            }
        }

        #endregion

        #region Signal Bar Quality

        /// <summary>
        /// Score signal bar quality (0-120). Checks bar size, body ratio,
        /// wick alignment, and direction alignment.
        /// </summary>
        private double ScoreSignalBar(bool isLong, double atrVal)
        {
            double barRange = High[0] - Low[0];
            double body = Math.Abs(Close[0] - Open[0]);
            double upperWick = High[0] - Math.Max(Open[0], Close[0]);
            double lowerWick = Math.Min(Open[0], Close[0]) - Low[0];
            bool isBullish = Close[0] > Open[0];

            double score = 100.0;

            // Bar size
            if (barRange < MinBarSizeAtr * atrVal)
                score -= 40;
            else if (barRange > MaxBarSizeAtr * atrVal)
                score -= 30;

            // Body ratio
            double bodyRatio = barRange > 0 ? body / barRange : 0;
            if (bodyRatio < MinBodyRatio)
                score -= 30;
            else
                score += Math.Min(20, bodyRatio * 20);

            // Wick alignment
            if (isLong && barRange > 0 && upperWick > barRange * MaxWickRatio)
                score -= 25;
            else if (!isLong && barRange > 0 && lowerWick > barRange * MaxWickRatio)
                score -= 25;

            // Direction alignment
            if (isLong && !isBullish)
                score -= 35;
            else if (!isLong && isBullish)
                score -= 35;

            return Math.Max(0, Math.Min(120, score));
        }

        #endregion

        #region Entry Logic

        /// <summary>
        /// Check for H2/L2 entry signals. Filters by trend, signal quality,
        /// and minimum stop distance.
        /// </summary>
        private void CheckEntrySignals(double atrVal)
        {
            // Block sideways entries if disabled
            if (currentTrend == 0 && !AllowSidewaysEntries)
                return;

            // ── Check H2 (second entry long) ──
            bool h2Active = h2EntryCount == 2
                && h2SecondEntryBar >= 0
                && CurrentBar - h2SecondEntryBar < PatternValidity
                && (currentTrend == 1 || currentTrend == 0);

            // ── Check L2 (second entry short) ──
            bool l2Active = AllowShorts
                && l2EntryCount == 2
                && l2SecondEntryBar >= 0
                && CurrentBar - l2SecondEntryBar < PatternValidity
                && (currentTrend == -1 || currentTrend == 0);

            if (!h2Active && !l2Active)
                return;

            // Prefer H2 over L2 if both active
            bool isLong = h2Active;

            // With-trend check: H2 needs UP trend, L2 needs DOWN trend
            // (sideways already blocked above if AllowSidewaysEntries = false)
            bool isWithTrend = (isLong && currentTrend == 1) || (!isLong && currentTrend == -1);

            // Counter-trend not allowed in best config
            if (!isWithTrend && currentTrend != 0)
                return;

            // Signal bar quality
            double quality = ScoreSignalBar(isLong, atrVal);
            if (quality < MinSignalQuality)
                return;

            // Calculate stop
            double tick = TickSize;
            double offset = StopOffsetTicks * tick;
            double maxStop = MaxStopAtr * atrVal;

            double rawStop, stopDist;

            if (isLong)
            {
                rawStop = Low[0] - offset;
                stopDist = Close[0] - rawStop;
                if (stopDist > maxStop)
                {
                    rawStop = Close[0] - maxStop;
                    stopDist = maxStop;
                }
            }
            else
            {
                rawStop = High[0] + offset;
                stopDist = rawStop - Close[0];
                if (stopDist > maxStop)
                {
                    rawStop = Close[0] + maxStop;
                    stopDist = maxStop;
                }
            }

            rawStop = Instrument.MasterInstrument.RoundToTickSize(rawStop);

            // Minimum stop distance check
            if (MinStopTicks > 0 && Math.Abs(Close[0] - rawStop) < MinStopTicks * tick)
                return;

            // Store pending stop for OnExecutionUpdate
            pendingStopPrice = rawStop;

            // Enter
            if (isLong)
            {
                EnterLong(1, "LongEntry");
                // Reset H2 state after entry
                ResetH2State();
            }
            else
            {
                EnterShort(1, "ShortEntry");
                ResetL2State();
            }
        }

        #endregion

        #region Position Management

        /// <summary>
        /// Manage open position: grace period, stop checks, ATR trailing, time exit.
        /// During grace period, no stop is set (no protection, matching Python).
        /// After grace, stop is activated via SetStopLoss.
        /// ATR trail updates every bar (even during grace), but stop only fires after grace.
        /// </summary>
        private void ManagePosition(double atrVal)
        {
            int barsHeld = CurrentBar - myEntryBar;
            bool isLong = Position.MarketPosition == MarketPosition.Long;

            // ── Activate stop after grace period ──
            if (barsHeld >= GracePeriodBars && !stopIsActive)
            {
                string entryName = isLong ? "LongEntry" : "ShortEntry";
                SetStopLoss(entryName, CalculationMode.Price, myStopPrice, false);
                stopIsActive = true;
            }

            // ── Fixed target (only when ATR trail is OFF) ──
            if (!UseAtrTrail)
            {
                double targetPrice;
                double risk = Math.Abs(myEntryPrice - myOriginalStop);
                double targetDist = risk * RewardRiskRatio;
                double minTarget = MinTargetTicks * TickSize;
                if (targetDist < minTarget)
                    targetDist = minTarget;

                if (isLong)
                    targetPrice = myEntryPrice + targetDist;
                else
                    targetPrice = myEntryPrice - targetDist;

                targetPrice = Instrument.MasterInstrument.RoundToTickSize(targetPrice);
                string entryName = isLong ? "LongEntry" : "ShortEntry";
                SetProfitTarget(entryName, CalculationMode.Price, targetPrice);
            }

            // ── Time exit ──
            if (barsHeld >= MaxHoldBars)
            {
                if (isLong)
                    ExitLong("TimeExit", "LongEntry");
                else
                    ExitShort("TimeExit", "ShortEntry");
                return;
            }

            // ── ATR trailing stop ──
            if (UseAtrTrail && !double.IsNaN(atrVal) && atrVal > 0)
            {
                double risk = Math.Abs(myEntryPrice - myOriginalStop);
                double activation = AtrTrailActivation * risk;
                double trailDist = AtrTrailDistance * atrVal;

                if (isLong)
                {
                    double unrealized = High[0] - myEntryPrice;
                    if (unrealized >= activation)
                    {
                        double newStop = High[0] - trailDist;
                        newStop = Instrument.MasterInstrument.RoundToTickSize(newStop);
                        if (newStop > myStopPrice)
                        {
                            myStopPrice = newStop;
                            if (stopIsActive)
                                SetStopLoss("LongEntry", CalculationMode.Price, myStopPrice, false);
                        }
                    }
                }
                else
                {
                    double unrealized = myEntryPrice - Low[0];
                    if (unrealized >= activation)
                    {
                        double newStop = Low[0] + trailDist;
                        newStop = Instrument.MasterInstrument.RoundToTickSize(newStop);
                        if (newStop < myStopPrice)
                        {
                            myStopPrice = newStop;
                            if (stopIsActive)
                                SetStopLoss("ShortEntry", CalculationMode.Price, myStopPrice, false);
                        }
                    }
                }
            }
        }

        #endregion

        #region Execution Tracking

        protected override void OnExecutionUpdate(Execution execution, string executionId,
            double price, int quantity, MarketPosition marketPosition,
            string orderId, DateTime time)
        {
            // ── Track entry fill ──
            if ((execution.Order.Name == "LongEntry" || execution.Order.Name == "ShortEntry")
                && marketPosition != MarketPosition.Flat)
            {
                myEntryBar = CurrentBar;
                myEntryPrice = price;
                myStopPrice = pendingStopPrice;
                myOriginalStop = pendingStopPrice;
                stopIsActive = false;
            }

            // ── Track position close → update circuit breakers ──
            if (marketPosition == MarketPosition.Flat
                && SystemPerformance.AllTrades.Count > 0)
            {
                Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                double pnl = lastTrade.ProfitCurrency;

                dailyPnl += pnl;
                lastExitBar = CurrentBar;

                if (pnl < 0)
                    consecutiveLosses++;
                else
                    consecutiveLosses = 0;
            }
        }

        #endregion

        #region Properties — Entry

        [NinjaScriptProperty]
        [Range(1, 200)]
        [Display(Name = "EMA Period", Description = "EMA period for trend detection",
            Order = 1, GroupName = "1. Trend")]
        public int EmaPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(1, 50)]
        [Display(Name = "Trend Slope Lookback", Description = "Bars to measure EMA slope over",
            Order = 2, GroupName = "1. Trend")]
        public int TrendSlopeLookback { get; set; }

        [NinjaScriptProperty]
        [Range(0.001, 1.0)]
        [Display(Name = "Trend Slope Threshold", Description = "Normalized slope threshold for UP/DOWN",
            Order = 3, GroupName = "1. Trend")]
        public double TrendSlopeThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Allow Shorts", Description = "Allow L2 short entries",
            Order = 4, GroupName = "1. Trend")]
        public bool AllowShorts { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Allow Sideways Entries", Description = "Allow entries in sideways trend",
            Order = 5, GroupName = "1. Trend")]
        public bool AllowSidewaysEntries { get; set; }

        #endregion

        #region Properties — Pattern

        [NinjaScriptProperty]
        [Range(0.01, 5.0)]
        [Display(Name = "Pullback Min ATR", Description = "Minimum pullback size in ATR multiples",
            Order = 1, GroupName = "2. Pattern")]
        public double PullbackMinAtr { get; set; }

        [NinjaScriptProperty]
        [Range(5, 100)]
        [Display(Name = "Pattern Timeout", Description = "Bars before pattern expires",
            Order = 2, GroupName = "2. Pattern")]
        public int PatternTimeout { get; set; }

        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name = "Pattern Validity", Description = "Bars that H2/L2 signal stays valid",
            Order = 3, GroupName = "2. Pattern")]
        public int PatternValidity { get; set; }

        #endregion

        #region Properties — Signal Bar

        [NinjaScriptProperty]
        [Range(0, 120)]
        [Display(Name = "Min Signal Quality", Description = "Minimum signal bar quality score (0-120)",
            Order = 1, GroupName = "3. Signal Bar")]
        public int MinSignalQuality { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "Min Body Ratio", Description = "Minimum body/range ratio",
            Order = 2, GroupName = "3. Signal Bar")]
        public double MinBodyRatio { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "Max Wick Ratio", Description = "Maximum unfavorable wick/range ratio",
            Order = 3, GroupName = "3. Signal Bar")]
        public double MaxWickRatio { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 5.0)]
        [Display(Name = "Min Bar Size ATR", Description = "Minimum bar range in ATR multiples",
            Order = 4, GroupName = "3. Signal Bar")]
        public double MinBarSizeAtr { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 10.0)]
        [Display(Name = "Max Bar Size ATR", Description = "Maximum bar range in ATR multiples",
            Order = 5, GroupName = "3. Signal Bar")]
        public double MaxBarSizeAtr { get; set; }

        #endregion

        #region Properties — Risk / Stop

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "ATR Period", Description = "ATR period (SMA-based, not Wilder)",
            Order = 1, GroupName = "4. Risk")]
        public int AtrPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(0, 20)]
        [Display(Name = "Stop Offset Ticks", Description = "Ticks beyond signal bar for stop placement",
            Order = 2, GroupName = "4. Risk")]
        public int StopOffsetTicks { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 10.0)]
        [Display(Name = "Max Stop ATR", Description = "Maximum stop distance in ATR multiples",
            Order = 3, GroupName = "4. Risk")]
        public double MaxStopAtr { get; set; }

        [NinjaScriptProperty]
        [Range(0, 100)]
        [Display(Name = "Min Stop Ticks", Description = "Minimum stop distance in ticks (0 = no minimum)",
            Order = 4, GroupName = "4. Risk")]
        public int MinStopTicks { get; set; }

        #endregion

        #region Properties — Grace Period + Trail

        [NinjaScriptProperty]
        [Range(0, 30)]
        [Display(Name = "Grace Period Bars", Description = "Bars after entry with no stop (0 = immediate stop)",
            Order = 1, GroupName = "5. Grace + Trail")]
        public int GracePeriodBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use ATR Trail", Description = "Use ATR trailing stop (disables fixed target)",
            Order = 2, GroupName = "5. Grace + Trail")]
        public bool UseAtrTrail { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 10.0)]
        [Display(Name = "ATR Trail Activation", Description = "Start trailing after this × risk in profit",
            Order = 3, GroupName = "5. Grace + Trail")]
        public double AtrTrailActivation { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 10.0)]
        [Display(Name = "ATR Trail Distance", Description = "Trail distance in ATR multiples",
            Order = 4, GroupName = "5. Grace + Trail")]
        public double AtrTrailDistance { get; set; }

        #endregion

        #region Properties — Fixed Target

        [NinjaScriptProperty]
        [Range(0.1, 10.0)]
        [Display(Name = "Reward/Risk Ratio", Description = "Target = risk × this (used when ATR trail is OFF)",
            Order = 1, GroupName = "6. Fixed Target")]
        public double RewardRiskRatio { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Min Target Ticks", Description = "Minimum target distance in ticks",
            Order = 2, GroupName = "6. Fixed Target")]
        public int MinTargetTicks { get; set; }

        #endregion

        #region Properties — Time / Session

        [NinjaScriptProperty]
        [Range(1, 500)]
        [Display(Name = "Max Hold Bars", Description = "Time exit after N bars",
            Order = 1, GroupName = "7. Time")]
        public int MaxHoldBars { get; set; }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "RTH Start Hour", Description = "Session start hour (CT)",
            Order = 2, GroupName = "7. Time")]
        public int RthStartHour { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "RTH Start Minute", Description = "Session start minute",
            Order = 3, GroupName = "7. Time")]
        public int RthStartMinute { get; set; }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "RTH End Hour", Description = "Session end hour (CT)",
            Order = 4, GroupName = "7. Time")]
        public int RthEndHour { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "RTH End Minute", Description = "Session end minute",
            Order = 5, GroupName = "7. Time")]
        public int RthEndMinute { get; set; }

        #endregion

        #region Properties — Circuit Breakers

        [NinjaScriptProperty]
        [Range(-100000, 0)]
        [Display(Name = "Daily Loss Limit", Description = "Max daily loss $ before stopping",
            Order = 1, GroupName = "8. Circuit Breakers")]
        public double DailyLossLimit { get; set; }

        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name = "Max Consec Losses", Description = "Pause after N consecutive losses",
            Order = 2, GroupName = "8. Circuit Breakers")]
        public int MaxConsecLosses { get; set; }

        #endregion
    }
}
