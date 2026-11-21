import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Antifraud Gateway")
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))

    redis_host: str = os.getenv("REDIS_HOST", "redis")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_timeout_sec: float = float(os.getenv("REDIS_TIMEOUT_SEC", "0.02"))

    ml_grpc_addr: str = os.getenv("ML_GRPC_ADDR", "ml-grpc:50051")
    ml_timeout_sec: float = float(os.getenv("ML_TIMEOUT_SEC", "0.05"))

    decision_grpc_addr: str = os.getenv("DECISION_GRPC_ADDR", "decision-grpc:50052")
    decision_timeout_sec: float = float(os.getenv("DECISION_TIMEOUT_SEC", "0.03"))

    updater_url: str = os.getenv("UPDATER_URL", "http://updater:8002")
    updater_timeout_sec: float = float(os.getenv("UPDATER_TIMEOUT_SEC", "1.0"))

    default_avg_amount_30d: float = float(os.getenv("DEFAULT_AVG_AMOUNT_30D", "0.0"))
    default_tx_count_24h: int = int(os.getenv("DEFAULT_TX_COUNT_24H", "0"))
    default_geo_risk: float = float(os.getenv("DEFAULT_GEO_RISK", "0.0"))
    default_merchant_risk: float = float(os.getenv("DEFAULT_MERCHANT_RISK", "0.0"))


settings = Settings()