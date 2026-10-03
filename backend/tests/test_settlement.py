import time
from app.database import store
from app.predictions.evaluation import settle, performance


def test_settlement_requires_full_matching_window(candles):
    origin = 100
    p = dict(
        source="demo",
        symbol="TEST",
        horizon="15m",
        timeframe="5m",
        horizon_bars=3,
        asof=int(candles.end_time.iloc[origin]),
        due=int(candles.end_time.iloc[origin + 3]),
        model_version="test-settlement",
        reference_price=float(candles.close.iloc[origin]),
        neutral_threshold=0.001,
        direction="Bullish",
        expected_return=0.01,
        probabilities={"Bearish": 0.1, "Neutral": 0.2, "Bullish": 0.7},
    )
    store.save_prediction(p)
    assert settle(candles.iloc[: origin + 3], "TEST", "demo", "5m") == 0
    assert settle(candles, "TEST", "binance", "5m") == 0
    assert settle(candles, "TEST", "demo", "5m") == 1
    row = store.history("TEST", "demo")[0]
    assert row["result"]["actual_high"] == float(
        candles.high.iloc[origin + 1 : origin + 4].max()
    )
    assert settle(candles, "TEST", "demo", "5m") == 0


def test_forward_metrics_remove_overlapping_labels():
    rows = []
    for i in range(100):
        rows.append(
            dict(
                symbol="TEST",
                source="demo",
                horizon="1h",
                asof=i,
                due=i + 10,
                probabilities={"Bearish": 0.1, "Neutral": 0.1, "Bullish": 0.8},
                result={"actual_outcome": "Bullish", "absolute_return_error": 0.01},
            )
        )
    m = performance(rows)
    assert m["non_overlapping"] == 10 and m["status"] == "Insufficient sample size"
