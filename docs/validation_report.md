# Validation report — AlphaPredictorsAI 2.2.0

Verified 2 October 2026 (UTC). Environment: Linux, Python 3.12, Node 24, Chromium 134 / Playwright 1.51. All final reported commands completed successfully. Native Windows execution is not claimed.

## Final counts

| Check | Status | Final result |
|---|---|---|
| Complete backend suite | PASS | **58 passed / 58 total; 0 failed** |
| Frontend tests | PASS | **9 passed / 9 total; 0 failed** |
| TypeScript and Vite production build | PASS | Strict type-check and compiled production assets |
| Main browser workflow | PASS | 19 checks |
| New modules and authenticated workflow | PASS | 16 checks |
| Compiled launcher workflow | PASS | 4 checks |
| Real Binance browser pipeline | PASS | 7 checks |
| Total browser checks | PASS | **46 passed / 46 total; 0 failed** |
| SQLite initialization/migration | PASS | Fresh schema and 0001→0002 preservation tests |
| Extracted ZIP verification | PASS | See `zip-verification.json`; hash/CRC and extracted startup/paper smoke |

A Starlette TestClient/httpx deprecation warning remains in the test runner; it does not fail a test. Provider and browser evidence uses actual successful results, not inferred connectivity.

## Feature status

| Feature | Status | Evidence / boundary |
|---|---|---|
| Backend | PASS | Imports, health, validation, persistence and 58 automated cases |
| Frontend | PASS | 9 tests, TypeScript, production build, desktop/mobile browser checks |
| Binance live data | PASS | REST, 18 received candle frames in the final live run, displayed prices, canvas redraw, closed-candle analysis and socket reconnection |
| Forex | PARTIAL | Adapter and real-REST fallback tests pass; external key/plan required for live verification |
| Paper trading | PASS | Preview without fill, explicit confirm, idempotent concurrent fill, long/short SL/TP, close, costs, equity/P&L reconciliation and reload persistence |
| ICT/SMC / sessions | PASS | Causal features/events, filled zones and pan/zoom, structure markers, historical session ranges, incomplete-window rejection and DST |
| Predictions | PASS | Nine independent horizon identities, no fabricated probability, valid demo range overlay and source isolation |
| ML validation | PASS | Real Binance training ran; model remained REJECTED; separate calibration/validation/test and disjoint metrics |
| Backtesting | PASS | Fees/slippage/spread, risk/fixed units, brackets, trade/equity/drawdown and chronological holdout/forward windows |
| Economic calendar | BLOCKED | Adapter/schema/cache/filter/timezone/failure tests pass; Trading Economics credentials/access plan absent |
| News | BLOCKED | Source-attributed optional adapter and blocked UI; NewsAPI key absent for live verification |
| Correlation | PARTIAL | Configured instrument matrix/diagnostics pass; no licensed macro index/gold/DXY/yield adapter |
| Alerts | PASS | Price, structure, prediction/model, session/calendar rules; cooldown/de-dup; browser/sound controls and background price trigger |
| Security | PASS | Valid/invalid/expired/tampered auth, HTTP/WS rejection, origin checks, rate limiting and finite inputs |
| Windows setup | PARTIAL | Wrappers statically reviewed; their shared launcher and compiled default-port workflow executed on Linux; no native Windows runner |
| PostgreSQL | BLOCKED | Driver/config/migrations and locking code provided; no server supplied for execution |
| Real execution | PASS | Disabled; only virtual order APIs |
| Final ZIP | PASS | Required files, excluded secrets/dependencies/runtime data, integrity and manifest verification |

## Actual real-data ML result

The controlled BTCUSDT one-hour model used about 3,000 Binance five-minute bars. Candidate selection and promotion used validation, never the test set.

- Selected candidate: **random_forest**.
- Validation log loss: **0.874116**.
- Validation class-prior baseline log loss: **0.847532**; lower is better.
- Held-out accuracy: **46.94% on 49 non-overlapping origins**.
- Held-out log loss: **0.887234**.
- Macro precision / recall / F1: **0.1565 / 0.3333 / 0.2130**.
- **REJECTED** because validation did not beat the baseline. No live probability was enabled.

This small sample does not establish an edge, reliability or profitability. Synthetic demo/session runs demonstrate software behavior only. No pretrained live model, guaranteed accuracy or forced promotion is shipped.

## Resolved verification issues

- Fixed the correlation-table JSX closure before successful TypeScript/build checks.
- Fixed browser test process cleanup and readiness checks so old servers cannot be silently reused.
- Reconnection testing now closes only the market socket, leaving Vite's unrelated development socket alone.
- Live canvas verification checks redraws as well as pixel changes: unchanged market quotes can legitimately produce identical pixels. UI prices must still match received Binance frames.
- Added concurrent first-write protection for immutable forecasts and document records, with regression coverage.
- Corrected London/NY overlap completeness to reject missing bars before emitting session-range sweeps.

## Evidence and reproducibility

`backend-test-results.txt`, `frontend-test-results.txt`, `frontend-build-results.txt`, `final-regression.json`, `final-browser-regression.json`, the four browser JSON reports and their result logs contain the final outcomes. `live-training-validation.json` includes the real data hash, partitions and complete metrics. `session-training-validation.json` is explicitly synthetic next-session training. Screenshots include the final compiled dashboard, chart zones, forecast range and paper workflow.

The ZIP includes source, built assets, setup/run scripts, configuration templates, migrations, tests and documentation. Credentials, runtime SQLite data, dependencies, caches and trained binary artifacts are excluded. See `scope.md`, `security.md` and the README for operating boundaries.
