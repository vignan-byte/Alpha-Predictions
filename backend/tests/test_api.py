from fastapi.testclient import TestClient
from app.main import app
from app.database import store


def test_health_and_markets():
    with TestClient(app) as c:
        assert c.get("/health").json()["database"] == "connected"
        assert c.get("/health").json()["mode"] == "demo"
        assert len(c.get("/api/markets").json()) == 10
        assert c.get("/api/markets/INVALID").status_code == 404


def test_candles_analysis_prediction():
    with TestClient(app) as c:
        assert len(c.get("/api/candles/BTCUSDT?limit=100").json()["candles"]) == 100
        a = c.get("/api/analysis/BTCUSDT")
        assert a.status_code == 200
        assert a.json()["indicators"]["rsi"] is not None
        p = c.get("/api/predictions/ETHUSDT")
        assert p.status_code == 200
        assert p.json()["status"] == "unavailable" and p.json()["probability"] is None
        assert (
            c.get("/api/predictions/BTCUSDT/session").json()["status"] == "unavailable"
        )


def test_websocket_updates():
    with TestClient(app) as c:
        with c.websocket_connect("/ws/market/BTCUSDT?timeframe=5m") as ws:
            a = ws.receive_json()
            b = ws.receive_json()
            assert (
                a["source"] == b["source"] == "demo"
                and b["timestamp"] >= a["timestamp"]
            )
            assert a["type"] == "candle" and b["candle"]["close"] > 0


def test_watchlist_and_alerts():
    with TestClient(app) as c:
        assert c.put("/api/watchlist", json={"symbols": ["SOLUSDT"]}).status_code == 200
        assert c.get("/api/watchlist").json()["symbols"] == ["SOLUSDT"]
        r = c.post(
            "/api/alerts", json={"symbol": "SOLUSDT", "kind": "above", "level": 1}
        ).json()
        from app.alerts.engine import evaluate

        evaluate("SOLUSDT", "demo", 100, [])
        assert next(a for a in c.get("/api/alerts").json() if a["key"] == r["key"])[
            "triggered"
        ]
        assert c.delete("/api/alerts/" + r["key"]).status_code == 200


def test_backtest_and_news():
    with TestClient(app) as c:
        r = c.post("/api/backtest", json={"symbol": "BTCUSDT", "bars": 500}).json()
        assert "equity" in r and r["source"] == "demo"
        assert c.get("/api/news").json()["status"] == "blocked"
        assert c.get("/api/news").json()["items"] == []
        assert c.get("/api/performance").json()["status"] == "Insufficient sample size"


def test_origin_and_validation():
    with TestClient(app) as c:
        assert (
            c.put(
                "/api/watchlist",
                json={"symbols": []},
                headers={"Origin": "https://evil.example"},
            ).status_code
            == 403
        )
        assert c.get("/api/candles/BTCUSDT?timeframe=2s").status_code == 422
        assert c.put("/api/settings", json={"timezone": "invalid"}).status_code == 422
        assert c.post("/api/backtest", json={"cost_bps": -1}).status_code == 422
