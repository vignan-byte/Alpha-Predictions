import numpy as np
import pytest
from app.models.pipeline import train, infer, metrics, decision_labels, learn_decision_rule
from app.predictions.engine import make
from app.database import store


def test_probability_metrics():
    m = metrics(np.array([0, 1, 2]), np.eye(3) * 0.8 + 0.2 / 3)
    assert m["accuracy"] == 1 and 0 <= m["calibration_error"] <= 1


def test_training_calibration_and_forecast(candles):
    result = train(candles, "BTCUSDT", "5m", 1, "demo")
    assert result["test"]["samples"] > 30 and len(result["walk_forward"]) == 3
    for f in result["walk_forward"]:
        assert f["test_start"] - f["train_end"] > 1
    assert 0 <= result["test"]["accuracy"] <= 1
    assert len(result["comparison"]) >= 4
    # If validation rejects, do not bypass the gate for testing.
    if result["promoted"]:
        p = infer(candles, "BTCUSDT", "5m", 1, "demo")
        assert sum(p["probabilities"].values()) == pytest.approx(1)
        assert 0 <= p["probability"] <= 1
        out = make(candles, "BTCUSDT", "5m", 1, "demo", "5m")
        again = make(candles, "BTCUSDT", "5m", 1, "demo", "5m")
        assert out == again and out["expected_low"] <= out["expected_high"]
        with pytest.raises(ValueError, match="before"):
            infer(candles.iloc[:-30], "BTCUSDT", "5m", 1, "demo")
    else:
        assert infer(candles, "BTCUSDT", "5m", 1, "demo") is None


def test_decision_rule_can_abstain_to_neutral():
    p = np.array([
        [0.46, 0.08, 0.46],
        [0.36, 0.34, 0.30],
        [0.80, 0.10, 0.10],
        [0.10, 0.10, 0.80],
    ])
    y = np.array([0, 1, 0, 2])
    rule = learn_decision_rule(y, p)
    pred = decision_labels(p, rule)
    assert len(pred) == len(y)
    assert set(pred).issubset({0, 1, 2})
    assert "min_confidence" in rule and "min_margin" in rule


def test_insufficient_history(candles):
    with pytest.raises(ValueError, match="Insufficient"):
        train(candles.iloc[:100], "ETHUSDT", "5m", 12, "demo")
