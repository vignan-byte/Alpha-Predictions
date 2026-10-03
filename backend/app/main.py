import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import numpy as np
from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    BackgroundTasks,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool
from app.core.config import settings
from app.core.utils import clean
from app.data.providers import service, ASSETS, SECONDS, ProviderError, CryptoProvider
from app.features.engine import build
from app.sessions.engine import sessions
from app.database import store
from app.models.pipeline import train
from app.predictions.engine import make, HORIZONS
from app.predictions.evaluation import settle, performance
from app.backtesting.engine import run as backtest, chronological_report
from app.alerts.engine import evaluate
from app.calendar.provider import calendar
from app.correlations.engine import correlation
from app.news.provider import news
from app.api.extended import router as extended_router, paper_worker
from app.core.security import authorized, limiter
from app.sessions.engine import historical_sessions, session_sweeps

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("alpha")
logging.getLogger("httpx").setLevel(logging.WARNING)
BACKGROUND = set()
training_lock = asyncio.Lock()


async def collector():
    # Watchlisted assets only, 60-second cycle; caches constrain REST usage.
    while True:
        for symbol in store.get(
            "watchlists", "default", {"symbols": ["BTCUSDT", "ETHUSDT", "EURUSD"]}
        )["symbols"]:
            try:
                df, source = await service.candles(symbol, "5m", 800)
                closed = df[df.end_time <= time.time()]
                if len(closed) < 60:
                    continue
                d, events, _ = await run_in_threadpool(build, closed)
                events += session_sweeps(closed, historical_sessions(closed))
                forecast = await run_in_threadpool(
                    make, closed, symbol, "5m", 12, source, "1h"
                )
                calendar_data = await calendar.fetch()
                await run_in_threadpool(
                    evaluate,
                    symbol,
                    source,
                    float(df.close.iloc[-1]),
                    events,
                    forecast,
                    sessions(),
                    calendar_data.get("events", []),
                )
                await run_in_threadpool(settle, closed, symbol, source, "5m")
                for horizon in ["5m", "15m", "30m", "1h"]:
                    await run_in_threadpool(
                        make,
                        closed,
                        symbol,
                        "5m",
                        HORIZONS[horizon][1],
                        source,
                        horizon,
                    )
            except Exception as exc:
                log.warning(
                    json.dumps(
                        {
                            "event": "collector_error",
                            "symbol": symbol,
                            "error_type": type(exc).__name__,
                        }
                    )
                )
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app):
    store.init_db()
    task = asyncio.create_task(collector())
    paper_task = asyncio.create_task(paper_worker())
    yield
    task.cancel()
    paper_task.cancel()
    try:
        await paper_task
    except asyncio.CancelledError:
        pass
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="AlphaPredictorsAI", version="2.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


app.include_router(extended_router)


@app.middleware("http")
async def local_mutations(request: Request, call_next):
    # Prevent cross-site writes against the local service. Bind to loopback; not multiuser auth.
    origin = request.headers.get("origin")
    ip = request.client.host if request.client else "unknown"
    path = request.url.path
    if not limiter.allow(
        ip + ("login" if path == "/api/auth/login" else ""),
        5 if path == "/api/auth/login" else settings.rate_limit_per_minute,
    ):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded; retry after 60 seconds"},
            headers={"Retry-After": "60"},
        )
    if (
        path.startswith("/api/")
        and path not in ("/api/auth/status", "/api/auth/login")
        and not authorized(request.headers, request.cookies)
    ):
        return JSONResponse(
            status_code=401, content={"detail": "Authentication required"}
        )
    if (
        request.method in ("POST", "PUT", "DELETE", "PATCH")
        and origin
        and origin not in settings.cors_origins.split(",")
    ):
        return JSONResponse(status_code=403, content={"detail": "Origin rejected"})
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    log.info(
        json.dumps(
            dict(
                event="request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                ms=round((time.perf_counter() - started) * 1000),
            )
        )
    )
    return response


@app.exception_handler(ProviderError)
async def provider_error(request, exc):
    return JSONResponse(
        status_code=503, content={"detail": str(exc), "status": "unavailable"}
    )


@app.exception_handler(ValueError)
async def value_error(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def server_error(request, exc):
    log.error(json.dumps(dict(event="server_error", error_type=type(exc).__name__)))
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal operation failed. Check backend logs for error type."
        },
    )


def check(symbol, tf="5m"):
    if symbol not in ASSETS:
        raise HTTPException(404, "Unsupported symbol")
    if tf not in SECONDS:
        raise HTTPException(422, "Unsupported timeframe")


def closed(df):
    return df[df.end_time <= time.time()].reset_index(drop=True)


@app.get("/health/live")
async def liveness():
    return {"status": "ok", "service": "alphapredictorsai"}


@app.get("/health/ready")
async def readiness():
    with store.engine.connect() as c:
        c.execute(text("SELECT 1"))
    return {
        "status": "ready",
        "database": "connected",
        "mode": "demo" if settings.mock_mode else "live",
        "ml_engine": "ready",
    }


@app.get("/health")
async def health():
    with store.engine.connect() as c:
        c.execute(text("SELECT 1"))
    return dict(
        status="ok",
        mode="demo" if settings.mock_mode else "live",
        market_data=(
            "demo"
            if settings.mock_mode
            else "configured; connection verified per request"
        ),
        prediction_engine="ready",
        database="connected",
        ml_engine="ready",
        news="configured" if settings.news_api_key else "disabled",
        timestamp=int(time.time()),
    )


@app.get("/api/settings")
async def get_settings():
    return dict(
        mock_mode=settings.mock_mode,
        forex_configured=bool(settings.forex_api_key),
        news_configured=bool(settings.news_api_key),
        display_timezone=store.get(
            "settings", "display", {"timezone": settings.display_timezone}
        )["timezone"],
        trade_execution=False,
    )


class Display(BaseModel):
    timezone: str


@app.put("/api/settings")
async def set_settings(body: Display):
    try:
        ZoneInfo(body.timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(422, "Unknown IANA timezone")
    return store.put("settings", "display", {"timezone": body.timezone})


@app.get("/api/markets")
async def markets():
    return [
        dict(
            symbol=k,
            name=v[0],
            market=v[1],
            source=(
                "demo"
                if settings.mock_mode
                else ("binance" if v[1] == "crypto" else "twelvedata")
            ),
            available=settings.mock_mode
            or v[1] == "crypto"
            or bool(settings.forex_api_key),
        )
        for k, v in ASSETS.items()
    ]


@app.get("/api/markets/{symbol}")
async def quote(symbol: str):
    check(symbol)
    provider, source = service.provider(symbol)
    if isinstance(provider, CryptoProvider):
        q = await provider.quote(symbol)
    else:
        df, _ = await service.candles(symbol, "5m", 300)
        latest = df.iloc[-1]
        recent = df[df.time >= latest.time - 86400]
        q = dict(
            price=latest.close,
            change=(latest.close / recent.open.iloc[0] - 1) * 100,
            high=recent.high.max(),
            low=recent.low.min(),
            volume=recent.volume.sum(min_count=1),
            bid=None,
            ask=None,
            timestamp=int(latest.time),
            statistics_window="Last available 24h candle window",
        )
    return clean(
        dict(
            symbol=symbol,
            source=source,
            status=(
                "demo"
                if source == "demo"
                else ("stale" if time.time() - q["timestamp"] > 600 else "live")
            ),
            **q,
        )
    )


@app.get("/api/candles/{symbol}")
async def candles(
    symbol: str,
    timeframe: str = "5m",
    limit: int = Query(500, ge=30, le=1000),
    before: int | None = None,
):
    check(symbol, timeframe)
    df, source = await service.candles(symbol, timeframe, limit, before)
    store.put(
        "candles",
        f"{source}:{symbol}:{timeframe}:{int(df.time.iloc[0])}",
        {
            "source": source,
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": df.to_dict("records"),
        },
    )
    return clean(
        dict(
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            candles=df.to_dict("records"),
            has_more=len(df) == limit,
            last_closed=int(closed(df).end_time.iloc[-1]) if len(closed(df)) else None,
        )
    )


@app.get("/api/analysis/{symbol}")
async def analysis(symbol: str, timeframe: str = "5m"):
    check(symbol, timeframe)
    df, source = await service.candles(symbol, timeframe, 800)
    df = closed(df)
    if len(df) < 60:
        raise HTTPException(422, "Insufficient closed candles")
    d, events, zones = await run_in_threadpool(build, df)
    last = d.iloc[-1].to_dict()
    await run_in_threadpool(settle, df, symbol, source, timeframe)
    store.put(
        "indicator_values",
        f"{source}:{symbol}:{timeframe}",
        {"asof": int(df.end_time.iloc[-1]), "values": last},
    )
    store.put(
        "ict_signals",
        f"{source}:{symbol}:{timeframe}",
        {"events": events[-80:], "zones": zones},
    )
    windows = historical_sessions(df)
    events += session_sweeps(df, windows)
    events.sort(key=lambda e: e["time"])
    overlays = {
        k: [
            dict(time=int(t), value=float(v))
            for t, v in zip(d.time, d[k])
            if np.isfinite(v)
        ]
        for k in ["ema20", "ema50", "vwap", "bb_upper", "bb_lower", "supertrend"]
    }
    return clean(
        dict(
            symbol=symbol,
            source=source,
            timeframe=timeframe,
            asof=int(df.end_time.iloc[-1]),
            indicators=last,
            events=events[-80:],
            zones=zones,
            overlays=overlays,
            session_history=windows,
            sessions=sessions(
                display=store.get(
                    "settings", "display", {"timezone": settings.display_timezone}
                )["timezone"],
                df=df,
            ),
        )
    )


@app.get("/api/indicators/{symbol}")
async def indicator_route(symbol: str, timeframe: str = "5m"):
    return (await analysis(symbol, timeframe))["indicators"]


@app.get("/api/ict/{symbol}")
async def ict_route(symbol: str, timeframe: str = "5m"):
    a = await analysis(symbol, timeframe)
    return {k: a[k] for k in ["events", "zones", "asof", "source"]}


@app.get("/api/sessions")
async def session_route():
    return sessions(
        display=store.get(
            "settings", "display", {"timezone": settings.display_timezone}
        )["timezone"]
    )


@app.get("/api/predictions/{symbol}")
async def prediction(symbol: str, horizon: str = "1h"):
    check(symbol)
    if horizon not in HORIZONS:
        raise HTTPException(422, "Unknown horizon")
    tf, h = HORIZONS[horizon]
    df, source = await service.candles(symbol, tf, 1000)
    df = closed(df)
    if len(df) < 60:
        raise HTTPException(422, "Insufficient historical candles")
    await run_in_threadpool(settle, df, symbol, source, tf)
    return clean(await run_in_threadpool(make, df, symbol, tf, h, source, horizon))


@app.get("/api/predictions/{symbol}/{horizon}")
async def prediction_named(symbol: str, horizon: str):
    return await prediction(symbol, horizon)


class TrainRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    symbol: str = "BTCUSDT"
    horizon: str = "1h"
    history_bars: int = Field(3000, ge=800, le=20000)
    boosters: bool = False


async def training_job(job, body):
    async with training_lock:
        store.put("jobs", job, {"status": "running", "symbol": body.symbol})
        try:
            tf, h = HORIZONS[body.horizon]
            chunks = []
            before = None
            source = None
            for _ in range((body.history_bars + 999) // 1000):
                df, source = await service.candles(
                    body.symbol,
                    tf,
                    min(1000, body.history_bars - sum(len(c) for c in chunks)),
                    before,
                )
                chunks.insert(0, df)
                before = int(df.time.iloc[0])
                if len(df) < 100:
                    break
            import pandas as pd

            df = closed(
                pd.concat(chunks)
                .drop_duplicates("time")
                .sort_values("time")
                .reset_index(drop=True)
            )
            result = await run_in_threadpool(
                train, df, body.symbol, tf, h, source, body.boosters
            )
            store.put("jobs", job, {"status": "completed", "result": result})
        except Exception as exc:
            message = (
                str(exc)
                if isinstance(exc, (ValueError, ProviderError, ImportError))
                else "Training failed: " + type(exc).__name__
            )
            store.put("jobs", job, {"status": "failed", "error": message})


@app.post("/api/models/train", status_code=202)
async def start_training(body: TrainRequest, bg: BackgroundTasks):
    check(body.symbol)
    if body.horizon not in HORIZONS:
        raise HTTPException(422, "Horizon unsupported for training")
    if training_lock.locked():
        raise HTTPException(409, "Training already running")
    job = str(uuid.uuid4())
    store.put("jobs", job, {"status": "queued"})
    bg.add_task(training_job, job, body)
    return {"job_id": job}


@app.get("/api/jobs/{job}")
async def job_status(job: str):
    result = store.get("jobs", job)
    if result is None:
        raise HTTPException(404, "Unknown job")
    return result


@app.get("/api/models")
async def model_list():
    return store.records("model_versions")


@app.get("/api/history")
async def history(symbol: str | None = None, source: str | None = None):
    return store.history(symbol, source)


@app.get("/api/performance")
async def measured(
    symbol: str | None = None,
    source: str | None = None,
    model: str | None = None,
    regime: str | None = None,
    start: int | None = None,
    end: int | None = None,
    horizon: str | None = None,
):
    rows = store.history(
        symbol, source or ("demo" if settings.mock_mode else None), limit=10000
    )
    if not source and not settings.mock_mode:
        rows = [r for r in rows if r["source"] != "demo"]
    rows = [
        r
        for r in rows
        if (not model or r["model_version"] == model)
        and (not regime or r["regime"] == regime)
        and (start is None or r["asof"] >= start)
        and (end is None or r["asof"] <= end)
        and (not horizon or r["horizon"] == horizon)
    ]
    return performance(rows)


@app.get("/api/scanner")
async def scanner(
    market: str = "all",
    timeframe: str = "5m",
    direction: str = "all",
    min_probability: float = Query(0, ge=0, le=1),
    signal: str = "all",
):
    rows = []
    for symbol, asset in ASSETS.items():
        if market != "all" and asset[1] != market:
            continue
        try:
            df, source = await service.candles(symbol, timeframe, 800)
            d, events, zones = await run_in_threadpool(build, closed(df))
            last = d.iloc[-1]
            p = await run_in_threadpool(
                make, closed(df), symbol, timeframe, 1, source, "one_bar"
            )
            trend = "Bullish" if last.ema20 > last.ema50 else "Bearish"
            if direction != "all" and trend != direction:
                continue
            if min_probability and (p["probability"] or 0) < min_probability:
                continue
            recent = events[-30:]
            recent_kinds = [
                e["kind"]
                for e in recent
                if e["confirmed_at"] >= last.end_time - 5 * SECONDS[timeframe]
            ]
            if signal == "high_volatility" and "HIGH VOLATILITY" not in str(
                last.regime
            ):
                continue
            if signal == "sweep" and not any(
                "sweep" in k.lower() for k in recent_kinds
            ):
                continue
            if (
                signal not in ("all", "high_volatility", "sweep")
                and signal not in recent_kinds
            ):
                continue
            rows.append(
                clean(
                    dict(
                        symbol=symbol,
                        source=source,
                        status="ok",
                        price=last.close,
                        change=(
                            last.close
                            / d.close.iloc[
                                max(0, len(d) - int(86400 / SECONDS[timeframe]))
                            ]
                            - 1
                        )
                        * 100,
                        volume=closed(df)
                        .tail(max(1, int(86400 / SECONDS[timeframe])))
                        .volume.sum(min_count=1),
                        fvg=any(
                            z["kind"] == "FVG" and z["status"] == "active"
                            for z in zones
                        ),
                        liquidity_sweep=any("sweep" in k.lower() for k in recent_kinds),
                        prediction_status=p["validation_status"],
                        event_risk=(
                            "Unavailable without calendar key"
                            if not settings.calendar_api_key
                            else "See Economic Calendar"
                        ),
                        trend=trend,
                        volatility=last.volatility,
                        regime=last.regime,
                        rsi=last.rsi,
                        probability=p["probability"],
                        structure=events[-1]["kind"] if events else "No signal",
                        session=[r["name"] for r in sessions()["current"]],
                    )
                )
            )
        except ProviderError as exc:
            rows.append(dict(symbol=symbol, status="unavailable", message=str(exc)))
    return rows


class BacktestRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    symbol: str = "BTCUSDT"
    timeframe: str = "5m"
    strategy: Literal["ema", "smc", "rsi"] = "ema"
    bars: int = Field(1000, ge=100, le=1000)
    start: int | None = None
    end: int | None = None
    cost_bps: float = Field(5, ge=0, le=500)
    slippage_bps: float = Field(2, ge=0, le=500)
    risk_reward: float = Field(2, gt=0, le=20)
    stop_atr: float = Field(2, gt=0, le=10)
    risk_pct: float = Field(1, gt=0, le=5)
    spread_bps: float = Field(0, ge=0, le=500)
    sizing: Literal["risk", "fixed"] = "risk"
    fixed_units: float = Field(1, gt=0, le=1e9)


@app.post("/api/backtest")
async def backtest_route(body: BacktestRequest):
    check(body.symbol, body.timeframe)
    df, source = await service.candles(body.symbol, body.timeframe, body.bars, body.end)
    df = closed(df)
    if body.start:
        df = df[df.time >= body.start].reset_index(drop=True)
    if len(df) < 80:
        raise HTTPException(422, "Insufficient candles in selected date range")
    result = await run_in_threadpool(
        backtest,
        df,
        body.strategy,
        body.cost_bps,
        body.slippage_bps,
        body.risk_reward,
        body.stop_atr,
        body.risk_pct,
        body.spread_bps,
        body.sizing,
        body.fixed_units,
    )
    result["chronological"] = await run_in_threadpool(
        chronological_report,
        df,
        strategy=body.strategy,
        cost_bps=body.cost_bps,
        slippage_bps=body.slippage_bps,
        risk_reward=body.risk_reward,
        stop_atr=body.stop_atr,
        risk_pct=body.risk_pct,
        spread_bps=body.spread_bps,
        sizing=body.sizing,
        fixed_units=body.fixed_units,
    )
    result.update(
        source=source,
        symbol=body.symbol,
        start=int(df.time.iloc[0]),
        end=int(df.end_time.iloc[-1]),
        bars=len(df),
        strategy=body.strategy,
    )
    store.put("trades_backtest", str(uuid.uuid4()), result)
    return clean(result)


@app.get("/api/backtest")
async def default_backtest(symbol: str = "BTCUSDT", timeframe: str = "5m"):
    return await backtest_route(BacktestRequest(symbol=symbol, timeframe=timeframe))


@app.get("/api/watchlist")
async def watchlist():
    return store.get(
        "watchlists", "default", {"symbols": ["BTCUSDT", "ETHUSDT", "EURUSD"]}
    )


class Watchlist(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    symbols: list[str] = Field(max_length=30)


@app.put("/api/watchlist")
async def save_watchlist(body: Watchlist):
    for symbol in body.symbols:
        check(symbol)
    return store.put(
        "watchlists", "default", {"symbols": list(dict.fromkeys(body.symbols))}
    )


class Alert(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    symbol: str
    kind: Literal[
        "above",
        "below",
        "signal",
        "direction",
        "probability",
        "model",
        "session",
        "calendar",
    ]
    level: float = Field(0, ge=0)
    signal: Literal[
        "BOS",
        "CHoCH",
        "FVG",
        "Buy-side sweep",
        "Sell-side sweep",
        "MSS",
        "Session high sweep",
        "Session low sweep",
    ] = "BOS"
    repeat: bool = False
    cooldown_seconds: int = Field(300, ge=30, le=86400)
    delta: float = Field(0.1, gt=0, le=1)


@app.post("/api/alerts")
async def create_alert(body: Alert):
    check(body.symbol)
    _, source = service.provider(body.symbol)
    if body.kind in ("above", "below") and body.level <= 0:
        raise HTTPException(422, "Price must be positive")
    key = str(uuid.uuid4())
    row = dict(
        **body.model_dump(), source=source, created=int(time.time()), triggered=False
    )
    store.put("alert_rules", key, row)
    return dict(key=key, **row)


@app.get("/api/alerts")
async def alerts():
    return store.records("alert_rules")


@app.get("/api/notifications")
async def notifications():
    return store.records("notifications")[:100]


@app.delete("/api/alerts/{key}")
async def delete_alert(key: str):
    store.delete("alert_rules", key)
    return {"deleted": True}


@app.get("/api/news")
async def news_route():
    return await news()


@app.get("/api/correlations")
async def correlations(
    a: str = "BTCUSDT",
    b: str = "ETHUSDT",
    timeframe: str = "1h",
    window: int = Query(50, ge=20, le=200),
):
    check(a, timeframe)
    check(b, timeframe)
    da, sa = await service.candles(a, timeframe, window + 10)
    db, sb = await service.candles(b, timeframe, window + 10)
    if sa != sb:
        raise HTTPException(422, "Mixed-source correlation is disabled")
    return clean(
        dict(a=a, b=b, source=sa, **correlation(closed(da), closed(db), window))
    )


@app.websocket("/ws/market/{symbol}")
async def ws_market(ws: WebSocket, symbol: str, timeframe: str = "5m"):
    if not authorized(ws.headers, ws.cookies):
        await ws.close(code=4401)
        return
    if ws.headers.get("origin") and ws.headers[
        "origin"
    ] not in settings.cors_origins.split(","):
        await ws.close(code=4403)
        return
    await ws.accept()
    try:
        check(symbol, timeframe)
        provider, source = service.provider(symbol)
        async for event in provider.stream(symbol, timeframe):
            service.record_tick(symbol, event)
            await ws.send_json(clean(event))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json(
                {
                    "type": "status",
                    "status": "unavailable",
                    "message": (
                        str(exc)
                        if isinstance(exc, ProviderError)
                        else type(exc).__name__
                    ),
                }
            )
            await ws.close()
        except Exception:
            pass


# Serve the compiled application from the same origin in packaged/local production mode.
from fastapi.staticfiles import StaticFiles
from app.core.config import ROOT

if (ROOT / "frontend" / "dist" / "index.html").is_file():
    app.mount(
        "/",
        StaticFiles(directory=ROOT / "frontend" / "dist", html=True),
        name="terminal",
    )
