# Security and operating boundary

AlphaPredictorsAI binds to loopback and is intended for a single trusted local user. Optional `API_TOKEN` protects `/api/` and market WebSockets. Login accepts the server token and issues a signed 12-hour HttpOnly/SameSite=strict cookie. Cookie expiry, tampering, invalid tokens, unauthorized HTTP/WebSocket access and cross-origin mutations are covered by automated tests. Logout removes the local cookie; rotating the token revokes all signed cookies. Bearer authentication supports local API tools.

`CORS_ORIGINS` controls allowed browser origins. Mutating requests with another Origin are rejected. Credentials are supported only for explicit origins. WebSockets use the same origin and authentication checks. In-memory request limits default to 2,400 per minute per direct client IP, with five login attempts per minute. Rate limits are process-local and are not a distributed public-API abuse system.

Environment variables contain credentials; no keys are embedded into the frontend. Logs contain method/path/status/duration and exception types, not request bodies or credentialed provider URLs. Provider errors are redacted, and unexpected exceptions return a generic error. API numeric inputs reject non-finite values. Paper actions have append-only audit records.

The local cookie does not use Secure because the default server is HTTP localhost. A public deployment would need HTTPS, Secure cookies, trustworthy proxy handling, network restrictions, operational monitoring and a separate multi-user authorization design. Those are outside this local release. Public hosting was not performed.

All execution is virtual. No account, order placement, withdrawal or autonomous broker integration exists. Installed model files are trusted local Python artifacts; do not load untrusted joblib/pickle files. Distribution packaging excludes `.env`, databases, caches and trained binary artifacts.
