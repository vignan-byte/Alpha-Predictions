# 2.2 — Prediction + UX refinement

- Upgraded the causal feature schema from causal-v2 to causal-v3 with additional momentum, trend alignment, level-distance, range-position and volume/price context features.
- Expanded classifier candidates with Extra Trees and HistGradientBoosting and strengthened Random Forest settings.
- Added validation-only Neutral/abstention decision-rule learning so weak probability separation is not presented as a strong directional signal.
- Added balanced-accuracy reporting and preserved chronological, purged holdout evaluation.
- Added automatic recovery from stale active-model pointers when a compatible promoted model exists.
- Simplified the primary navigation to Dashboard, Chart, Predictions, Backtesting and Prediction History.
- Simplified chart layer controls and made 15m the default prediction horizon.
- Added explicit low-confidence UI messaging.
- No accuracy is fabricated or guaranteed; final performance must be established by fresh real-data training and untouched out-of-sample evaluation.

# 2.1 FINAL

Continues the existing 2.0 project; no application rewrite.

- Native filled chart zones, current OTE/liquidity, mitigation/transition annotations, historical session shading and validated forecast-range overlay.
- Persistent atomic virtual accounts: expiring previews, explicit confirmation, long/short brackets, mark/close accounting, equity and audited performance.
- Separate real-provider calendar and news screens with cache, source attribution and honest missing-key states.
- Correlation matrix and deterministic relationship diagnostics; scanner filters and additional context.
- Independent next-session target, extended model metrics and visible validation status; no forced promotion.
- Backtest spread and fixed-unit options plus research/holdout/forward-window reports.
- Repeating and transition alerts with cooldown/de-duplication; browser/sound opt-in.
- Optional token login, signed cookies, API/WebSocket origin and access checks, bounded requests.
- Non-destructive paper/audit migration; immutable forecast and document first-write concurrency fixes.
- Cross-platform readiness/port checks and compiled preview launcher; browser test process cleanup fixed.
- Updated documentation, tests, release evidence and a checksummed source distribution.
