# Final release scope — 2.1

PASS means the delivered behavior was exercised in this environment. PARTIAL means an implemented capability has a stated coverage limit. BLOCKED means an external verification dependency is absent. Detailed commands and counts are in `validation_report.md`.

| Feature | Status | Verified behavior / limitation |
|---|---|---|
| Backend / frontend | PASS | API and unit suites, strict TypeScript compilation, production bundle and component tests |
| Live Binance | PASS | Public REST, real WebSocket → chart → closed-candle analysis → prediction gate; browser reconnect |
| Forex | PARTIAL | Six-pair Twelve Data history/stream/real REST fallback implemented and adapter-tested; live key/plan absent |
| Charts / ICT-SMC | PASS | Nine timeframes, candles/volume/history, native filled zones, causal structure and session markers, pan/zoom |
| Sessions | PASS | DST-aware civil sessions, Asia/Kolkata display, historical ranges and confirmed sweeps; holidays excluded |
| Predictions | PASS | Independent model identities for nine horizons, estimate/context display and range overlay; no probability without validation |
| ML validation | PASS | Chronological splits, embargo, calibration, baseline/incumbent gate and held-out metrics; latest live model rejected |
| Backtesting | PASS | Fixed strategies, fees/slippage/spread, risk/unit sizing, brackets, equity, drawdown and chronological holdout windows |
| Paper trading | PASS | Atomic preview/confirmation, long/short, quote guards, SL/TP, closing, accounting, persistence and audit |
| Economic calendar | BLOCKED | Trading Economics adapter, cache/failure handling, fields, timezone and filters locally tested; no key/plan for live verification |
| News | BLOCKED | NewsAPI source-linked headlines, cache/failure handling and asset-keyword labels implemented; live key absent |
| Correlation | PARTIAL | Configured crypto/forex pair matrix, rolling return comparison and deterministic SMT descriptors; no licensed gold/index/DXY/yield adapter |
| Alerts | PASS | Local price/structure/prediction/model/session/calendar rules, cooldown/de-dup, browser/sound opt-in; calendar feed itself requires a key |
| Security | PASS | Optional login/token/cookie, API/WS rejection, origin controls, validation and rate-limit tests |
| SQLite | PASS | Fresh initialization, existing-data-preserving migration, prediction/paper/audit persistence |
| PostgreSQL | BLOCKED | Driver requirements, SQLAlchemy/Alembic and account locking implemented; no server provisioned for runtime test |
| Windows setup/run | PARTIAL | Quoted batch/PowerShell wrappers reviewed; shared launcher and compiled default-port workflow tested on Linux; no native Windows runner |
| Optional boosters | PARTIAL | Opt-in dependency/candidate support; default logistic/random-forest pipeline tested; optional booster environments not certified |
| Real broker execution | PASS | Off by design; no real-order integration |

Further limits: local single-user deployment; no public hosting/SLA, multi-user roles, exchange microstructure, funding/borrow, limit orders, partial exits or external messaging channels. Model explanations describe observed used features and validation importance, not causal attribution. Historical breaker/inverse-FVG areas are marked historical. No guaranteed accuracy, calibrated range coverage or profitability is claimed.
