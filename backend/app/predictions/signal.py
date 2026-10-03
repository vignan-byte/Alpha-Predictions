"""Production signal decision layer.

The ML classifier estimates directional class probabilities.  This module is a
separate policy layer that converts those probabilities into a trading decision
or an explicit NO-TRADE abstention.  It never changes model probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SignalPolicy:
    min_directional_probability: float = 0.55
    min_probability_margin: float = 0.08
    min_expected_atr_multiple: float = 0.15
    minimum_rr: float = 2.0
    fee_slippage_bps: float = 8.0


def build_signal(*, price: float, atr: float, support: float, resistance: float,
                 probabilities: dict[str, float], expected_return: float,
                 policy: SignalPolicy | None = None) -> dict:
    """Return LONG/SHORT/NO-TRADE with deterministic risk levels."""
    policy = policy or SignalPolicy()
    bull = float(probabilities.get("Bullish", 0.0))
    bear = float(probabilities.get("Bearish", 0.0))
    neutral = float(probabilities.get("Neutral", 0.0))
    directional = max(bull, bear)
    raw_side = "LONG" if bull >= bear else "SHORT"
    other = bear if raw_side == "LONG" else bull
    margin = directional - max(other, neutral)

    atr = max(float(atr or 0.0), price * 1e-5)
    cost_floor = max(price * policy.fee_slippage_bps / 100_000, atr * 0.02)
    edge_floor = max(atr * policy.min_expected_atr_multiple, cost_floor * 2)
    signed_edge = float(expected_return) if raw_side == "LONG" else -float(expected_return)

    eligible = (
        directional >= policy.min_directional_probability
        and margin >= policy.min_probability_margin
        and signed_edge >= edge_floor / max(price, 1e-12)
    )

    entry = float(price)
    if raw_side == "LONG":
        stop = float(support) if 0 < support < entry else entry - 1.5 * atr
        risk = max(entry - stop, atr * 0.5)
        stop = entry - risk
        target = entry + max(policy.minimum_rr * risk, edge_floor)
    else:
        stop = float(resistance) if resistance > entry else entry + 1.5 * atr
        risk = max(stop - entry, atr * 0.5)
        stop = entry + risk
        target = entry - max(policy.minimum_rr * risk, edge_floor)

    rr = abs(target - entry) / max(abs(entry - stop), 1e-12)
    action = raw_side if eligible and rr >= policy.minimum_rr else "NO-TRADE"
    confidence = (
        "HIGH" if directional >= 0.70 and margin >= 0.15 and action != "NO-TRADE"
        else "MEDIUM" if directional >= 0.60 and margin >= 0.10 and action != "NO-TRADE"
        else "LOW" if action != "NO-TRADE" else "ABSTAIN"
    )

    return {
        "action": action,
        "model_direction": raw_side,
        "probability": directional,
        "margin": margin,
        "neutral_probability": neutral,
        "confidence": confidence,
        "entry": entry,
        "stop_loss": stop,
        "take_profit": target,
        "risk_reward": rr,
        "edge_threshold_return": edge_floor / max(price, 1e-12),
        "signed_expected_return": signed_edge,
        "transaction_cost_floor_bps": policy.fee_slippage_bps,
        "reason": (
            "Validated directional edge passed probability, separation and expected-return gates."
            if action != "NO-TRADE"
            else "No statistically sufficient edge after probability, separation and expected-return gates."
        ),
    }
