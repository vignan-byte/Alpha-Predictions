# Architecture

The shared launcher starts the compiled React/Vite preview; it serves the browser locally on 5173. Its `/api`, `/health` and `/ws` proxies connect to FastAPI on 8000. Credentials are read only in the backend. The browser never calls a credentialed provider directly.

A common provider interface separates synthetic data, Binance public spot REST/WebSocket and Twelve Data forex REST/WebSocket. REST histories are cached with per-key async locks. Independent chart sockets reconnect with backoff. The demo series is indexed by timestamps, so requesting older history does not change already closed bars.

Closed candles flow through technical indicators, confirmed ICT/SMC features and feature generation. The model pipeline uses explicit future labels only during training. Inference calls a versioned model whose training history cannot extend beyond the forecast origin. Predictions are immutable by source/symbol/horizon/as-of/model-version key.

FastAPI routes orchestrate CPU operations through a thread pool. Model training is serialized; UI polls a persistent job document. A background collector monitors watchlisted symbols every minute, generates supported intraday predictions and settles available outcomes. Session, daily and long-horizon analyses are refreshed on request. The worker is local/in-process, not a distributed durable queue.

SQLite persists a normalized prediction table and a typed JSON document table. Document kinds contain watchlists, settings, alerts, model versions, jobs, candle snapshots, indicator snapshots, ICT signals and backtest results. Alembic revision `0001` creates the original schema; `0002` adds transactional paper account books and append-only audit events without dropping existing data. This reduces schema complexity while preserving separate prediction identity and settlement records. PostgreSQL needs an installed driver and an explicitly configured SQLAlchemy URL.

Default network binding is 127.0.0.1. Optional API_TOKEN login protects API and WebSocket access using signed cookies or Bearer tokens. Origin checks and rate limits provide additional local controls. Paper order routes are virtual only; there is no brokerage or real-order adapter.

A ten-second background worker marks paper positions from fresh source-specific quotes and checks virtual brackets. Calendar/news adapters cache attributed provider responses, with explicit missing-key/error/stale states. Native chart primitives attach filled zones to the existing candlestick series and recompute screen coordinates on redraw.
