# AlphaPredictorsAI — Verification 2026-10-03

## Current execution evidence

| Area | Result | Evidence |
|---|---|---|
| Python compilation | PASS | `python -m compileall -q backend scripts` |
| Backend automated tests | PASS | **62 passed / 62 total** |
| Extracted release integrity | PASS | ZIP CRC, path safety, manifest hashes |
| Extracted backend smoke | PASS | health, migrations, paper lifecycle, unvalidated-model gate |
| Frontend unit tests/build | NOT VERIFIED HERE | The supplied archive contained Windows `node_modules`; clean `npm ci` could not complete in this execution environment because package-registry access did not complete |
| Docker build/compose | NOT VERIFIED HERE | Docker CLI is not installed in this execution environment |
| Native Windows setup | NOT VERIFIED HERE | No native Windows runner is available |
| Live Binance API from this runner | NOT VERIFIED | Application correctly returned HTTP 503 when the provider was unreachable; it did **not** substitute synthetic data |
| ML 70% gate | PASS AS A SAFETY RULE | Existing validation gate rejects models that do not genuinely pass; no fabricated 70% metric is used |

## Important interpretation

This report deliberately does **not** call the project “100% verified.” The repository contains substantial working functionality, and the backend/release smoke tests pass, but frontend, Docker, native Windows, and live-provider execution cannot all be independently re-executed in this environment.

The project therefore prefers an explicit `NOT VERIFIED`/provider-unavailable state over a false success claim.
