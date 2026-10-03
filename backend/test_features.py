import asyncio
from app.data.providers import service
from app.features.engine import build, FEATURES

async def main():
    df, src = await service.candles("BTCUSDT", "15m", 1000)

    print("SOURCE:", src)
    print("CANDLES:", len(df))

    d, _, _ = build(df)
    x = d[FEATURES]

    print("FEATURE ROWS:", len(x))
    print("FEATURES:", len(FEATURES))
    print("FINITE VALUES:", int(x.notna().sum().sum()), "/", x.size)
    print("ROWS WITH ALL FEATURES:", int(x.notna().all(axis=1).sum()))
    print("LAST ROW COMPLETE:", bool(x.iloc[-1].notna().all()))

asyncio.run(main())
