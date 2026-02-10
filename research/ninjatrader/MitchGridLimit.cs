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
    /// Mitch Grid Limit Strategy — 1:1 port of Python backtest
    ///
    /// Architecture (5 layers in series):
    ///   1. Trend structure detection (HH/HL/LH/LL state machine)
    ///   2. Pullback entry signals (1st + 2nd entries in confirmed trend)
    ///   3. Grid probability filter (8 ultra cells, split-half validated)
    ///   4. Limit order entry at swing price (5-bar timeout)
    ///   5. Trail-only exit (structure-based trailing stop, no fixed target)
    ///
    /// Python reference: research/modules/mitch_grid_strategy.py (backtest_grid_limit)
    /// Validated: 479 trades, 33.6% WR, 1.33 PF, +$3,014 (2019-2026 MNQ 5-min)
    /// </summary>
    public class MitchGridLimit : Strategy
    {
        #region Private Fields

        // ── Indicators ──
        private EMA emaIndicator;
        private Series<double> trSeries;    // true range per bar
        private Series<double> smaAtr;      // SMA-based ATR(14)

        // ── Swing history (last 2 of each, for trend classification) ──
        private double swingHigh1, swingHigh2; // most recent, prior
        private double swingLow1, swingLow2;

        // ── Trend state machine ──
        // 0=unknown, 1=up, -1=down, 2=range
        private int trendState;

        // ── Pullback counters ──
        private int longPullbackCount;
        private int shortPullbackCount;

        // ── Current bar swing detection results ──
        private bool barIsSwingHigh;
        private bool barIsSwingLow;
        private double barSwingHighPrice;
        private double barSwingLowPrice;

        // ── Current bar signal (from state machine) ──
        private int barSignalDir;           // 0=none, 1=long, -1=short
        private double barSignalStop;       // initial stop price
        private double barSignalLimitPrice; // limit order price (swing price)

        // ── Pending entry order ──
        private Order entryOrder;
        private int pendingOrderBar;
        private double pendingStopPrice;    // stored so OnExecutionUpdate can read it

        // ── Position tracking ──
        private int myEntryBar;
        private double myEntryPrice;
        private double currentStopPrice;
        private bool breakevenMoved;
        private int trailCount;
        private int lastExitBar;

        // ── Circuit breaker ──
        private double dailyPnl;
        private int consecutiveLosses;
        private DateTime lastDate;

        // ── Grid cells ──
        private HashSet<string> activeCells;
        private bool gridFilterEnabled;
        private bool useUltraMode;  // true = 4-axis (ultra), false = 3-axis (fine)

        // ── Signal bar filter stats (debug) ──
        private int signalBarPassed;
        private int signalBarFailed;

        #endregion

        #region OnStateChange

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Mitch Grid Limit — Al Brooks structure + grid filter + limit entries + trail-only exits";
                Name = "MitchGridLimit";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = false;
                IsFillLimitOnTouch = true;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 70;

                // === VALIDATED OPTIMAL PARAMETERS ===
                SwingStrength    = 2;
                EmaPeriod        = 21;
                AtrPeriod        = 14;
                StopBufferAtr    = 1.5;
                MaxStopAtr       = 2.0;
                TrailBufferAtr   = 0.8;
                UseBreakeven     = true;
                LimitOrderTimeout = 5;
                MaxHoldBars      = 90;
                DailyLossLimit   = -200;
                MaxConsecLosses  = 3;
                GridFilterMode   = 0;  // 0=None, 1=Fine(6), 2=Fine(10), 3=Ultra(8)
                UseSignalBarFilter = true;
                SignalBarClosePct  = 0.40;
                SignalBarBodyPct   = 0.15;
            }
            else if (State == State.Configure)
            {
            }
            else if (State == State.DataLoaded)
            {
                emaIndicator = EMA(EmaPeriod);
                trSeries = new Series<double>(this);
                smaAtr = new Series<double>(this);

                // Trend state
                swingHigh1 = double.NaN;
                swingHigh2 = double.NaN;
                swingLow1 = double.NaN;
                swingLow2 = double.NaN;
                trendState = 0;
                longPullbackCount = 0;
                shortPullbackCount = 0;

                // Position
                lastDate = DateTime.MinValue;
                myEntryBar = 0;
                myEntryPrice = 0;
                currentStopPrice = 0;
                breakevenMoved = false;
                trailCount = 0;
                lastExitBar = -1;
                dailyPnl = 0;
                consecutiveLosses = 0;

                // Grid filter setup based on GridFilterMode
                InitializeGridFilter();

                // Signal bar filter stats
                signalBarPassed = 0;
                signalBarFailed = 0;
            }
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
            }

            // ── 3. Detect swing on current bar ──
            DetectSwing();

            // ── 4. Update trend state machine + generate signals ──
            UpdateTrendAndSignals(atrVal);

            // ── 5. Position management (trail + time exit) ──
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                UpdateTrailingStop(atrVal);

                if (CurrentBar - myEntryBar >= MaxHoldBars)
                {
                    if (Position.MarketPosition == MarketPosition.Long)
                        ExitLong("TimeExit", "LongEntry");
                    else
                        ExitShort("TimeExit", "ShortEntry");
                }
                return;
            }

            // ── 6. Pending order timeout ──
            if (entryOrder != null
                && (entryOrder.OrderState == OrderState.Working
                    || entryOrder.OrderState == OrderState.Accepted))
            {
                if (CurrentBar - pendingOrderBar > LimitOrderTimeout)
                {
                    CancelOrder(entryOrder);
                    entryOrder = null;
                }
            }

            // ── 7. Skip entry on same bar as exit ──
            if (CurrentBar == lastExitBar)
                return;

            // ── 8. Circuit breakers ──
            if (dailyPnl <= DailyLossLimit)
                return;
            if (consecutiveLosses >= MaxConsecLosses)
                return;

            // ── 9. RTH filter (8:30-15:00 CT) ──
            double timeF = Time[0].Hour + Time[0].Minute / 60.0;
            if (timeF < 8.5 || timeF >= 15.0)
                return;

            // ── 10. Check for signal from state machine ──
            if (barSignalDir == 0)
                return;

            // ── 11. Grid filter ──
            if (gridFilterEnabled)
            {
                double atrRoll50Val = ComputeAtrRoll50();
                string cell = ClassifyGridCell(barSignalDir, timeF, atrVal, atrRoll50Val);
                if (cell == null || !activeCells.Contains(cell))
                    return;
            }

            // ── 12. Signal bar quality filter ──
            if (UseSignalBarFilter)
            {
                if (!CheckSignalBar(barSignalDir, atrVal))
                {
                    signalBarFailed++;
                    return;
                }
                signalBarPassed++;
            }

            // ── 13. Cancel existing pending order ──
            if (entryOrder != null
                && (entryOrder.OrderState == OrderState.Working
                    || entryOrder.OrderState == OrderState.Accepted))
            {
                CancelOrder(entryOrder);
                entryOrder = null;
            }

            // ── 14. Place limit order at swing price ──
            pendingStopPrice = barSignalStop;

            if (barSignalDir == 1)
            {
                SetStopLoss("LongEntry", CalculationMode.Price, barSignalStop, false);
                entryOrder = EnterLongLimit(1, barSignalLimitPrice, "LongEntry");
                pendingOrderBar = CurrentBar;
            }
            else
            {
                SetStopLoss("ShortEntry", CalculationMode.Price, barSignalStop, false);
                entryOrder = EnterShortLimit(1, barSignalLimitPrice, "ShortEntry");
                pendingOrderBar = CurrentBar;
            }
        }

        #endregion

        #region ATR Calculation

        /// <summary>
        /// SMA-based ATR matching Python's compute_atr (simple rolling mean of TR).
        /// NinjaTrader's built-in ATR uses Wilder's smoothing which differs.
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

        /// <summary>
        /// 50-bar rolling mean of ATR for volatility regime classification.
        /// Uses smaAtr[1..50] (excludes current bar, matching Python's atr[i-50:i]).
        /// </summary>
        private double ComputeAtrRoll50()
        {
            if (CurrentBar < AtrPeriod - 1 + 50)
                return double.NaN;

            double sum = 0;
            int count = 0;
            for (int k = 1; k <= 50; k++)
            {
                if (!double.IsNaN(smaAtr[k]))
                {
                    sum += smaAtr[k];
                    count++;
                }
            }
            return count > 0 ? sum / count : double.NaN;
        }

        #endregion

        #region Swing Detection

        /// <summary>
        /// Detect if bar[SwingStrength] is a swing high/low, confirmed at current bar.
        /// Matches Python's detect_swings with confirmation delay.
        /// </summary>
        private void DetectSwing()
        {
            barIsSwingHigh = false;
            barIsSwingLow = false;
            barSwingHighPrice = double.NaN;
            barSwingLowPrice = double.NaN;

            int s = SwingStrength;
            if (CurrentBar < 2 * s)
                return;

            // Swing HIGH: High[s] > all neighbors within s bars
            bool isSH = true;
            for (int k = 1; k <= s; k++)
            {
                if (High[s] <= High[s - k] || High[s] <= High[s + k])
                {
                    isSH = false;
                    break;
                }
            }

            // Swing LOW: Low[s] < all neighbors within s bars
            bool isSL = true;
            for (int k = 1; k <= s; k++)
            {
                if (Low[s] >= Low[s - k] || Low[s] >= Low[s + k])
                {
                    isSL = false;
                    break;
                }
            }

            if (isSH)
            {
                barIsSwingHigh = true;
                barSwingHighPrice = High[s];
            }
            if (isSL)
            {
                barIsSwingLow = true;
                barSwingLowPrice = Low[s];
            }
        }

        #endregion

        #region Trend State Machine

        /// <summary>
        /// Update trend classification and pullback counters. Generate entry signals.
        /// Matches Python's detect_trend_and_entries state machine.
        ///
        /// Trend: HH+HL=UP, LH+LL=DOWN, else=RANGE
        /// Long signals: in uptrend, count swing lows after a new HH
        /// Short signals: in downtrend, count swing highs after a new LL
        /// </summary>
        private void UpdateTrendAndSignals(double atrVal)
        {
            barSignalDir = 0;
            barSignalStop = 0;
            barSignalLimitPrice = 0;

            // ── Update swing history ──
            if (barIsSwingHigh)
            {
                swingHigh2 = swingHigh1;
                swingHigh1 = barSwingHighPrice;
            }
            if (barIsSwingLow)
            {
                swingLow2 = swingLow1;
                swingLow1 = barSwingLowPrice;
            }

            // ── Classify trend (need 2 of each swing type) ──
            if (double.IsNaN(swingHigh2) || double.IsNaN(swingLow2))
            {
                trendState = 0; // UNKNOWN
            }
            else
            {
                bool hh = swingHigh1 > swingHigh2;
                bool hl = swingLow1 > swingLow2;
                bool lh = swingHigh1 < swingHigh2;
                bool ll = swingLow1 < swingLow2;

                if (hh && hl)
                    trendState = 1;  // UP
                else if (lh && ll)
                    trendState = -1; // DOWN
                else
                    trendState = 2;  // RANGE
            }

            // ── LONG side: in uptrend, count pullbacks (swing lows) after HH ──
            if (trendState == 1)
            {
                if (barIsSwingHigh && !double.IsNaN(swingHigh2) && swingHigh1 > swingHigh2)
                    longPullbackCount = 0;

                if (barIsSwingLow && longPullbackCount >= 0)
                {
                    longPullbackCount++;

                    if (longPullbackCount == 1 || longPullbackCount == 2)
                    {
                        double stopLevel = barSwingLowPrice - StopBufferAtr * atrVal;
                        if (barSwingLowPrice - stopLevel > MaxStopAtr * atrVal)
                            stopLevel = barSwingLowPrice - MaxStopAtr * atrVal;

                        barSignalDir = 1;
                        barSignalStop = stopLevel;
                        barSignalLimitPrice = barSwingLowPrice;

                        if (longPullbackCount == 2)
                            longPullbackCount = -1; // consumed
                    }
                }
            }
            else
            {
                longPullbackCount = 0;
            }

            // ── SHORT side: in downtrend, count pullbacks (swing highs) after LL ──
            if (trendState == -1)
            {
                if (barIsSwingLow && !double.IsNaN(swingLow2) && swingLow1 < swingLow2)
                    shortPullbackCount = 0;

                if (barIsSwingHigh && shortPullbackCount >= 0)
                {
                    shortPullbackCount++;

                    if (shortPullbackCount == 1 || shortPullbackCount == 2)
                    {
                        double stopLevel = barSwingHighPrice + StopBufferAtr * atrVal;
                        if (stopLevel - barSwingHighPrice > MaxStopAtr * atrVal)
                            stopLevel = barSwingHighPrice + MaxStopAtr * atrVal;

                        barSignalDir = -1;
                        barSignalStop = stopLevel;
                        barSignalLimitPrice = barSwingHighPrice;

                        if (shortPullbackCount == 2)
                            shortPullbackCount = -1; // consumed
                    }
                }
            }
            else
            {
                shortPullbackCount = 0;
            }
        }

        #endregion

        #region Grid Classification

        /// <summary>
        /// Initialize grid cell sets based on GridFilterMode parameter.
        /// Mode 0: No filter (all signals pass)
        /// Mode 1: Fine — 6 stable cells (3-axis: EMA|TOD|direction)
        /// Mode 2: Fine — 10 profitable cells (3-axis, not split-validated)
        /// Mode 3: Ultra — 8 stable cells (4-axis: EMA|TOD|direction|vol)
        /// </summary>
        private void InitializeGridFilter()
        {
            activeCells = new HashSet<string>();

            switch (GridFilterMode)
            {
                case 0: // No grid filter
                    gridFilterEnabled = false;
                    useUltraMode = false;
                    break;

                case 1: // Fine — 6 stable cells (split-half validated)
                    gridFilterEnabled = true;
                    useUltraMode = false;
                    activeCells = new HashSet<string>
                    {
                        "ema<-2|open|SHORT",
                        "ema<-2|afternoon|SHORT",
                        "ema<-2|morning|SHORT",
                        "ema-2..-1|afternoon|SHORT",
                        "ema>2|open|LONG",
                        "ema>2|morning|LONG",
                    };
                    break;

                case 2: // Fine — 10 profitable cells (full-sample, use with caution)
                    gridFilterEnabled = true;
                    useUltraMode = false;
                    activeCells = new HashSet<string>
                    {
                        "ema<-2|open|SHORT",
                        "ema<-2|afternoon|SHORT",
                        "ema<-2|morning|SHORT",
                        "ema-2..-1|afternoon|SHORT",
                        "ema-2..-1|morning|SHORT",
                        "ema0..1|morning|SHORT",
                        "ema1..2|afternoon|LONG",
                        "ema>2|open|LONG",
                        "ema>2|afternoon|LONG",
                        "ema>2|morning|LONG",
                    };
                    break;

                case 3: // Ultra — 8 stable cells (split-half validated)
                    gridFilterEnabled = true;
                    useUltraMode = true;
                    activeCells = new HashSet<string>
                    {
                        "ema<-2|open|SHORT|high_vol",
                        "ema<-2|morning|SHORT|high_vol",
                        "ema-2..-1|afternoon|SHORT|norm_vol",
                        "ema-1..0|morning|SHORT|norm_vol",
                        "ema0..1|morning|LONG|norm_vol",
                        "ema0..1|afternoon|LONG|norm_vol",
                        "ema>2|open|LONG|high_vol",
                        "ema>2|afternoon|LONG|low_vol",
                    };
                    break;

                default: // Invalid → treat as no filter
                    gridFilterEnabled = false;
                    useUltraMode = false;
                    break;
            }
        }

        /// <summary>
        /// Classify current conditions into a grid cell key.
        /// Fine mode: EMA bucket | time-of-day | direction (3-axis)
        /// Ultra mode: EMA bucket | time-of-day | direction | volatility regime (4-axis)
        /// Returns null if any dimension is unclassifiable.
        /// </summary>
        private string ClassifyGridCell(int direction, double timeF,
                                         double atrVal, double atrRoll50Val)
        {
            // EMA distance in ATR units
            double emaVal = emaIndicator[0];
            if (double.IsNaN(emaVal) || atrVal <= 0)
                return null;

            double emaDist = (Close[0] - emaVal) / atrVal;

            string emaBucket;
            if      (emaDist < -2) emaBucket = "ema<-2";
            else if (emaDist < -1) emaBucket = "ema-2..-1";
            else if (emaDist <  0) emaBucket = "ema-1..0";
            else if (emaDist <  1) emaBucket = "ema0..1";
            else if (emaDist <  2) emaBucket = "ema1..2";
            else                   emaBucket = "ema>2";

            // Time of day
            string tod;
            if      (timeF >= 8.5  && timeF < 9.5)  tod = "open";
            else if (timeF >= 9.5  && timeF < 12.0) tod = "morning";
            else if (timeF >= 12.0 && timeF < 15.0) tod = "afternoon";
            else return null;

            // Direction
            string dir = direction == 1 ? "LONG" : "SHORT";

            if (!useUltraMode)
                return emaBucket + "|" + tod + "|" + dir;

            // Ultra: add volatility regime
            if (double.IsNaN(atrRoll50Val) || atrRoll50Val <= 0)
                return null;
            double volRatio = atrVal / atrRoll50Val;

            string vol;
            if      (volRatio < 0.9) vol = "low_vol";
            else if (volRatio < 1.2) vol = "norm_vol";
            else                     vol = "high_vol";

            return emaBucket + "|" + tod + "|" + dir + "|" + vol;
        }

        #endregion

        #region Signal Bar Filter

        /// <summary>
        /// Check if the current bar qualifies as a good signal bar.
        /// Matches Python's check_signal_bar from mitch_v2_strategy.py.
        ///
        /// For long signals: bar must be bullish (close > open), close in upper
        /// portion of bar range, body must be meaningful portion of range.
        /// For short signals: mirror logic (bearish bar, close in lower portion).
        ///
        /// Also rejects dojis (tiny body) and extreme bars (range > 3x ATR).
        /// </summary>
        private bool CheckSignalBar(int direction, double atrVal)
        {
            double barRange = High[0] - Low[0];
            if (barRange <= 0)
                return false;

            // Range must be meaningful but not extreme
            if (double.IsNaN(atrVal) || atrVal <= 0)
                return false;
            if (barRange < 0.15 * atrVal)  // not a doji
                return false;
            if (barRange > 3.0 * atrVal)   // not an outlier
                return false;

            // Body size check
            double body = Math.Abs(Close[0] - Open[0]);
            if (body / barRange < SignalBarBodyPct)
                return false;

            // Close position + direction check
            if (direction == 1) // Long: bullish bar, close in upper portion
            {
                if (Close[0] <= Open[0])
                    return false;
                if ((Close[0] - Low[0]) / barRange < (1.0 - SignalBarClosePct))
                    return false;
            }
            else // Short: bearish bar, close in lower portion
            {
                if (Close[0] >= Open[0])
                    return false;
                if ((High[0] - Close[0]) / barRange < (1.0 - SignalBarClosePct))
                    return false;
            }

            return true;
        }

        #endregion

        #region Trailing Stop

        /// <summary>
        /// Update trailing stop behind favorable swing points.
        /// - Breakeven: move stop to entry price on first favorable swing
        /// - Trail: ratchet stop to swing - buffer (only moves in favorable direction)
        /// Updates NinjaTrader's stop order via SetStopLoss.
        /// </summary>
        private void UpdateTrailingStop(double atrVal)
        {
            if (double.IsNaN(atrVal) || atrVal <= 0)
                return;

            double buf = TrailBufferAtr * atrVal;

            if (Position.MarketPosition == MarketPosition.Long)
            {
                if (!barIsSwingLow || double.IsNaN(barSwingLowPrice))
                    return;

                bool updated = false;

                // Breakeven: first swing low above entry → stop to entry
                if (UseBreakeven && !breakevenMoved && barSwingLowPrice > myEntryPrice)
                {
                    if (myEntryPrice > currentStopPrice)
                    {
                        currentStopPrice = myEntryPrice;
                        trailCount++;
                        updated = true;
                    }
                    breakevenMoved = true;
                }

                // Trail tighter: swing low - buffer
                double newStop = barSwingLowPrice - buf;
                if (newStop > currentStopPrice)
                {
                    currentStopPrice = newStop;
                    trailCount++;
                    updated = true;
                }

                if (updated)
                    SetStopLoss("LongEntry", CalculationMode.Price, currentStopPrice, false);
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                if (!barIsSwingHigh || double.IsNaN(barSwingHighPrice))
                    return;

                bool updated = false;

                // Breakeven: first swing high below entry → stop to entry
                if (UseBreakeven && !breakevenMoved && barSwingHighPrice < myEntryPrice)
                {
                    if (myEntryPrice < currentStopPrice)
                    {
                        currentStopPrice = myEntryPrice;
                        trailCount++;
                        updated = true;
                    }
                    breakevenMoved = true;
                }

                // Trail tighter: swing high + buffer
                double newStop = barSwingHighPrice + buf;
                if (newStop < currentStopPrice)
                {
                    currentStopPrice = newStop;
                    trailCount++;
                    updated = true;
                }

                if (updated)
                    SetStopLoss("ShortEntry", CalculationMode.Price, currentStopPrice, false);
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
                currentStopPrice = pendingStopPrice;
                breakevenMoved = false;
                trailCount = 0;
                entryOrder = null;
            }

            // ── Track position close → update circuit breakers ──
            if (Position.MarketPosition == MarketPosition.Flat
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

        #region Properties

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Swing Strength", Description = "Fractal lookback bars on each side",
            Order = 1, GroupName = "1. Entry")]
        public int SwingStrength { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "EMA Period", Description = "EMA period for grid classification",
            Order = 2, GroupName = "1. Entry")]
        public int EmaPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Limit Order Timeout", Description = "Bars before limit order expires",
            Order = 3, GroupName = "1. Entry")]
        public int LimitOrderTimeout { get; set; }

        [NinjaScriptProperty]
        [Range(0, 3)]
        [Display(Name = "Grid Filter Mode",
            Description = "0=None (all signals), 1=Fine 6 cells, 2=Fine 10 cells, 3=Ultra 8 cells",
            Order = 4, GroupName = "1. Entry")]
        public int GridFilterMode { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "ATR Period", Description = "ATR period (SMA-based, not Wilder)",
            Order = 1, GroupName = "2. Stop")]
        public int AtrPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, double.MaxValue)]
        [Display(Name = "Stop Buffer ATR", Description = "Initial stop buffer from swing (ATR mult)",
            Order = 2, GroupName = "2. Stop")]
        public double StopBufferAtr { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, double.MaxValue)]
        [Display(Name = "Max Stop ATR", Description = "Maximum stop distance (ATR mult)",
            Order = 3, GroupName = "2. Stop")]
        public double MaxStopAtr { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, double.MaxValue)]
        [Display(Name = "Trail Buffer ATR", Description = "Trailing stop buffer from swing (ATR mult)",
            Order = 4, GroupName = "2. Stop")]
        public double TrailBufferAtr { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Breakeven", Description = "Move stop to breakeven on first favorable swing",
            Order = 5, GroupName = "2. Stop")]
        public bool UseBreakeven { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Max Hold Bars", Description = "Time exit after N bars",
            Order = 6, GroupName = "2. Stop")]
        public int MaxHoldBars { get; set; }

        [NinjaScriptProperty]
        [Range(-100000, 0)]
        [Display(Name = "Daily Loss Limit", Description = "Circuit breaker: max daily loss ($)",
            Order = 1, GroupName = "3. Risk")]
        public double DailyLossLimit { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Max Consec Losses", Description = "Circuit breaker: pause after N consecutive losses",
            Order = 2, GroupName = "3. Risk")]
        public int MaxConsecLosses { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Signal Bar Filter",
            Description = "Require signal bar to show directional conviction (bullish for longs, bearish for shorts)",
            Order = 1, GroupName = "4. Signal Bar")]
        public bool UseSignalBarFilter { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 0.50)]
        [Display(Name = "Signal Bar Close %",
            Description = "Close must be in this % of bar from favorable end (0.40=top 60% for longs). Lower = stricter.",
            Order = 2, GroupName = "4. Signal Bar")]
        public double SignalBarClosePct { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 0.50)]
        [Display(Name = "Signal Bar Body %",
            Description = "Body must be at least this % of bar range (0.15=15% min body). Higher = stricter.",
            Order = 3, GroupName = "4. Signal Bar")]
        public double SignalBarBodyPct { get; set; }

        #endregion
    }
}
