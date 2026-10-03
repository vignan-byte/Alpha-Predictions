import asyncio
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.main import app
from app.core.config import settings
from app.core.security import RateLimiter, issue_cookie, valid_cookie, limiter
from app.database import store
from app.paper import engine as paper
from app.calendar.provider import CalendarProvider, normalize
from app.data.providers import ProviderError, MockProvider, service
from app.features.engine import build
from app.features.session_targets import next_window, session_targets
from app.sessions.engine import historical_sessions, session_sweeps
from app.backtesting.engine import run, chronological_report
from app.correlations.engine import matrix
from app.alerts.engine import evaluate


@pytest.fixture
def source():
    return "test-" + uuid.uuid4().hex


def order(source, side=1):
    return paper.preview(
        source,
        "BTCUSDT",
        100,
        time.time(),
        side,
        10,
        90 if side == 1 else 110,
        120 if side == 1 else 80,
        5,
        2,
    )


def test_paper_confirm_idempotent_and_costs(source):
    p = order(source)
    assert not paper.snapshot(source, "USDT")["positions"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(
            pool.map(
                lambda _: paper.confirm(source, "USDT", p["id"], 100, time.time()),
                range(4),
            )
        )
    a = paper.snapshot(source, "USDT")
    assert len(a["positions"]) == 1
    assert a["balance"] == pytest.approx(10000 - 100.02 * 10 * 0.0005)
    t = paper.close(source, "USDT", p["id"], 110, time.time())
    assert t["exit"] == pytest.approx(109.978)
    assert t["net_pnl"] == pytest.approx(
        (109.978 - 100.02) * 10 - (109.978 + 100.02) * 10 * 0.0005
    )
    assert paper.close(source, "USDT", p["id"], 110, time.time()) == t
    assert paper.snapshot(source, "USDT")["balance"] == pytest.approx(
        10000 + t["net_pnl"]
    )


@pytest.mark.parametrize(
    "side,mark,reason",
    [(1, 89, "stop"), (1, 121, "target"), (-1, 111, "stop"), (-1, 79, "target")],
)
def test_paper_brackets(source, side, mark, reason):
    p = order(source, side)
    paper.confirm(source, "USDT", p["id"], 100, time.time())
    paper.mark(source, "BTCUSDT", mark, time.time())
    a = paper.snapshot(source, "USDT")
    assert not a["positions"]
    assert a["trades"][0]["reason"] == reason


def test_paper_quote_guards_and_isolation(source):
    with pytest.raises(ValueError, match="Fresh"):
        paper.preview(source, "BTCUSDT", 100, time.time() - 200, 1, 1, 90, 120)
    with pytest.raises(ValueError, match="Finite"):
        paper.preview(source, "BTCUSDT", np.nan, time.time(), 1, 1, 90, 120)
    with pytest.raises(ValueError, match="Insufficient"):
        paper.preview(source, "BTCUSDT", 100, time.time(), 1, 1000, 90, 120)
    p = order(source)
    with pytest.raises(ValueError, match="tolerance"):
        paper.confirm(source, "USDT", p["id"], 102, time.time())
    with pytest.raises(ValueError, match="not found"):
        paper.confirm(source + "other", "USDT", p["id"], 100, time.time())
    with paper.transaction(source, "USDT") as (book, s):
        book["orders"][0]["expires"] = 0
    with pytest.raises(ValueError, match="expired"):
        paper.confirm(source, "USDT", p["id"], 100, time.time())
    assert paper.snapshot(source, "USD")["balance"] == 10000


def test_paper_risk_and_configuration(source):
    paper.configure(source, "USDT", 5000)
    p = paper.preview(source, "BTCUSDT", 100, time.time(), 1, 1, 90, 120, risk_pct=1)
    assert p["estimated_risk"] <= 50.01
    paper.confirm(source, "USDT", p["id"], 100, time.time())
    with pytest.raises(ValueError, match="first filled"):
        paper.configure(source, "USDT", 20000)
    before = paper.snapshot(source, "USDT")
    paper.mark(source, "BTCUSDT", 50, time.time() - 200)
    assert paper.snapshot(source, "USDT")["positions"] == before["positions"]


def test_paper_api_preview_confirmation_and_audit():
    with TestClient(app) as c:
        q = c.get("/api/paper/quote/ETHUSDT").json()["price"]
        r = c.post(
            "/api/paper/preview",
            json=dict(
                symbol="ETHUSDT", side=1, units=0.001, stop=q * 0.9, target=q * 1.1
            ),
        )
        assert r.status_code == 200, r.text
        p = r.json()
        assert (
            c.post(
                "/api/paper/confirm",
                json=dict(symbol="ETHUSDT", preview_id=p["id"], confirm=False),
            ).status_code
            == 422
        )
        assert (
            c.post(
                "/api/paper/confirm",
                json=dict(symbol="ETHUSDT", preview_id=p["id"], confirm=True),
            ).status_code
            == 200
        )
        assert (
            c.post(
                f"/api/paper/positions/{p['id']}/close",
                json=dict(symbol="ETHUSDT", confirm=True),
            ).status_code
            == 200
        )
        assert any(e["action"] == "paper.close" for e in c.get("/api/audit").json())


def test_auth_http_cookie_websocket_and_origin(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "test-access-token-32-characters-long")
    limiter.buckets.clear()
    with TestClient(app) as c:
        assert c.get("/api/markets").status_code == 401
        assert c.get("/health").status_code == 200
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect("/ws/market/BTCUSDT"):
                pass
        assert c.post("/api/auth/login", json={"token": "wrong"}).status_code == 401
        assert (
            c.post(
                "/api/auth/login",
                json={"token": settings.api_token},
                headers={"Origin": "https://evil.example"},
            ).status_code
            == 403
        )
        r = c.post("/api/auth/login", json={"token": settings.api_token})
        assert r.status_code == 200
        assert (
            "HttpOnly" in r.headers["set-cookie"]
            and "SameSite=strict" in r.headers["set-cookie"]
        )
        assert c.get("/api/markets").status_code == 200
        with c.websocket_connect("/ws/market/BTCUSDT") as ws:
            assert ws.receive_json()["source"] == "demo"
        c.post("/api/auth/logout")
        assert c.get("/api/markets").status_code == 401
        assert (
            c.get(
                "/api/markets",
                headers={"Authorization": "Bearer " + settings.api_token},
            ).status_code
            == 200
        )
    assert valid_cookie(issue_cookie())
    assert not valid_cookie(issue_cookie() + "bad")


def test_rate_limit_expiry_and_login(monkeypatch):
    l = RateLimiter()
    assert l.allow("x", 2, 0)
    assert l.allow("x", 2, 1)
    assert not l.allow("x", 2, 2)
    assert l.allow("x", 2, 61)
    monkeypatch.setattr(settings, "api_token", "test-token")
    limiter.buckets.clear()
    with TestClient(app) as c:
        for _ in range(5):
            assert c.post("/api/auth/login", json={"token": "wrong"}).status_code == 401
        assert c.post("/api/auth/login", json={"token": "wrong"}).status_code == 429
    limiter.buckets.clear()


def test_calendar_schema_cache_filters_and_failure(monkeypatch):
    monkeypatch.setattr(settings, "calendar_api_key", "fixture-key")
    rows = [
        dict(
            CalendarId="1",
            Date="2026-10-01T12:30:00",
            Event="CPI",
            Country="United States",
            Importance=3,
            Forecast="2%",
            Previous="1.9%",
            Actual="0",
            Source="BLS",
            SourceURL="https://www.bls.gov/",
        )
    ]
    calls = []

    async def fetch(*a, **kw):
        calls.append(1)
        return rows

    monkeypatch.setattr("app.calendar.provider.get_json", fetch)
    p = CalendarProvider()
    r = asyncio.run(p.fetch("Asia/Kolkata", "high", "USD"))
    assert r["status"] == "live" and r["events"][0]["local_time"].endswith(
        "18:00:00+05:30"
    )
    assert r["events"][0]["actual"] == "0"
    assert not asyncio.run(p.fetch(impact="low"))["events"]
    assert len(calls) == 1
    p.cache["fetched_at"] = 0

    async def failure(*a, **kw):
        raise ProviderError("Fixture provider outage")

    monkeypatch.setattr("app.calendar.provider.get_json", failure)
    stale = asyncio.run(p.fetch())
    assert stale["status"] == "stale" and stale["events"]
    monkeypatch.setattr(settings, "calendar_api_key", "")
    assert asyncio.run(p.fetch())["status"] == "blocked"


def test_calendar_zero_actual():
    assert (
        normalize(
            dict(
                Date="2026-10-01T00:00:00Z",
                Event="Rate",
                Country="Japan",
                Importance=3,
                Actual=0,
            )
        )["actual"]
        == 0
    )


def test_historical_sessions_complete_and_causal(candles):
    windows = historical_sessions(candles)
    assert windows and any(w["complete"] for w in windows)
    for w in windows:
        subset = candles[(candles.time >= w["start"]) & (candles.end_time <= w["end"])]
        assert w["high"] == subset.high.max() and w["low"] == subset.low.min()
    ev = session_sweeps(candles, windows)
    assert all(e["confirmed_at"] <= candles.end_time.iloc[-1] for e in ev)
    prefix = candles.iloc[:600]
    pe = session_sweeps(prefix, historical_sessions(prefix))
    assert [e for e in ev if e["confirmed_at"] <= prefix.end_time.iloc[-1]] == pe


def test_next_session_targets_contiguous_future_only():
    df = (
        asyncio.run(MockProvider().candles("BTCUSDT", "1h", 300))
        .iloc[:-1]
        .reset_index(drop=True)
    )
    d, _, _ = build(df)
    target = session_targets(d)
    i = next(i for i in range(70, len(d)) if pd.notna(target["return"].iloc[i]))
    w = next_window(d.end_time.iloc[i])
    f = d[(d.time >= w["start"]) & (d.end_time <= w["end"])]
    assert f.time.iloc[0] >= d.end_time.iloc[i]
    assert target["return"].iloc[i] == pytest.approx(
        f.close.iloc[-1] / d.close.iloc[i] - 1
    )
    g = d.drop(index=f.index[2]).reset_index(drop=True)
    assert session_targets(g).iloc[i].isna().all()


def test_backtest_fixed_size_spread_and_chronological(candles):
    free = run(candles, sizing="fixed", fixed_units=0.1, spread_bps=0)
    paid = run(candles, sizing="fixed", fixed_units=0.1, spread_bps=10)
    assert all(t["units"] <= 0.1 for t in paid["trades"])
    assert paid["net_return"] < free["net_return"]
    r = chronological_report(candles, sizing="fixed", fixed_units=0.1)
    a, b, *folds = r["segments"]
    assert a["end"] <= b["start"]
    assert len(folds) == 3 and all(
        x["end"] <= y["start"] for x, y in zip(folds, folds[1:])
    )
    assert a["total_trades"] == a["wins"] + a["losses"]


def test_correlation_matrix_return_alignment(candles):
    b = candles.copy()
    b["close"] *= 2
    result = matrix({"A": candles, "B": b}, 50)
    assert result["matrix"]["A"]["B"] == pytest.approx(1)
    assert result["matrix"]["A"]["B"] == result["matrix"]["B"]["A"]
    assert result["relationships"][0]["samples"] == 50


@pytest.mark.parametrize(
    "kind,first,second",
    [
        ("direction", {"direction": "Bearish"}, {"direction": "Bullish"}),
        ("probability", {"probability": 0.5}, {"probability": 0.7}),
        (
            "model",
            {"validation_status": "NO VALIDATED MODEL"},
            {"validation_status": "VALIDATED"},
        ),
    ],
)
def test_alert_transitions_dedup_and_source(source, kind, first, second):
    key = uuid.uuid4().hex
    store.put(
        "alert_rules",
        key,
        dict(
            symbol="TEST",
            source=source,
            kind=kind,
            created=int(time.time()),
            repeat=True,
            cooldown_seconds=30,
            delta=0.1,
            triggered=False,
        ),
    )
    assert not evaluate("TEST", source, 100, [], first)
    assert len(evaluate("TEST", source, 100, [], second)) == 1
    assert not evaluate("TEST", source, 100, [], second)
    assert not evaluate("TEST", source + "other", 100, [], first)


def test_alert_cooldown_and_event_id(source, monkeypatch):
    now = int(time.time())
    key = uuid.uuid4().hex
    store.put(
        "alert_rules",
        key,
        dict(
            symbol="TEST",
            source=source,
            kind="signal",
            signal="BOS",
            created=now,
            repeat=True,
            cooldown_seconds=30,
            triggered=False,
        ),
    )
    event = dict(kind="BOS", time=now, confirmed_at=now)
    assert len(evaluate("TEST", source, 100, [event])) == 1
    monkeypatch.setattr("app.alerts.engine.time.time", lambda: now + 31)
    assert not evaluate("TEST", source, 100, [event])
    assert (
        len(
            evaluate(
                "TEST", source, 100, [dict(event, time=now + 31, confirmed_at=now + 31)]
            )
        )
        == 1
    )


def test_extended_endpoints_and_invalid_inputs():
    with TestClient(app) as c:
        assert c.get("/api/calendar").json()["status"] == "blocked"
        assert c.get("/api/provider-status").json()["real_execution"] is False
        assert c.get("/api/sessions/BTCUSDT/history").json()["windows"]
        m = c.get("/api/correlations/matrix")
        assert m.status_code == 200, m.text
        assert m.json()["matrix"]["BTCUSDT"]["BTCUSDT"] == pytest.approx(1)
        assert (
            c.post(
                "/api/paper/preview", json=dict(symbol="INVALID", stop=1, target=2)
            ).status_code
            == 404
        )
        assert (
            c.post(
                "/api/backtest",
                content='{"cost_bps":NaN}',
                headers={"Content-Type": "application/json"},
            ).status_code
            == 422
        )


def test_migration_preserves_existing_records(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text, inspect
    from alembic import command
    from alembic.config import Config
    from app.core.config import ROOT

    engine = create_engine("sqlite:///" + str(tmp_path / "upgrade.db"))
    monkeypatch.setattr(store, "engine", engine)
    cfg = Config(str(ROOT / "backend/alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend/migrations"))
    command.upgrade(cfg, "0001")
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO records(kind,key,payload,updated) VALUES ('watchlists','preserve','{\"symbols\":[\"BTCUSDT\"]}',1)"
            )
        )
    command.upgrade(cfg, "head")
    with engine.connect() as c:
        assert json.loads(
            c.execute(text("SELECT payload FROM records WHERE key='preserve'")).scalar()
        )["symbols"] == ["BTCUSDT"]
        assert (
            c.execute(text("SELECT version_num FROM alembic_version")).scalar()
            == "0002"
        )
    assert {"records", "predictions", "paper_accounts", "audit_events"}.issubset(
        inspect(engine).get_table_names()
    )
    engine.dispose()


def test_forex_real_rest_fallback_and_status(monkeypatch):
    from app.data.providers import ForexProvider, DataService

    monkeypatch.setattr(settings, "forex_api_key", "fixture-key")
    provider = ForexProvider()

    async def unavailable(*args):
        yield {"type": "status", "status": "unavailable"}

    stamp = int(time.time()) // 60 * 60

    async def bars(*args):
        return pd.DataFrame(
            [
                dict(
                    time=stamp,
                    end_time=stamp + 60,
                    open=1.1,
                    high=1.2,
                    low=1.0,
                    close=1.15,
                    volume=np.nan,
                )
            ]
        )

    monkeypatch.setattr(provider, "websocket_stream", unavailable)
    monkeypatch.setattr(provider, "candles", bars)

    async def exercise():
        stream = provider.stream("EURUSD", "1m")
        first = await anext(stream)
        second = await anext(stream)
        await stream.aclose()
        return first, second

    first, second = asyncio.run(exercise())
    assert first["transport"] == "rest"
    assert second["source"] == "twelvedata" and second["candle"]["close"] == 1.15
    data = DataService()
    data.record_tick("EURUSD", second)
    assert data.ticks["EURUSD"]["transport"] == "rest"


def test_cookie_expiry_and_ws_origin(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "fixture-access-token")
    now = time.time()
    cookie = issue_cookie()
    monkeypatch.setattr("app.core.security.time.time", lambda: now + 43201)
    assert not valid_cookie(cookie)
    with TestClient(app) as c:
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect(
                "/ws/market/BTCUSDT",
                headers={
                    "Authorization": "Bearer fixture-access-token",
                    "Origin": "https://evil.example",
                },
            ):
                pass


def test_launcher_rejects_occupied_port():
    import importlib.util, socket
    from app.core.config import ROOT

    spec = importlib.util.spec_from_file_location(
        "launcher", ROOT / "scripts/launch.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        with pytest.raises(RuntimeError, match="occupied"):
            module.preflight(port)


def test_stale_quote_cannot_fill_a_paper_order(monkeypatch, source):
    from app.data.providers import CryptoProvider, DataService

    data = DataService()
    provider = CryptoProvider()

    async def old_quote(symbol):
        return {"price": 100, "timestamp": int(time.time()) - 300}

    monkeypatch.setattr(provider, "quote", old_quote)
    monkeypatch.setattr(data, "provider", lambda symbol: (provider, "binance"))
    quote = asyncio.run(data.snapshot("BTCUSDT"))
    assert quote["status"] == "stale"
    with pytest.raises(ValueError, match="Fresh"):
        paper.preview(
            source, "BTCUSDT", quote["price"], quote["timestamp"], 1, 1, 90, 120
        )


def test_concurrent_forecasts_keep_first_immutable_record(source):
    p = dict(
        source=source,
        symbol="TEST",
        horizon="5m",
        asof=int(time.time()),
        due=int(time.time()) + 300,
        model_version="fixture",
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda i: store.save_prediction(dict(p, first_writer_value=i)),
                range(24),
            )
        )
    assert all(result == results[0] for result in results)
    assert len(store.history(symbol="TEST", source=source)) == 1


def test_concurrent_document_creation(source):
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: store.put("fixture", source, {"value": i}), range(24)))
    assert store.get("fixture", source)["value"] in range(24)


@pytest.mark.parametrize("kind", ["calendar", "session"])
def test_session_calendar_alerts_deduplicate(source, kind, monkeypatch):
    now = int(time.time())
    key = uuid.uuid4().hex
    store.put(
        "alert_rules",
        key,
        dict(
            symbol="EURUSD",
            source=source,
            kind=kind,
            created=now - 60,
            repeat=True,
            cooldown_seconds=30,
            triggered=False,
        ),
    )
    session = {
        "current": [
            {
                "name": "London",
                "start": datetime.fromtimestamp(now - 10, timezone.utc).isoformat(),
            }
        ]
    }
    releases = [
        {
            "id": "fixture-CPI",
            "impact": "high",
            "timestamp": now + 300,
            "currency": "USD",
        }
    ]
    assert (
        len(
            evaluate(
                "EURUSD",
                source,
                1.1,
                [],
                session_context=session,
                calendar_events=releases,
            )
        )
        == 1
    )
    monkeypatch.setattr("app.alerts.engine.time.time", lambda: now + 40)
    assert not evaluate(
        "EURUSD", source, 1.1, [], session_context=session, calendar_events=releases
    )


def test_overlap_with_missing_bar_is_not_complete(candles):
    overlap = next(
        w
        for w in historical_sessions(candles)
        if w["name"] == "London/NY overlap" and w["complete"]
    )
    missing = candles[
        (candles.time >= overlap["start"]) & (candles.end_time <= overlap["end"])
    ].index[2]
    g = candles.drop(index=missing).reset_index(drop=True)
    window = next(
        w
        for w in historical_sessions(g)
        if w["name"] == overlap["name"] and w["start"] == overlap["start"]
    )
    assert not window["complete"]
