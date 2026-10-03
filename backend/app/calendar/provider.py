"""Trading Economics calendar, separate from headlines. Never synthesizes events."""

import asyncio
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.core.config import settings
from app.data.providers import get_json, ProviderError
from app.database import store

COUNTRY_CURRENCY = {
    "United States": "USD",
    "United Kingdom": "GBP",
    "Euro Area": "EUR",
    "Germany": "EUR",
    "France": "EUR",
    "Italy": "EUR",
    "Japan": "JPY",
    "Australia": "AUD",
    "Canada": "CAD",
    "Switzerland": "CHF",
    "New Zealand": "NZD",
    "China": "CNY",
    "India": "INR",
}


def normalize(row):
    stamp = datetime.fromisoformat(str(row["Date"]).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    actual = row.get("Actual")
    actual = None if actual in (None, "") else actual
    return dict(
        id=str(
            row.get(
                "CalendarId",
                f"{row.get('Country')}:{row.get('Event')}:{stamp.isoformat()}",
            )
        ),
        name=row["Event"],
        timestamp=int(stamp.timestamp()),
        currency=row.get("Currency")
        or COUNTRY_CURRENCY.get(row.get("Country"), "Unknown"),
        country=row.get("Country"),
        impact={1: "low", 2: "medium", 3: "high"}.get(
            int(row.get("Importance") or 0), "unknown"
        ),
        forecast=None if row.get("Forecast") in (None, "") else row.get("Forecast"),
        previous=None if row.get("Previous") in (None, "") else row.get("Previous"),
        actual=actual,
        source=row.get("Source") or "Trading Economics",
        source_url=row.get("SourceURL") or None,
        provider="Trading Economics",
        status="released" if actual is not None else "scheduled",
        tentative=bool(row.get("DateSpan") not in (None, 0, "0")),
    )


class CalendarProvider:
    def __init__(self):
        self.cache = None
        self.lock = asyncio.Lock()

    async def fetch(self, display="Asia/Kolkata", impact=None, currency=None):
        tz = ZoneInfo(display)
        if not settings.calendar_api_key:
            return dict(
                status="blocked",
                message="Economic calendar unavailable: set CALENDAR_API_KEY to a Trading Economics key with calendar access.",
                source="Trading Economics",
                events=[],
                timezone=display,
            )
        async with self.lock:
            failed = None
            if self.cache is None or time.time() - self.cache["fetched_at"] > 300:
                try:
                    raw = await get_json(
                        "https://api.tradingeconomics.com/calendar",
                        {"c": settings.calendar_api_key, "f": "json"},
                    )
                    if not isinstance(raw, list):
                        raise ProviderError(
                            "Calendar provider returned an unexpected response; check access plan"
                        )
                    parsed = []
                    for row in raw:
                        try:
                            parsed.append(normalize(row))
                        except (ValueError, KeyError, TypeError):
                            continue
                    if raw and not parsed:
                        raise ProviderError("Calendar event schema could not be parsed")
                    self.cache = {"events": parsed, "fetched_at": time.time()}
                    store.put("events", "calendar", self.cache)
                except ProviderError as exc:
                    failed = str(exc)
                    if self.cache is None:
                        self.cache = store.get("events", "calendar")
                    if self.cache is None:
                        return dict(
                            status="error",
                            message=failed,
                            source="Trading Economics",
                            events=[],
                            timezone=display,
                        )
            events = [
                dict(
                    e,
                    local_time=datetime.fromtimestamp(e["timestamp"], timezone.utc)
                    .astimezone(tz)
                    .isoformat(),
                    seconds_until=e["timestamp"] - int(time.time()),
                )
                for e in self.cache["events"]
                if (not impact or e["impact"] == impact)
                and (not currency or e["currency"] == currency)
            ]
            return dict(
                status="stale" if failed else "live",
                message=failed,
                source="Trading Economics",
                fetched_at=self.cache["fetched_at"],
                events=sorted(events, key=lambda e: e["timestamp"]),
                timezone=display,
            )


calendar = CalendarProvider()
