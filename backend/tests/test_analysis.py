import asyncio
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pytest
from app.data.providers import (
    MockProvider,
    parse_binance,
    parse_kline,
    validate,
    ProviderError,
    service,
)
from app.indicators.engine import calculate
from app.ict_smc.engine import calculate as ict
from app.features.engine import build, targets, FEATURES
from app.sessions.engine import sessions
from app.backtesting.engine import run


def test_binance_parser():
    d = parse_binance([[1000000, "10", "12", "9", "11", "20", 1059999]])
    assert (
        d.close.iloc[0] == 11 and d.time.iloc[0] == 1000 and d.end_time.iloc[0] == 1060
    )


def test_stream_parser():
    d = parse_kline(
        {
            "k": {
                "t": 1000000,
                "T": 1059999,
                "o": "10",
                "h": "12",
                "l": "9",
                "c": "11",
                "v": "20",
                "x": True,
            }
        }
    )
    assert d["closed"] and d["end_time"] == 1060 and d["close"] == 11


def test_invalid_ohlc():
    with pytest.raises(ProviderError):
        validate(
            pd.DataFrame([dict(time=0, open=10, close=11, high=9, low=8, volume=1)])
        )


def test_demo_history_stable():
    a = asyncio.run(MockProvider().candles("BTCUSDT", "5m", 150))
    b = asyncio.run(MockProvider().candles("BTCUSDT", "5m", 200))
    pd.testing.assert_frame_equal(
        a.iloc[:-1].reset_index(drop=True), b.iloc[-150:-1].reset_index(drop=True)
    )


def test_calendar_months():
    d = asyncio.run(MockProvider().candles("BTCUSDT", "1M", 60))
    assert (pd.to_datetime(d.time, unit="s", utc=True).dt.day == 1).all()
    assert np.array_equal(d.end_time.iloc[:-1].to_numpy(), d.time.iloc[1:].to_numpy())


def test_indicators_known():
    c = np.arange(1, 251, dtype=float)
    d = pd.DataFrame(
        dict(
            time=np.arange(250) * 300,
            end_time=np.arange(250) * 300 + 300,
            open=c,
            close=c,
            high=c + 1,
            low=c - 1,
            volume=np.ones(250),
        )
    )
    out = calculate(d)
    assert out.rsi.iloc[-1] == 100
    assert out.ema20.iloc[-1] == pytest.approx(
        pd.Series(c).ewm(span=20, adjust=False).mean().iloc[-1]
    )
    assert out.atr.iloc[-1] == pytest.approx(2)
    assert out.macd.iloc[-1] == pytest.approx(7, abs=0.001)
    assert out.sma20.iloc[-1] == pytest.approx(240.5)


def test_flat_rsi():
    d = pd.DataFrame(
        dict(
            time=np.arange(80) * 300,
            end_time=np.arange(80) * 300 + 300,
            open=10.0,
            close=10.0,
            high=11.0,
            low=9.0,
            volume=1.0,
        )
    )
    assert calculate(d).rsi.iloc[-1] == 50


def test_features_prefix_invariant(candles):
    full, ev, z = build(candles)
    prefix, pe, pz = build(candles.iloc[:600])
    pd.testing.assert_frame_equal(full.iloc[:600][FEATURES], prefix[FEATURES])
    assert [e for e in ev if e["time"] <= candles.time.iloc[599]] == pe


def test_targets_use_future_only(candles):
    d, _, _ = build(candles)
    t = targets(d, 6)
    assert t["high"].iloc[70] == pytest.approx(
        d.high.iloc[71:77].max() / d.close.iloc[70] - 1
    )
    assert t["low"].iloc[70] == pytest.approx(
        d.low.iloc[71:77].min() / d.close.iloc[70] - 1
    )
    assert t["return"].iloc[70] == pytest.approx(
        d.close.iloc[76] / d.close.iloc[70] - 1
    )
    assert t.tail(6).isna().all().all()


def test_fvg_and_invalidation():
    d = pd.DataFrame(
        dict(
            time=np.arange(5) * 60,
            open=[10, 11, 14, 14, 9],
            close=[11, 12, 15, 14, 8],
            high=[12, 13, 16, 15, 10],
            low=[9, 10, 14, 13, 7],
            atr=[1] * 5,
        )
    )
    f, e, z = ict(d)
    assert f.fvg.iloc[2] == 1
    assert f.inverse_fvg.iloc[4] == -1
    assert any(z["kind"] == "FVG" and z["status"] == "invalidated" for z in z)


def test_swing_confirmation_bos_sweep():
    c = [10, 11, 12, 15, 12, 11, 10, 12, 14, 17, 16, 14, 9, 8, 7, 6]
    d = pd.DataFrame(
        dict(
            time=np.arange(len(c)) * 60,
            open=np.array(c) - 0.2,
            close=c,
            high=np.array(c) + 1,
            low=np.array(c) - 1,
            atr=np.ones(len(c)),
        )
    )
    f, e, z = ict(d)
    assert np.isnan(f.swing_high.iloc[5]) and f.swing_high.iloc[6] == 16
    assert any(x["kind"] == "BOS" and x["side"] == 1 for x in e)
    assert any(x["kind"] == "CHoCH" and x["side"] == -1 for x in e)


def test_dst_sessions():
    summer = sessions(datetime(2026, 7, 6, 8, tzinfo=timezone.utc), "UTC")
    winter = sessions(datetime(2026, 1, 5, 9, tzinfo=timezone.utc), "UTC")
    assert next(r for r in summer["current"] if r["name"] == "London")[
        "start"
    ].endswith("07:00:00+00:00")
    assert next(r for r in winter["current"] if r["name"] == "London")[
        "start"
    ].endswith("08:00:00+00:00")


def test_weekend_sessions():
    s = sessions(datetime(2026, 10, 3, 20, tzinfo=timezone.utc), "Asia/Kolkata")
    assert not s["current"] and s["next"] is not None


def test_backtest_costs(candles):
    free = run(candles, cost_bps=0, slippage_bps=0)
    paid = run(candles, cost_bps=20, slippage_bps=5)
    assert free["total_trades"] > 0 and paid["net_return"] < free["net_return"]
    assert paid["max_drawdown"] <= 0
    for t in paid["trades"]:
        assert t["closed"] > t["opened"]


def test_no_silent_fallback(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "forex_api_key", "")
    with pytest.raises(ProviderError, match="FOREX_API_KEY"):
        asyncio.run(service.candles("EURUSD", "5m"))


def test_labels_reject_gaps(candles):
    d, _, _ = build(candles.drop(index=105).reset_index(drop=True))
    y = targets(d, 12)
    assert y.iloc[100].isna().all()
    assert y.iloc[120].notna().all()
