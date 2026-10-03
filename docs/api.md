# API

The executable OpenAPI schema at http://localhost:8000/docs is authoritative. Symbols in paths omit slashes, e.g. BTCUSDT or EURUSD.

| Method / route | Purpose |
|---|---|
| GET /health | Database check, configured engine state, demo/live mode |
| GET /api/markets | Supported instrument catalog and source availability |
| GET /api/markets/{symbol} | Quote and available market statistics |
| GET /api/candles/{symbol} | timeframe, limit (30–1000), optional exclusive `before` Unix seconds |
| GET /api/analysis/{symbol} | Closed-candle indicators, structure, zones, overlays, sessions |
| GET /api/indicators/{symbol} | Last indicator values |
| GET /api/ict/{symbol} | Structure events and zones |
| GET /api/sessions | DST-aware sessions |
| GET /api/predictions/{symbol} | `horizon=5m,15m,30m,1h,session,day,week,month,year` |
| GET /api/predictions/{symbol}/{horizon} | Named horizon alias |
| POST /api/models/train | symbol, horizon, history_bars, optional boosters; returns job_id |
| GET /api/jobs/{id} | Queued/running/completed/failed state |
| GET /api/models | Version registry and measured validation/test metadata |
| GET /api/history | Optional symbol/source filters |
| GET /api/performance | Optional symbol/source/model/regime/start/end/horizon filters |
| GET /api/scanner | market/timeframe/direction/min_probability filters |
| POST /api/backtest | Validated strategy and cost inputs, actual simulation results |
| GET /api/backtest | Default simulation convenience endpoint |
| GET/PUT /api/watchlist | Persistent symbol list |
| GET/POST /api/alerts | Persistent one-shot rules |
| DELETE /api/alerts/{key} | Delete local alert |
| GET/PUT /api/settings | Safe settings and timezone preference; no secret values |
| GET /api/news | Optional authentic source-linked headlines |
| GET /api/correlations | a, b, timeframe, window; aligned return correlation |
| WS /ws/market/{symbol}?timeframe=5m | Candle/price/status events |

Example training body:

```json
{"symbol":"BTCUSDT","horizon":"1h","history_bars":3000,"boosters":false}
```

Example backtest body:

```json
{"symbol":"BTCUSDT","timeframe":"5m","strategy":"ema","bars":1000,"cost_bps":5,"slippage_bps":2,"risk_reward":2,"stop_atr":2,"risk_pct":1}
```

Provider failures return 503 with a safe explicit reason, unknown symbols 404, invalid inputs 422 and busy training 409. Credentials are excluded from responses. WebSockets emit reconnecting/unavailable events rather than forged prices.

## Release 2.1 additions

All `/api/` endpoints except auth status/login require the configured Bearer token or signed cookie when `API_TOKEN` is set. `/health` remains public. API models reject non-finite numeric input. OpenAPI `/docs` is the authoritative current request schema.

| Method / path | Purpose |
|---|---|
| GET `/api/auth/status` | Whether login is enabled and the caller authenticated |
| POST `/api/auth/login`, `/api/auth/logout` | Session cookie lifecycle |
| GET `/api/provider-status` | Source, freshness and external configuration availability |
| GET `/api/calendar?impact=high&currency=USD` | Trading Economics calendar with timezone/filter/cache states |
| GET `/api/sessions/{symbol}/history` | Historical civil-session statistics and sweeps |
| GET `/api/correlations/matrix?symbols=BTCUSDT,ETHUSDT&window=50` | Aligned return matrix and relationship diagnostics |
| GET/PUT `/api/paper/account` | Inspect account or configure initial virtual balance |
| GET `/api/paper/quote/{symbol}` | Source-qualified timestamped quote |
| POST `/api/paper/preview` | Persist expiring market-order preview, no position yet |
| POST `/api/paper/confirm` | Explicit `confirm:true`, preview ID and matching symbol |
| POST `/api/paper/positions/{id}/close` | Explicit `confirm:true` and matching symbol |
| GET `/api/audit` | Recent paper-operation audit records |
| GET `/api/notifications` | Persistent alert delivery events |

Alert kinds now include direction, probability, model, session and calendar, with optional repeat/cooldown/delta. Backtests accept `spread_bps`, `sizing` (`risk`/`fixed`) and `fixed_units`, and return chronological evaluation summaries. Next-session prediction/training is a separate `session` target.
