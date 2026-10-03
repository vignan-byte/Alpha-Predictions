import time
import numpy as np
from app.models.pipeline import infer
from app.features.engine import build
from app.database import store
from app.data.providers import SECONDS
from app.core.config import settings
from app.predictions.signal import SignalPolicy, build_signal

HORIZONS = {
    "session": ("1h", "session"),
    "5m": ("5m", 1),
    "15m": ("5m", 3),
    "30m": ("5m", 6),
    "1h": ("5m", 12),
    "day": ("1d", 1),
    "week": ("1d", 7),
    "month": ("1d", 30),
    "year": ("1d", 365),
}


def make(df, symbol, tf, horizon_bars, source, horizon):
    d, events, zones = build(df)
    last = d.iloc[-1]
    p = infer(df, symbol, tf, horizon_bars, source)
    window = None
    if horizon_bars == "session":
        from app.features.session_targets import next_window

        window = next_window(last.end_time)
        horizon_bars = (window["end"] - window["start"]) // SECONDS[tf]
    support = (
        float(last.swing_low)
        if np.isfinite(last.swing_low)
        else float(d.low.tail(20).min())
    )
    resistance = (
        float(last.swing_high)
        if np.isfinite(last.swing_high)
        else float(d.high.tail(20).max())
    )
    factors = []
    if np.isfinite(last.ema50):
        factors.append(
            "EMA20 above EMA50" if last.ema20 > last.ema50 else "EMA20 below EMA50"
        )
    if np.isfinite(last.rsi):
        factors.append(f"RSI14 = {last.rsi:.1f}")
    factors.extend(
        e["kind"] for e in events if e["time"] >= int(d.time.iloc[max(0, len(d) - 5)])
    )
    result = dict(
        symbol=symbol,
        source=source,
        horizon=horizon,
        timeframe=tf,
        horizon_bars=horizon_bars,
        asof=int(last.end_time),
        due=int(last.end_time) + SECONDS[tf] * horizon_bars,
        reference_price=float(last.close),
        support=support,
        resistance=resistance,
        liquidity_targets=[support, resistance],
        invalidation=support if last.ema20 > last.ema50 else resistance,
        regime=last.regime,
        explanation=list(dict.fromkeys(factors)),
        status="unavailable",
        reason="No validated model promoted for this asset, source and horizon. Train in Model Performance.",
        probability=None,
        direction=None,
        expected_high=None,
        expected_low=None,
        session=window,
        outcome_start=window["start"] if window else int(last.end_time),
        validation_status="NO VALIDATED MODEL",
        data_age_seconds=max(0, int(time.time() - last.end_time)),
    )
    if window:
        result["due"] = window["end"]
    # Scenarios are conditional levels, never assigned invented probabilities.
    width = float(last.atr) * np.sqrt(horizon_bars)
    result["scenarios"] = [
        dict(
            name="Bull",
            condition=f"Close above resistance {resistance:.6g}",
            low=resistance,
            high=resistance + width,
        ),
        dict(
            name="Base",
            condition="Price remains between observed support and resistance",
            low=support,
            high=resistance,
        ),
        dict(
            name="Bear",
            condition=f"Close below support {support:.6g}",
            low=max(0, support - width),
            high=support,
        ),
    ]
    if time.time() - int(last.end_time) > SECONDS[tf] * 1.5:
        result.update(
            status="unavailable",
            reason="Latest closed candle is stale or the market is closed; no fresh model prediction issued.",
        )
        return result
    if not p:
        return result
    result["supporting_factors"] = []
    result["opposing_factors"] = []
    side = (
        1 if p["direction"] == "Bullish" else (-1 if p["direction"] == "Bearish" else 0)
    )
    observed = [
        (
            "ema_gap",
            "EMA20 above EMA50" if last.ema_gap > 0 else "EMA20 below EMA50",
            1 if last.ema_gap > 0 else -1,
        ),
        ("sweep", "Confirmed liquidity sweep", float(last.sweep)),
        ("fvg", "Confirmed FVG", float(last.fvg)),
        (
            "htf_return",
            "Closed higher-timeframe return",
            float(last.htf_return) if np.isfinite(last.htf_return) else 0,
        ),
    ]
    for feature, label, signal in observed:
        if feature in p.get("used_features", []) and signal:
            result[
                (
                    "supporting_factors"
                    if side and signal * side > 0
                    else "opposing_factors"
                )
            ].append(label)

    estimates = p.pop("estimates")
    result.update(p)
    result.update(
        status="prediction",
        reason=None,
        expected_return=estimates["return"],
        volatility=max(0, estimates["volatility"]),
        expected_high=float(last.close)
        * (1 + max(0, estimates["high"], estimates["low"])),
        expected_low=max(
            0, float(last.close) * (1 + min(0, estimates["low"], estimates["high"]))
        ),
        confidence="Calibrated probability; consult held-out sample size",
        neutral_threshold=float(last.atr_ratio * 0.15),
    )
    signal = build_signal(
        price=float(last.close),
        atr=float(last.atr),
        support=support,
        resistance=resistance,
        probabilities=result["probabilities"],
        expected_return=float(estimates["return"]),
        policy=SignalPolicy(
            min_directional_probability=settings.signal_min_directional_probability,
            min_probability_margin=settings.signal_min_margin,
            min_expected_atr_multiple=settings.signal_min_expected_atr_multiple,
            minimum_rr=settings.signal_min_rr,
            fee_slippage_bps=settings.signal_cost_bps,
        ),
    )
    result.update(
        signal_action=signal["action"],
        model_direction=signal["model_direction"],
        signal_probability=signal["probability"],
        signal_margin=signal["margin"],
        signal_confidence=signal["confidence"],
        entry=signal["entry"],
        stop_loss=signal["stop_loss"],
        take_profit=signal["take_profit"],
        risk_reward=signal["risk_reward"],
        signal_reason=signal["reason"],
        edge_threshold_return=signal["edge_threshold_return"],
    )
    # The public direction is the trading decision; model_direction preserves
    # the raw classifier direction for settlement and research metrics.
    result["direction"] = signal["action"]
    result["explanation"].append(
        "Detected factors describe context; they are not causal model attributions."
    )
    return store.save_prediction(result)
