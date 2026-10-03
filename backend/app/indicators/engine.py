import numpy as np
import pandas as pd


def rma(s, n):
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def calculate(df):
    d = df.copy()
    c = d.close
    h = d.high
    l = d.low
    v = d.volume
    prev = c.shift()
    for n in (9, 20, 50, 200):
        d[f"ema{n}"] = c.ewm(span=n, adjust=False, min_periods=n).mean()
        d[f"sma{n}"] = c.rolling(n).mean()
    d["wma20"] = c.rolling(20).apply(
        lambda a: np.dot(a, np.arange(1, 21)) / 210, raw=True
    )
    delta = c.diff()
    up = rma(delta.clip(lower=0), 14)
    down = rma(-delta.clip(upper=0), 14)
    d["rsi"] = 100 - 100 / (1 + up / down.replace(0, np.nan))
    d.loc[(down == 0) & (up > 0), "rsi"] = 100
    d.loc[(down == 0) & (up == 0), "rsi"] = 50
    tr = pd.concat([h - l, (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    d["atr"] = rma(tr, 14)
    d["std20"] = c.rolling(20).std(ddof=0)
    d["bb_mid"] = c.rolling(20).mean()
    d["bb_upper"] = d.bb_mid + 2 * d.std20
    d["bb_lower"] = d.bb_mid - 2 * d.std20
    d["macd"] = (
        c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    )
    d["macd_signal"] = d.macd.ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d.macd - d.macd_signal
    lo = l.rolling(14).min()
    hi = h.rolling(14).max()
    width = (hi - lo).replace(0, np.nan)
    d["stochastic"] = 100 * (c - lo) / width
    d["stochastic_d"] = d.stochastic.rolling(3).mean()
    d["williams_r"] = -100 * (hi - c) / width
    tp = (h + l + c) / 3
    mad = tp.rolling(20).apply(lambda a: np.mean(np.abs(a - a.mean())), raw=True)
    d["cci"] = (tp - tp.rolling(20).mean()) / (0.015 * mad.replace(0, np.nan))
    d["roc"] = c.pct_change(12) * 100
    d["obv"] = (np.sign(delta).fillna(0) * v).cumsum()
    money = tp * v
    positive = money.where(tp.diff() > 0, 0).rolling(14).sum()
    negative = money.where(tp.diff() < 0, 0).rolling(14).sum()
    d["mfi"] = 100 - 100 / (1 + positive / negative.replace(0, np.nan))
    d.loc[(negative == 0) & (positive > 0), "mfi"] = 100
    d.loc[v.isna(), "mfi"] = np.nan
    d["volume_ma"] = v.rolling(20).mean()
    day = pd.to_datetime(d.time, unit="s", utc=True).dt.date
    d["vwap"] = (tp * v).groupby(day).cumsum() / v.groupby(day).cumsum().replace(
        0, np.nan
    )
    d["tenkan"] = (h.rolling(9).max() + l.rolling(9).min()) / 2
    d["kijun"] = (h.rolling(26).max() + l.rolling(26).min()) / 2
    d["senkou_a"] = ((d.tenkan + d.kijun) / 2).shift(26)
    d["senkou_b"] = ((h.rolling(52).max() + l.rolling(52).min()) / 2).shift(26)
    # Chikou is deliberately not shifted backward into historical features.
    mid = (h + l) / 2
    upper = (mid + 3 * d.atr).to_numpy()
    lower = (mid - 3 * d.atr).to_numpy()
    close = c.to_numpy()
    st = np.full(len(d), np.nan)
    direction = np.ones(len(d))
    for i in range(14, len(d)):
        if np.isfinite(upper[i - 1]):
            if close[i - 1] <= upper[i - 1]:
                upper[i] = min(upper[i], upper[i - 1])
            if close[i - 1] >= lower[i - 1]:
                lower[i] = max(lower[i], lower[i - 1])
            direction[i] = (
                1
                if close[i] > upper[i - 1]
                else (-1 if close[i] < lower[i - 1] else direction[i - 1])
            )
        st[i] = lower[i] if direction[i] > 0 else upper[i]
    d["supertrend"] = st
    d["supertrend_direction"] = direction
    d["return"] = c.pct_change()
    d["volatility"] = d["return"].rolling(20).std()
    d["atr_ratio"] = d.atr / c
    avgvol = d.volatility.rolling(100, min_periods=30).median()
    trend = (d.ema20 - d.ema50).abs() / d.atr.replace(0, np.nan)
    d["regime"] = np.select(
        [
            d.volatility > avgvol * 1.5,
            d.volatility < avgvol * 0.65,
            (trend > 1) & (d.ema20 > d.ema50),
            (trend > 1) & (d.ema20 < d.ema50),
            ((d.ema20 - d.ema50) * (d.ema20.shift(1) - d.ema50.shift(1)) < 0),
        ],
        [
            "HIGH VOLATILITY",
            "LOW VOLATILITY",
            "TRENDING BULLISH",
            "TRENDING BEARISH",
            "TRANSITION",
        ],
        default="RANGING",
    )
    d["expansion"] = d.atr > d.atr.shift(5)
    d["bull_regime"] = c > d.ema200
    # Completed calendar periods only, using UTC boundaries.
    times = pd.to_datetime(d.time, unit="s", utc=True)
    for name, key in [
        ("day", times.dt.strftime("%Y-%m-%d")),
        ("week", times.dt.strftime("%G-%V")),
        ("month", times.dt.strftime("%Y-%m")),
    ]:
        agg = (
            d.groupby(key, sort=False)
            .agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
            .shift()
        )
        d[f"previous_{name}_high"] = key.map(agg.high)
        d[f"previous_{name}_low"] = key.map(agg.low)
        if name == "day":
            d["pivot"] = (key.map(agg.high) + key.map(agg.low) + key.map(agg.close)) / 3
            d["pivot_r1"] = 2 * d["pivot"] - key.map(agg.low)
            d["pivot_s1"] = 2 * d["pivot"] - key.map(agg.high)
    for ratio in (0.236, 0.382, 0.5, 0.618, 0.786, 1.272, 1.618):
        d[f"fib_{ratio}"] = (
            l.rolling(50).min() + (h.rolling(50).max() - l.rolling(50).min()) * ratio
        )
    return d.replace([np.inf, -np.inf], np.nan)
