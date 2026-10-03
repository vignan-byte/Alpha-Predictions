"""Provider errors never cause silent substitution of synthetic data."""

import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
import httpx
import numpy as np
import pandas as pd
import websockets
from app.core.config import settings

ASSETS = {
    "BTCUSDT": ("BTC/USDT", "crypto", 65000),
    "ETHUSDT": ("ETH/USDT", "crypto", 3200),
    "SOLUSDT": ("SOL/USDT", "crypto", 145),
    "XRPUSDT": ("XRP/USDT", "crypto", 0.6),
    "EURUSD": ("EUR/USD", "forex", 1.09),
    "GBPUSD": ("GBP/USD", "forex", 1.28),
    "USDJPY": ("USD/JPY", "forex", 150),
    "AUDUSD": ("AUD/USD", "forex", 0.67),
    "USDCAD": ("USD/CAD", "forex", 1.36),
    "USDCHF": ("USD/CHF", "forex", 0.88),
}
SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
    "1M": 2592000,
}
TD = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1day",
    "1w": "1week",
    "1M": "1month",
}


class ProviderError(Exception):
    pass


def validate(df):
    if df.empty:
        raise ProviderError("No candles returned")
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[["open", "high", "low", "close"]].isna().any().any():
        raise ProviderError("Invalid candle prices")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise ProviderError("Nonpositive prices")
    if (
        (df.high < df[["open", "close"]].max(axis=1))
        | (df.low > df[["open", "close"]].min(axis=1))
        | (df.high < df.low)
    ).any():
        raise ProviderError("Malformed OHLC candle")
    return df


def parse_binance(rows):
    return validate(
        pd.DataFrame(
            [
                dict(
                    time=int(r[0]) // 1000,
                    open=r[1],
                    high=r[2],
                    low=r[3],
                    close=r[4],
                    volume=r[5],
                    end_time=int(r[6]) // 1000 + 1,
                )
                for r in rows
            ]
        )
    )


def parse_kline(event):
    k = event["k"]
    return dict(
        time=int(k["t"]) // 1000,
        open=float(k["o"]),
        high=float(k["h"]),
        low=float(k["l"]),
        close=float(k["c"]),
        volume=float(k["v"]),
        end_time=int(k["T"]) // 1000 + 1,
        closed=bool(k["x"]),
    )


class MarketDataProvider(ABC):
    @abstractmethod
    async def candles(self, symbol, tf, limit=800, before=None): ...
    @abstractmethod
    async def stream(self, symbol, tf):
        yield {}


class MockProvider(MarketDataProvider):
    """Timestamp-indexed synthetic prices: closed history stays identical across calls."""

    async def candles(self, symbol, tf, limit=800, before=None):
        sec = SECONDS[tf]
        now = int(time.time())
        last = min(now, before - 1) if before else now
        if tf == "1M":
            stamp = pd.Timestamp(last, unit="s", tz="UTC").normalize().replace(day=1)
            t = (
                pd.date_range(end=stamp, periods=limit, freq="MS")
                .astype("int64")
                .to_numpy()
                // 10**9
            )
            ends = (
                pd.to_datetime(t, unit="s", utc=True) + pd.offsets.MonthBegin(1)
            ).astype("int64").to_numpy() // 10**9
        else:
            t = (
                np.arange(last // sec - limit + 1, last // sec + 1, dtype=np.int64)
                * sec
            )
            ends = t + sec
        seed = int(hashlib.sha256(symbol.encode()).hexdigest()[:6], 16)
        base = ASSETS[symbol][2]
        scale = 0.015 if ASSETS[symbol][1] == "crypto" else 0.002

        def price(ts):
            x = (ts - 1700000000) / 3600
            return base * np.exp(
                scale
                * (
                    np.sin(x / 9 + seed)
                    + 0.7 * np.sin(x / 2.7 + seed / 3)
                    + 0.4 * np.sin(x / 0.37)
                )
            )

        o = price(t)
        c = price(np.minimum(ends, now))
        spread = base * scale * 0.08 * (1 + np.abs(np.sin(t + seed)))
        return validate(
            pd.DataFrame(
                dict(
                    time=t,
                    open=o,
                    high=np.maximum(o, c) + spread,
                    low=np.minimum(o, c) - spread,
                    close=c,
                    volume=100 + 90 * np.abs(np.sin(t / 71 + seed)),
                    end_time=ends,
                )
            )
        )

    async def stream(self, symbol, tf):
        while True:
            d = await self.candles(symbol, tf, 2)
            yield {
                "type": "candle",
                "candle": d.iloc[-1].to_dict(),
                "source": "demo",
                "status": "demo",
                "timestamp": int(time.time()),
            }
            await asyncio.sleep(2)


async def get_json(url, params):
    async with httpx.AsyncClient(timeout=15) as client:
        for attempt in range(3):
            try:
                response = await client.get(url, params=params)
                if response.status_code in (429, 503):
                    if attempt < 2:
                        await asyncio.sleep(min(2**attempt, 4))
                        continue
                    raise ProviderError(
                        "Provider rate limit or service unavailable; retry later"
                    )
                if response.status_code >= 400:
                    raise ProviderError(f"Provider HTTP {response.status_code}")
                data = response.json()
                if isinstance(data, dict) and data.get("status") == "error":
                    raise ProviderError(
                        f"Provider rejected request (code {data.get('code','unknown')}); check plan, symbol and credentials"
                    )
                return data
            except (httpx.HTTPError, ValueError) as exc:
                if attempt == 2:
                    raise ProviderError(
                        f"Provider connection failed ({type(exc).__name__})"
                    ) from None
                await asyncio.sleep(2**attempt)


class CryptoProvider(MarketDataProvider):
    async def candles(self, symbol, tf, limit=800, before=None):
        params = dict(symbol=symbol, interval=tf, limit=min(limit, 1000))
        if before:
            params["endTime"] = before * 1000 - 1
        return parse_binance(
            await get_json(settings.crypto_rest_url + "/api/v3/klines", params)
        )

    async def quote(self, symbol):
        q, b = await asyncio.gather(
            get_json(
                settings.crypto_rest_url + "/api/v3/ticker/24hr", {"symbol": symbol}
            ),
            get_json(
                settings.crypto_rest_url + "/api/v3/ticker/bookTicker",
                {"symbol": symbol},
            ),
        )
        return dict(
            price=float(q["lastPrice"]),
            change=float(q["priceChangePercent"]),
            high=float(q["highPrice"]),
            low=float(q["lowPrice"]),
            volume=float(q["volume"]),
            bid=float(b["bidPrice"]),
            ask=float(b["askPrice"]),
            timestamp=int(q["closeTime"]) // 1000,
            statistics_window="24h",
        )

    async def stream(self, symbol, tf):
        delay = 1
        while True:
            try:
                async with websockets.connect(
                    f"{settings.crypto_ws_url}/{symbol.lower()}@kline_{tf}",
                    ping_interval=20,
                    ping_timeout=20,
                    open_timeout=15,
                ) as ws:
                    delay = 1
                    async for raw in ws:
                        evt = json.loads(raw)
                        if "k" in evt:
                            yield dict(
                                type="candle",
                                candle=parse_kline(evt),
                                source="binance",
                                status="live",
                                timestamp=int(evt["E"]) // 1000,
                            )
            except (OSError, TimeoutError, websockets.WebSocketException):
                yield {
                    "type": "status",
                    "status": "reconnecting",
                    "message": "Crypto stream disconnected",
                    "source": "binance",
                }
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)


class ForexProvider(MarketDataProvider):
    async def candles(self, symbol, tf, limit=800, before=None):
        if not settings.forex_api_key:
            raise ProviderError("Forex unavailable: set FOREX_API_KEY in backend/.env")
        p = dict(
            symbol=ASSETS[symbol][0],
            interval=TD[tf],
            outputsize=min(limit, 5000),
            apikey=settings.forex_api_key,
            timezone="UTC",
            order="asc",
        )
        if before:
            p["end_date"] = pd.Timestamp(before - 1, unit="s", tz="UTC").strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        data = await get_json("https://api.twelvedata.com/time_series", p)
        rows = []
        for r in data.get("values", []):
            stamp = pd.Timestamp(r["datetime"], tz="UTC")
            end = (
                stamp + pd.offsets.MonthBegin(1)
                if tf == "1M"
                else stamp + pd.Timedelta(seconds=SECONDS[tf])
            )
            rows.append(
                dict(
                    time=int(stamp.timestamp()),
                    end_time=int(end.timestamp()),
                    **{
                        k: r.get(k, np.nan)
                        for k in ["open", "high", "low", "close", "volume"]
                    },
                )
            )
        return validate(pd.DataFrame(rows))

    async def websocket_stream(self, symbol, tf):
        if not settings.forex_api_key:
            raise ProviderError("Forex API key missing")
        delay = 1
        while True:
            try:
                async with websockets.connect(
                    "wss://ws.twelvedata.com/v1/quotes/price?apikey="
                    + settings.forex_api_key,
                    open_timeout=15,
                ) as ws:
                    await ws.send(
                        json.dumps(
                            {
                                "action": "subscribe",
                                "params": {"symbols": ASSETS[symbol][0]},
                            }
                        )
                    )
                    delay = 1
                    while True:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), 10)
                        except asyncio.TimeoutError:
                            await ws.send(json.dumps({"action": "heartbeat"}))
                            continue
                        evt = json.loads(raw)
                        if evt.get("event") == "price":
                            yield {
                                "type": "price",
                                "price": float(evt["price"]),
                                "timestamp": int(evt["timestamp"]),
                                "source": "twelvedata",
                                "status": "live",
                            }
                        elif (
                            evt.get("event") == "subscribe-status"
                            and evt.get("status") == "error"
                        ):
                            yield {
                                "type": "status",
                                "status": "unavailable",
                                "message": "Forex streaming subscription denied; check plan",
                            }
            except (OSError, TimeoutError, websockets.WebSocketException):
                yield {
                    "type": "status",
                    "status": "reconnecting",
                    "message": "Forex stream disconnected; REST candles remain available",
                }
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def stream(self, symbol, tf):
        if not settings.forex_api_key:
            raise ProviderError("Forex API key missing")
        while True:
            generator = self.websocket_stream(symbol, tf)
            try:
                while True:
                    event = await asyncio.wait_for(anext(generator), 25)
                    if event.get("status") in ("unavailable", "reconnecting"):
                        break
                    yield event
            except (TimeoutError, ProviderError, StopAsyncIteration):
                pass
            finally:
                await generator.aclose()
            yield dict(
                type="status",
                status="connecting",
                source="twelvedata",
                transport="rest",
                message="Streaming unavailable; using real REST polling",
            )
            for _ in range(5):
                try:
                    df = await self.candles(symbol, tf, 2)
                    bar = df.iloc[-1].to_dict()
                    state = (
                        "stale"
                        if time.time() - bar["time"] > SECONDS[tf] * 2
                        else "live"
                    )
                    yield dict(
                        type="candle",
                        candle=bar,
                        source="twelvedata",
                        status=state,
                        transport="rest",
                        timestamp=int(bar["time"]),
                    )
                except ProviderError as exc:
                    yield dict(
                        type="status",
                        status="error",
                        source="twelvedata",
                        transport="rest",
                        message=str(exc),
                    )
                await asyncio.sleep(45)


class DataService:
    def __init__(self):
        self.cache = {}
        self.locks = {}
        self.ticks = {}
        self.status = {}

    def provider(self, symbol):
        if symbol not in ASSETS:
            raise ProviderError("Unsupported symbol")
        if settings.mock_mode:
            return MockProvider(), "demo"
        return (
            (CryptoProvider(), "binance")
            if ASSETS[symbol][1] == "crypto"
            else (ForexProvider(), "twelvedata")
        )

    async def candles(self, symbol, tf, limit=800, before=None):
        if tf not in SECONDS:
            raise ProviderError("Unsupported timeframe")
        provider, source = self.provider(symbol)
        key = (source, symbol, tf, limit, before)
        ttl = 2 if source == "demo" else (45 if source == "twelvedata" else 10)
        async with self.locks.setdefault(key, asyncio.Lock()):
            cached = self.cache.get(key)
            if cached and time.time() - cached[0] < ttl:
                return cached[1].copy(), source
            df = await provider.candles(symbol, tf, limit, before)
            if len(self.cache) > 150:
                self.cache.clear()
            self.cache[key] = (time.time(), df)
            return df.copy(), source

    def record_tick(self, symbol, event):
        if event.get("type") in ("candle", "price"):
            price = event.get("price") or event["candle"]["close"]
            self.ticks[symbol] = dict(
                price=float(price),
                timestamp=int(event["timestamp"]),
                source=event["source"],
                status=event["status"],
                transport=event.get("transport", "websocket"),
            )
        self.status[symbol] = dict(
            status=event.get("status", "connecting"),
            source=event.get("source"),
            observed_at=int(time.time()),
        )

    async def snapshot(self, symbol):
        provider, source = self.provider(symbol)
        tick = self.ticks.get(symbol)
        if tick and tick["source"] == source and time.time() - tick["timestamp"] < 15:
            return dict(tick)
        if isinstance(provider, CryptoProvider):
            q = await provider.quote(symbol)
        else:
            df = await provider.candles(symbol, "1m", 2)
            r = df.iloc[-1]
            q = dict(
                price=float(r.close),
                timestamp=int(time.time()) if source == "demo" else int(r.time),
            )
        q.update(
            source=source,
            status=(
                "demo"
                if source == "demo"
                else ("live" if time.time() - q["timestamp"] <= 120 else "stale")
            ),
            transport="rest",
        )
        self.ticks[symbol] = q
        self.status[symbol] = dict(
            status=q["status"], source=source, observed_at=int(time.time())
        )
        return q


service = DataService()
