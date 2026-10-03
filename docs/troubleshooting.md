# Troubleshooting and operational notes

Run setup before startup. Node dependencies live in frontend/node_modules; Python dependencies live in .venv. Both directories are intentionally absent from the ZIP and are installed automatically. Runtime databases and test-generated models are not shipped.

If PowerShell policies prevent execution of a downloaded script, review the script first and use the supplied .bat wrapper, which sets execution policy only for its launched process. Managed organizational policies may still override it. Setup preserves an existing .env.

For failure diagnostics, first open the backend console, then `/health`, then the affected API route in `/docs`. Logs contain event names, request paths, latency and error types. HTTP client debug logs are disabled so URL API keys are not printed. Provider errors intentionally omit request URLs.

News and forex subscription plans may limit requests. The data service caches recent responses and retries temporary HTTP 429/503 failures. Scanning all forex symbols or training many thousands of rows consumes plan credits. WebSockets reconnect with capped backoff. UI status distinguishes connection, stale feed and unavailable data.

Training can finish without promotion; this is a valid result. Inspect validation log loss versus the baseline. A model is not promoted because its training accuracy is large. Incumbent comparison requires genuinely later data; immediately pressing retrain on the same history will not satisfy that requirement.

Session predictions require their own validated model. The economic calendar requires a Trading Economics key/plan. Gold/index/DXY/yield instruments are not configured. No frontend action invents provider data or bypasses model validation.

For database backup, stop the backend before copying `data/alpha.db`. Preserve models/trained and models/metadata together with the database so active-version references remain valid. Only restore trusted local model artifacts.
