import logging
from dataclasses import dataclass

import redis.asyncio as redis

from .config import settings

logger = logging.getLogger("gateway.redis")


@dataclass(frozen=True)
class RedisFeatures:
    avg_amount_30d: float
    tx_count_24h: int
    geo_risk: float
    merchant_risk: float


def _to_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


async def fetch_features(
    redis_client: redis.Redis,
    account_id: str,
    region: str | None = None,
    merchant_id: str | None = None,
) -> RedisFeatures:
    """
    Забирает 4 признака из Redis за один сетевой поход (pipeline).
    При отсутствии ключей (Cache Miss) или сбое Redis возвращает безопасные дефолты.
    """
    defaults = RedisFeatures(
        avg_amount_30d=settings.default_avg_amount_30d,
        tx_count_24h=settings.default_tx_count_24h,
        geo_risk=settings.default_geo_risk,
        merchant_risk=settings.default_merchant_risk,
    )

    try:
        async with redis_client.pipeline(transaction=False) as pipe:
            # Агрегаты счёта (формат Hash согласован с updater.py сокомандника)
            pipe.hmget(
                f"account:{account_id}:aggregates",
                "avg_amount_30d",
                "tx_count_24h",
            )
            if region:
                pipe.get(f"region:{region}:risk")
            if merchant_id:
                pipe.get(f"merchant:{merchant_id}:risk")

            results = await pipe.execute()
    except Exception as exc:
        logger.warning("Redis fetch failed for account=%s, using defaults: %s", account_id, exc)
        return defaults

    aggregates = results[0] or [None, None]
    avg_amount_30d = _to_float(aggregates[0], settings.default_avg_amount_30d)
    tx_count_24h = _to_int(aggregates[1], settings.default_tx_count_24h)

    idx = 1
    geo_risk = settings.default_geo_risk
    if region:
        geo_risk = _to_float(results[idx], settings.default_geo_risk)
        idx += 1

    merchant_risk = settings.default_merchant_risk
    if merchant_id:
        merchant_risk = _to_float(results[idx], settings.default_merchant_risk)

    return RedisFeatures(
        avg_amount_30d=avg_amount_30d,
        tx_count_24h=tx_count_24h,
        geo_risk=geo_risk,
        merchant_risk=merchant_risk,
    )