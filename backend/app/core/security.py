import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from app.core.config import settings

COOKIE = "alpha_session"


def issue_cookie():
    body = f"{int(time.time())+43200}.{secrets.token_hex(16)}"
    return (
        body
        + "."
        + hmac.new(
            settings.api_token.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
    )


def valid_cookie(value):
    if not settings.api_token:
        return True
    try:
        expiry, nonce, signature = value.split(".")
        body = expiry + "." + nonce
        expected = hmac.new(
            settings.api_token.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        return int(expiry) > time.time() and hmac.compare_digest(signature, expected)
    except (ValueError, AttributeError):
        return False


def authorized(headers, cookies):
    if not settings.api_token:
        return True
    bearer = headers.get("authorization", "")
    return (
        bearer.startswith("Bearer ")
        and hmac.compare_digest(bearer[7:], settings.api_token)
    ) or valid_cookie(cookies.get(COOKIE))


class RateLimiter:
    def __init__(self):
        self.buckets = defaultdict(deque)

    def allow(self, key, limit, now=None):
        now = time.monotonic() if now is None else now
        if len(self.buckets) > 10000:
            self.buckets.clear()
        q = self.buckets[key]
        while q and q[0] <= now - 60:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


limiter = RateLimiter()
