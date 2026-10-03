from app.predictions.signal import build_signal


def test_signal_abstains_on_weak_edge():
    s = build_signal(
        price=100.0,
        atr=1.0,
        support=99.5,
        resistance=100.5,
        probabilities={"Bearish": 0.46, "Neutral": 0.10, "Bullish": 0.44},
        expected_return=0.0001,
    )
    assert s["action"] == "NO-TRADE"
    assert s["confidence"] == "ABSTAIN"


def test_signal_requires_realistic_long_edge():
    s = build_signal(
        price=100.0,
        atr=1.0,
        support=98.5,
        resistance=101.0,
        probabilities={"Bearish": 0.10, "Neutral": 0.05, "Bullish": 0.85},
        expected_return=0.03,
    )
    assert s["action"] == "LONG"
    assert s["stop_loss"] < s["entry"] < s["take_profit"]
    assert s["risk_reward"] >= 2.0


def test_signal_requires_realistic_short_edge():
    s = build_signal(
        price=100.0,
        atr=1.0,
        support=99.0,
        resistance=102.0,
        probabilities={"Bearish": 0.82, "Neutral": 0.06, "Bullish": 0.12},
        expected_return=-0.03,
    )
    assert s["action"] == "SHORT"
    assert s["take_profit"] < s["entry"] < s["stop_loss"]
    assert s["risk_reward"] >= 2.0
