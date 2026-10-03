"""Optional NewsAPI headlines. Sentiment and impact are intentionally unscored."""

import time
from app.core.config import settings
from app.data.providers import get_json, ProviderError
from app.database import store

_cache = None


async def news():
    global _cache
    if not settings.news_api_key:
        return dict(
            status="blocked",
            message="News feed unavailable: configure NEWS_API_KEY for NewsAPI.",
            source="NewsAPI",
            items=[],
        )
    failed = None
    if _cache is None or time.time() - _cache["fetched_at"] > 300:
        try:
            data = await get_json(
                "https://newsapi.org/v2/everything",
                {
                    "q": "forex OR bitcoin OR central bank",
                    "sortBy": "publishedAt",
                    "pageSize": 20,
                    "apiKey": settings.news_api_key,
                },
            )
            if data.get("status") != "ok":
                raise ProviderError(
                    "News provider rejected the request; check key and plan"
                )
            items = []
            for r in data.get("articles", []):
                title = r.get("title") or ""
                related = [
                    asset
                    for term, asset in [
                        ("bitcoin", "BTC"),
                        ("ethereum", "ETH"),
                        ("dollar", "USD"),
                        ("euro", "EUR"),
                        ("yen", "JPY"),
                        ("sterling", "GBP"),
                    ]
                    if term in title.lower()
                ]
                items.append(
                    dict(
                        title=title,
                        url=r.get("url"),
                        published_at=r.get("publishedAt"),
                        source=r.get("source", {}).get("name"),
                        related_assets=related,
                        related_asset_method="Headline keyword match",
                        sentiment=None,
                        impact=None,
                    )
                )
            _cache = dict(items=items, fetched_at=time.time())
            store.put("news", "cache", _cache)
        except ProviderError as exc:
            failed = str(exc)
            _cache = _cache or store.get("news", "cache")
            if _cache is None:
                return dict(status="error", message=failed, source="NewsAPI", items=[])
    return dict(
        **_cache,
        status="stale" if failed else "live",
        message=failed,
        source="NewsAPI",
        note="No reliable sentiment or event-impact classification supplied by this feed."
    )
