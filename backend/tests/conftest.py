import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["MOCK_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp()) / "test.db")
import pytest
from app.database.store import init_db


@pytest.fixture(scope="session", autouse=True)
def database():
    init_db()


@pytest.fixture
def candles():
    import asyncio
    from app.data.providers import MockProvider

    return (
        asyncio.run(MockProvider().candles("BTCUSDT", "5m", 1200))
        .iloc[:-1]
        .reset_index(drop=True)
    )
