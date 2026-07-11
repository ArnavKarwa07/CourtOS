from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COURTOS_")

    mode: str = "simulation"
    db_backend: str = "sqlite"
    db_url: str = "./data/courtos.db"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    sim_interval: float = 1.0

    decel_warn: float = 5.0
    decel_crit: float = 9.0
    velocity_warn: float = 12.0
    velocity_crit: float = 18.0
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_requests_per_minute: int = 15
