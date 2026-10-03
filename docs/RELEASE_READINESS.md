# AlphaPredictorsAI 2.2.0 — Release Readiness

## Release posture

AlphaPredictorsAI 2.2 is a production-oriented **market-intelligence and quantitative research platform**. It is intentionally not an autonomous real-money trading system.

The release separates:

1. **Model direction** — the calibrated ML classifier's raw directional estimate.
2. **Trading signal** — a deterministic policy layer that can return `LONG`, `SHORT`, or `NO-TRADE`.
3. **Risk levels** — entry, stop loss, take profit and R:R derived from current market context.

A weak model probability is therefore not presented as a trade recommendation. The default signal policy requires directional probability, probability separation and expected-return gates to pass simultaneously. Otherwise the platform explicitly abstains.

## Validation gates

A model is eligible for promotion only after chronological train/calibration/validation/test evaluation, leakage-safe feature construction, probability calibration and baseline comparison. Test data is not used to select the winning candidate.

Do not change the test set after inspecting results and do not advertise a win rate that is not supported by a sufficiently large untouched out-of-sample sample.

## Operational safety

- LIVE mode never silently falls back to synthetic data.
- DEMO mode is visibly labelled as synthetic.
- Real-money execution is disabled.
- Paper trading uses a separate virtual ledger.
- API authentication is optional for localhost development; set a long random `API_TOKEN` for any exposed deployment.
- Cookies become `Secure` automatically behind HTTPS / `X-Forwarded-Proto: https`.
- Security response headers are enabled.
- Liveness and readiness endpoints are available at `/health/live` and `/health/ready`.

## Deployment

### Windows

```powershell
.\setup.bat
.\run.bat
```

### Docker

```bash
docker compose up --build -d
```

Before any public deployment, set `API_TOKEN`, configure an explicit `CORS_ORIGINS` allow-list, provision persistent storage, and place the service behind HTTPS/reverse proxy infrastructure.

## Final verification commands

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
cd frontend
npm ci
npm test -- --run
npm run build
cd ..
```

The project archive must not contain `.venv`, `node_modules`, generated `dist`, SQLite runtime databases, logs, or trained model binaries. These are environment/runtime artifacts and should be generated or provisioned during deployment.
