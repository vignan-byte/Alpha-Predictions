# Data sources and provenance

## Binance spot

Public-data-only endpoint: `https://data-api.binance.vision/api/v3`.
REST klines map open timestamps, OHLC, base volume and close timestamps into seconds. Binance's inclusive millisecond close time is converted to an exclusive second boundary. The chart socket uses `wss://data-stream.binance.vision/ws/{symbol}@kline_{interval}`. A separate REST ticker supplies 24h change, high/low, volume and bid/ask. Public feeds need no API key; regional access can vary.

Official reference: https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
Streaming reference: https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md

## Twelve Data forex

REST: `https://api.twelvedata.com/time_series`, with UTC timestamps, explicit interval, ascending order and optional historical end date. Price WebSocket: `wss://ws.twelvedata.com/v1/quotes/price`. Subscribe to the slash-separated pair; send heartbeat messages on receive timeout. Your subscription must allow requested symbols and streaming access. Missing forex volume remains null, not zero. REST history polling is slower than price ticks and reconciles candles. A disconnected or stale stream is surfaced.

Official reference: https://twelvedata.com/docs

## Demo provider

Synthetic, timestamp-indexed trigonometric prices around arbitrary base values. This is deliberately reproducible software demonstration data, not a market simulation suitable for estimating real performance. Every response, forecast identity, model version and visible quote identifies demo provenance. Monthly candles use calendar month boundaries. No demo provider is invoked automatically after a live error.

## News

Optional NewsAPI.org market headlines with source URLs and publication timestamps. No configured key means “News feed unavailable.” Headlines are not a structured economic calendar. Reference: https://newsapi.org/docs/endpoints/everything

## Validation

Reject empty data, nonpositive/non-numeric prices and malformed OHLC bounds. Sort and deduplicate timestamps. Training labels spanning missing candles are discarded. The app does not reconstruct missing historical trades or assume missing volume is available. Model inference suppresses stale-candle forecasts. Historical snapshots are retained in the document store; they are not a fully fledged market-data warehouse.

## Economic calendar

Trading Economics `/calendar?c=...&f=json` supplies structured releases. Source dates are normalized to UTC and rendered in the chosen timezone. Five-minute cache; stale cached results are explicitly labeled after failure. No credentials were supplied for live verification. Official schema reference: https://docs.tradingeconomics.com/economic_calendar/snapshot/
