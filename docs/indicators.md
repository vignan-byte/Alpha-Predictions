# Indicator definitions

All calculations use trailing observations only. Indicators for analysis and ML use closed candles; the price chart separately shows the developing candle.

- SMA: arithmetic rolling means for 9/20/50/200 closes.
- EMA: pandas exponentially weighted mean, `adjust=False`, span 9/20/50/200, initial warmup equal to span.
- WMA20: weights 1 through 20, newest largest.
- RSI14: Wilder-style exponential smoothing (`alpha=1/14`, first-observation seed, minimum 14 differences) of positive and negative close differences. All-up = 100, flat = 50. This seed may differ from TradingView's initial SMA seed.
- MACD: EMA12 minus EMA26; signal EMA9; histogram difference.
- Stochastic14: `(close - lowest low)/(highest high - lowest low)*100`; D is three-bar SMA.
- Williams %R14: negative distance from the highest high divided by the same range.
- CCI20: typical-price deviation divided by 0.015 times mean absolute deviation.
- ROC12: percentage close change over 12 bars.
- ATR14: maximum of high-low, absolute high-previous close and absolute low-previous close, smoothed with `alpha=1/14`.
- Bollinger: SMA20 ± two population standard deviations (`ddof=0`).
- VWAP: cumulative typical-price × volume / cumulative volume within UTC calendar day; unavailable if volume is absent.
- OBV: cumulative signed close difference × volume.
- MFI14: positive/negative typical-price money-flow sums; no price-volume value is invented when volume is absent.
- Supertrend: midpoint ± 3 ATR; bands retain trailing prior values until breached; direction switches on closing break. First valid direction is up.
- Ichimoku: Tenkan9, Kijun26, Senkou A and B shifted forward 26 bars in the display-time series. Chikou backward displacement is excluded from predictive features.
- Fibonacci: trailing 50-bar low + ratio × range; ratios .236/.382/.5/.618/.786/1.272/1.618. These are rolling-range levels, not discretionary swing anchoring.
- Previous day/week/month: final high and low of the preceding UTC period. Weekly boundaries use ISO weeks. The current incomplete period never substitutes for a previous period.
- Pivot: prior-day (H+L+C)/3; R1 = 2P−L; S1 = 2P−H.

Regime: high volatility above 1.5× trailing volatility median; low below .65×; otherwise trending bullish/bearish by EMA order when |EMA20−EMA50|/ATR > 1; a just-crossed EMA order is TRANSITION, ranging otherwise. Expansion compares ATR with five bars ago; bull-regime flag tests close > EMA200. These are deterministic labels, not validated predictive advantages.

No claim of exact Pine Script parity is made. Unit tests check known EMA, RSI, ATR and MACD values and prefix invariance. For exact external-library parity, align seeds, warmup, session conventions and standard-deviation conventions first.
