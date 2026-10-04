async def collector():
    # Watchlisted assets only, 60-second cycle; caches constrain REST usage.
    while True:
        for symbol in store.get(
            "watchlists",
            "default",
            {"symbols": ["BTCUSDT", "ETHUSDT", "EURUSD"]},
        )["symbols"]:
            try:
                df, source = await service.candles(symbol, "5m", 800)
                closed = df[df.end_time <= time.time()]

                if len(closed) < 60:
                    continue

                d, events, _ = await run_in_threadpool(
                    build,
                    closed,
                )

                events += session_sweeps(
                    closed,
                    historical_sessions(closed),
                )

                forecast = await run_in_threadpool(
                    make,
                    closed,
                    symbol,
                    "5m",
                    12,
                    source,
                    "1h",
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

                await run_in_threadpool(
                    settle,
                    closed,
                    symbol,
                    source,
                    "5m",
                )

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
                            "error": str(exc),
                        }
                    )
                )

        await asyncio.sleep(60)