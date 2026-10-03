from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    mock_mode: bool = False
    forex_api_key: str = ""
    crypto_api_key: str = ""
    crypto_api_secret: str = ""
    news_api_key: str = ""
    calendar_api_key: str = ""
    api_token: str = ""
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
    )
    rate_limit_per_minute: int = 2400
    signal_min_directional_probability: float = 0.55
    signal_min_margin: float = 0.08
    signal_min_expected_atr_multiple: float = 0.15
    signal_min_rr: float = 2.0
    signal_cost_bps: float = 8.0
    display_timezone: str = "Asia/Kolkata"
    database_url: str = ""
    crypto_rest_url: str = "https://data-api.binance.vision"
    crypto_ws_url: str = "wss://data-stream.binance.vision/ws"
    model_config = SettingsConfigDict(
        env_file=ROOT / "backend" / ".env", extra="ignore"
    )


settings = Settings()
(ROOT / "data").mkdir(exist_ok=True)
