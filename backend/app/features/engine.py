import numpy as np
import pandas as pd
from app.indicators.engine import calculate as indicators
from app.ict_smc.engine import calculate as ict

FEATURE_VERSION = "causal-v3"
TARGET_VERSION = "triple-barrier-v1"

FEATURES = [
    # Price / momentum
    "return",
    "ret3",
    "ret5",
    "ret10",
    "ret20",
    "momentum_accel",
    "atr_normalized_return",
    "trend_momentum_alignment",

    # Candle structure
    "body",
    "upper_wick",
    "lower_wick",
    "body_to_range",
    "candle_direction",

    # Trend
    "ema_gap",
    "ema9_gap",
    "ema200_gap",
    "trend_strength",
    "trend_slope",
    "ema_rsi_alignment",

    # Momentum indicators
    "rsi_scaled",
    "rsi_change",
    "macd_scaled",
    "macd_hist_scaled",
    "stoch_scaled",
    "cci_scaled",
    "roc_scaled",

    # Volatility
    "atr_ratio",
    "volatility",
    "volatility_ratio",
    "bb_position",
    "bb_width",

    # Volume
    "volume_ratio",
    "mfi_scaled",
    "obv_change",

    # VWAP
    "vwap_distance",

    # Supertrend
    "supertrend_distance",
    "supertrend_direction",

    # Market structure / ICT-SMC
    "bos",
    "choch",
    "sweep",
    "fvg",
    "displacement",
    "premium_discount",

    # Regime / expansion
    "regime_trend",
    "expansion",

    # Time
    "hour_sin",
    "hour_cos",
    "weekday",

    # Higher timeframe
    "htf_return",

    # Session context
    "session_range_ratio",
    "session_position",

    # Previous completed levels
    "prev_day_high_distance",
    "prev_day_low_distance",
    "prev_week_high_distance",
    "prev_week_low_distance",

    # Fibonacci context
    "fib_382_distance",
    "fib_50_distance",
    "fib_618_distance",

    # Additional causal level/flow context
    "swing_high_distance",
    "swing_low_distance",
    "range_position_20",
    "volume_price_impulse",
]


def build(df):
    d, events, zones = ict(indicators(df))
    c = d.close

    # -------------------------
    # Price / momentum
    # -------------------------
    d["return"] = c.pct_change()
    d["ret3"] = c.pct_change(3)
    d["ret5"] = c.pct_change(5)
    d["ret10"] = c.pct_change(10)
    d["ret20"] = c.pct_change(20)
    d["momentum_accel"] = d["ret5"] - d["ret20"] / 4
    d["atr_normalized_return"] = d["return"] / (d["atr"] / c).replace(0, np.nan)
    d["trend_momentum_alignment"] = np.sign((d.ema20 - d.ema50) / c) * np.sign(d["ret5"])

    # -------------------------
    # Candle structure
    # -------------------------
    candle_range = (d.high - d.low).replace(0, np.nan)
    d["body"] = (c - d.open) / c
    d["upper_wick"] = (
        d.high - d[["open", "close"]].max(axis=1)
    ) / c
    d["lower_wick"] = (
        d[["open", "close"]].min(axis=1) - d.low
    ) / c
    d["body_to_range"] = (c - d.open).abs() / candle_range
    d["candle_direction"] = np.sign(c - d.open)

    # -------------------------
    # Trend
    # -------------------------
    d["ema_gap"] = (d.ema20 - d.ema50) / c
    d["ema9_gap"] = (d.ema9 - d.ema20) / c
    d["ema200_gap"] = (c - d.ema200) / c
    d["trend_strength"] = (
        (d.ema20 - d.ema50).abs()
        / d.atr.replace(0, np.nan)
    )
    d["trend_slope"] = (
        d.ema20 - d.ema20.shift(5)
    ) / c
    d["ema_rsi_alignment"] = np.sign(d.ema20 - d.ema50) * ((d.rsi - 50) / 50)

    # -------------------------
    # Momentum
    # -------------------------
    d["rsi_scaled"] = d.rsi / 100
    d["rsi_change"] = d.rsi.diff(3) / 100
    d["macd_scaled"] = d.macd / c
    d["macd_hist_scaled"] = d.macd_hist / c
    d["stoch_scaled"] = d.stochastic / 100
    d["cci_scaled"] = d.cci / 200
    d["roc_scaled"] = d.roc / 100

    # -------------------------
    # Volatility
    # -------------------------
    d["atr_ratio"] = d.atr / c
    d["volatility"] = d["return"].rolling(20).std()
    d["volatility_ratio"] = (
        d.volatility
        / d.volatility.rolling(100, min_periods=30).median()
    )

    d["bb_position"] = (
        (c - d.bb_lower)
        / (d.bb_upper - d.bb_lower).replace(0, np.nan)
    )
    d["bb_width"] = (
        (d.bb_upper - d.bb_lower) / c
    )

    # -------------------------
    # Volume
    # -------------------------
    d["volume_ratio"] = (
        d.volume
        / d.volume_ma.replace(0, np.nan)
    )
    d["mfi_scaled"] = d.mfi / 100
    d["obv_change"] = (
        d.obv.diff(5)
        / d.volume_ma.replace(0, np.nan)
    )

    # -------------------------
    # VWAP
    # -------------------------
    d["vwap_distance"] = (
        c - d.vwap
    ) / c

    # -------------------------
    # Supertrend
    # -------------------------
    d["supertrend_distance"] = (
        c - d.supertrend
    ) / c
    d["supertrend_direction"] = d.supertrend_direction

    # -------------------------
    # ICT / SMC
    # -------------------------
    # These are produced by the existing causal ICT/SMC engine.
    # Do not alter their definitions here.
    d["bos"] = d["bos"]
    d["choch"] = d["choch"]
    d["sweep"] = d["sweep"]
    d["fvg"] = d["fvg"]
    d["displacement"] = d["displacement"]
    d["premium_discount"] = d["premium_discount"]

    # -------------------------
    # Regime / expansion
    # -------------------------
    regime_map = {
        "HIGH VOLATILITY": 2.0,
        "LOW VOLATILITY": -2.0,
        "TRENDING BULLISH": 1.0,
        "TRENDING BEARISH": -1.0,
        "TRANSITION": 0.0,
        "RANGING": 0.0,
    }
    d["regime_trend"] = d.regime.map(regime_map).fillna(0.0)
    d["expansion"] = d.expansion.astype(float)

    # -------------------------
    # Time
    # -------------------------
    t = pd.to_datetime(d.time, unit="s", utc=True)
    d["hour_sin"] = np.sin(
        t.dt.hour * 2 * np.pi / 24
    )
    d["hour_cos"] = np.cos(
        t.dt.hour * 2 * np.pi / 24
    )
    d["weekday"] = t.dt.dayofweek / 6

    # -------------------------
    # 4H higher-timeframe return
    # -------------------------
    indexed = d.set_index(t)

    htf = (
        indexed.close
        .resample("4h", label="right", closed="left")
        .last()
        .pct_change()
        .rename("htf_return")
    )

    available = pd.to_datetime(
        d.end_time,
        unit="s",
        utc=True,
    )

    merged = pd.merge_asof(
        pd.DataFrame({"at": available}),
        htf.reset_index().rename(
            columns={"time": "at"}
        ),
        on="at",
        direction="backward",
    )

    d["htf_return"] = merged.htf_return.to_numpy()

    # -------------------------
    # Session context
    # -------------------------
    block = d.time // 28800

    hi = d.high.groupby(block).cummax()
    lo = d.low.groupby(block).cummin()

    d["session_range_ratio"] = (
        (hi - lo) / c
    )

    d["session_position"] = (
        (c - lo)
        / (hi - lo).replace(0, np.nan)
    )

    # -------------------------
    # Previous completed levels
    # -------------------------
    d["prev_day_high_distance"] = (
        c - d.previous_day_high
    ) / c

    d["prev_day_low_distance"] = (
        c - d.previous_day_low
    ) / c

    d["prev_week_high_distance"] = (
        c - d.previous_week_high
    ) / c

    d["prev_week_low_distance"] = (
        c - d.previous_week_low
    ) / c

    # -------------------------
    # Fibonacci context
    # -------------------------
    d["fib_382_distance"] = (
        c - d["fib_0.382"]
    ) / c

    d["fib_50_distance"] = (
        c - d["fib_0.5"]
    ) / c

    d["fib_618_distance"] = (
        c - d["fib_0.618"]
    ) / c

    # -------------------------
    # Additional causal level/flow context
    # -------------------------
    d["swing_high_distance"] = (d.swing_high - c) / c
    d["swing_low_distance"] = (c - d.swing_low) / c
    rolling_hi = d.high.rolling(20, min_periods=5).max()
    rolling_lo = d.low.rolling(20, min_periods=5).min()
    d["range_position_20"] = (
        (c - rolling_lo) / (rolling_hi - rolling_lo).replace(0, np.nan)
    )
    d["volume_price_impulse"] = d["return"] * d["volume_ratio"]

    return (
        d.replace([np.inf, -np.inf], np.nan),
        events,
        zones,
    )


def targets(d, horizon):
    """Triple-barrier labels using only candles after the prediction candle."""
    y = pd.DataFrame(index=d.index)
    h = int(horizon)
    close = d.close.to_numpy(dtype=float)
    high = d.high.to_numpy(dtype=float)
    low = d.low.to_numpy(dtype=float)
    atr = d.atr.to_numpy(dtype=float)
    classes = np.full(len(d), np.nan)
    returns = np.full(len(d), np.nan)
    highs = np.full(len(d), np.nan)
    lows = np.full(len(d), np.nan)
    vols = np.full(len(d), np.nan)
    barrier_atr = 0.60
    for i in range(max(0, len(d) - h)):
        if not np.isfinite(close[i]) or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        up = close[i] + barrier_atr * atr[i]
        down = close[i] - barrier_atr * atr[i]
        end = min(len(d), i + h + 1)
        label = 1
        for j in range(i + 1, end):
            up_hit = high[j] >= up
            down_hit = low[j] <= down
            if up_hit and down_hit:
                label = 1
                break
            if up_hit:
                label = 2
                break
            if down_hit:
                label = 0
                break
        classes[i] = label
        last = end - 1
        returns[i] = close[last] / close[i] - 1
        highs[i] = np.max(high[i + 1:end]) / close[i] - 1
        lows[i] = np.min(low[i + 1:end]) / close[i] - 1
        r = d["return"].iloc[i + 1:end].to_numpy(dtype=float)
        if len(r):
            vols[i] = float(np.std(r))
    y["class"] = classes
    y["return"] = returns
    y["high"] = highs
    y["low"] = lows
    y["volatility"] = vols
    time_diffs = d.time.diff().dropna()
    interval = int(time_diffs.median()) if len(time_diffs) else 0
    if interval > 0:
        contiguous = d.time.shift(-h) - d.time == interval * h
        y.loc[~contiguous, :] = np.nan
    return y

