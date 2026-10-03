import asyncio
import hmac
import time
from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from app.core.config import settings
from app.core.security import authorized, issue_cookie, COOKIE
from app.core.utils import clean
from app.data.providers import service, ASSETS, ProviderError
from app.database import store
from app.paper import engine as paper
from app.calendar.provider import calendar
from app.sessions.engine import historical_sessions, session_sweeps
from app.correlations.engine import matrix

router = APIRouter()


class Input(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")


class Login(Input):
    token: str = Field(min_length=1, max_length=1000)


@router.get("/api/auth/status")
async def auth_status(request: Request):
    return {
        "enabled": bool(settings.api_token),
        "authenticated": authorized(request.headers, request.cookies),
    }


@router.post("/api/auth/login")
async def login(body: Login, response: Response, request: Request):
    if settings.api_token and not hmac.compare_digest(body.token, settings.api_token):
        raise HTTPException(401, "Invalid access token")
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"
    response.set_cookie(
        COOKIE,
        issue_cookie(),
        httponly=True,
        samesite="strict",
        max_age=43200,
        secure=secure,
    )
    return {"authenticated": True}


@router.post("/api/auth/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"authenticated": False}


@router.get("/api/calendar")
async def calendar_route(
    impact: Literal["low", "medium", "high"] | None = None, currency: str | None = None
):
    display = store.get("settings", "display", {"timezone": settings.display_timezone})[
        "timezone"
    ]
    return await calendar.fetch(display, impact, currency)


@router.get("/api/sessions/{symbol}/history")
async def session_history(symbol: str, timeframe: str = "5m"):
    df, source = await service.candles(symbol, timeframe, 1000)
    df = df[df.end_time <= time.time()]
    windows = historical_sessions(df)
    return dict(source=source, windows=windows, sweeps=session_sweeps(df, windows))


@router.get("/api/provider-status")
async def provider_status():
    states = {
        k: dict(
            v, status="stale" if time.time() - v["observed_at"] > 120 else v["status"]
        )
        for k, v in service.status.items()
    }
    return dict(
        mode="demo" if settings.mock_mode else "live",
        instruments=states,
        forex="configured" if settings.forex_api_key else "blocked: key required",
        calendar="configured" if settings.calendar_api_key else "blocked: key required",
        news="configured" if settings.news_api_key else "blocked: key required",
        real_execution=False,
    )


def paper_source(symbol):
    if symbol not in ASSETS:
        raise HTTPException(404, "Unsupported symbol")
    if ASSETS[symbol][1] not in ("crypto", "forex"):
        raise HTTPException(
            422, "Paper orders supported for configured crypto and forex pairs only"
        )
    return service.provider(symbol)[1]


class PaperConfig(Input):
    symbol: str = "BTCUSDT"
    balance: float = Field(10000, ge=100, le=1e9)


@router.put("/api/paper/account")
async def paper_config(body: PaperConfig):
    return clean(
        await run_in_threadpool(
            paper.configure,
            paper_source(body.symbol),
            paper.currency(body.symbol),
            body.balance,
        )
    )


@router.get("/api/paper/account")
async def paper_account(symbol: str = "BTCUSDT"):
    source = paper_source(symbol)
    result = await run_in_threadpool(paper.snapshot, source, paper.currency(symbol))
    return clean(result)


class PaperPreview(Input):
    symbol: str = "BTCUSDT"
    side: Literal[1, -1] = 1
    units: float = Field(0.01, gt=0, le=1e9)
    risk_pct: float | None = Field(None, gt=0, le=5)
    stop: float = Field(gt=0)
    target: float = Field(gt=0)
    fee_bps: float = Field(5, ge=0, le=100)
    slippage_bps: float = Field(2, ge=0, le=100)


@router.post("/api/paper/preview")
async def paper_preview(body: PaperPreview):
    source = paper_source(body.symbol)
    q = await service.snapshot(body.symbol)
    return clean(
        await run_in_threadpool(
            paper.preview,
            source,
            body.symbol,
            q["price"],
            q["timestamp"],
            body.side,
            body.units,
            body.stop,
            body.target,
            body.fee_bps,
            body.slippage_bps,
            body.risk_pct,
        )
    )


class PaperConfirm(Input):
    symbol: str
    preview_id: str
    confirm: Literal[True]


@router.post("/api/paper/confirm")
async def paper_confirm(body: PaperConfirm):
    source = paper_source(body.symbol)
    order = await run_in_threadpool(
        paper.order_lookup, source, paper.currency(body.symbol), body.preview_id
    )
    if order["symbol"] != body.symbol:
        raise HTTPException(422, "Preview symbol mismatch")
    q = await service.snapshot(body.symbol)
    return clean(
        await run_in_threadpool(
            paper.confirm,
            source,
            paper.currency(body.symbol),
            body.preview_id,
            q["price"],
            q["timestamp"],
        )
    )


class PaperClose(Input):
    symbol: str
    confirm: Literal[True]


@router.post("/api/paper/positions/{position_id}/close")
async def paper_close(position_id: str, body: PaperClose):
    source = paper_source(body.symbol)
    account = await run_in_threadpool(
        paper.snapshot, source, paper.currency(body.symbol)
    )
    position = next(
        (p for p in account["positions"] + account["trades"] if p["id"] == position_id),
        None,
    )
    if not position or position["symbol"] != body.symbol:
        raise HTTPException(404, "Paper position not found for this symbol")
    q = await service.snapshot(body.symbol)
    return clean(
        await run_in_threadpool(
            paper.close,
            source,
            paper.currency(body.symbol),
            position_id,
            q["price"],
            q["timestamp"],
        )
    )


@router.get("/api/paper/quote/{symbol}")
async def paper_quote(symbol: str):
    paper_source(symbol)
    return clean(await service.snapshot(symbol))


@router.get("/api/audit")
async def audit_events():
    import json

    with store.Session() as s:
        return [
            dict(
                id=r.id, created=r.created, action=r.action, data=json.loads(r.payload)
            )
            for r in s.scalars(
                select(paper.AuditEvent).order_by(paper.AuditEvent.id.desc()).limit(100)
            )
        ]


@router.get("/api/correlations/matrix")
async def correlation_matrix(
    symbols: str = "BTCUSDT,ETHUSDT,SOLUSDT",
    timeframe: str = "1h",
    window: int = Query(50, ge=20, le=200),
):
    names = list(dict.fromkeys(symbols.split(",")))
    if len(names) > 8:
        raise HTTPException(422, "Select at most 8 instruments")
    data = {}
    sources = {}
    errors = {}
    for symbol in names:
        try:
            d, src = await service.candles(symbol, timeframe, window + 40)
            data[symbol] = d[d.end_time <= time.time()]
            sources[symbol] = src
        except ProviderError as exc:
            errors[symbol] = str(exc)
    return clean(dict(**matrix(data, window), sources=sources, errors=errors))


async def paper_worker():
    while True:
        for source, symbol in await run_in_threadpool(paper.open_symbols):
            try:
                if service.provider(symbol)[1] != source:
                    continue
                q = await service.snapshot(symbol)
                await run_in_threadpool(
                    paper.mark, source, symbol, q["price"], q["timestamp"]
                )
            except ProviderError:
                service.status[symbol] = dict(
                    status="error", source=source, observed_at=int(time.time())
                )
            except Exception:
                import logging

                logging.getLogger("alpha").error("paper_worker_operation_failed")
        await asyncio.sleep(10)
