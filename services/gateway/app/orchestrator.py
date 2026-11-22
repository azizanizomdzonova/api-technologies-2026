from datetime import timezone

import grpc
import redis.asyncio as redis

from .grpc_clients import call_decision_service, call_ml_service
from .redis_client import fetch_features
from .schemas import TransactionRequest, VerdictEnum


def _extract_utc_hour(tx: TransactionRequest) -> int:
    ts = tx.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).hour


async def evaluate_transaction_flow(
    tx: TransactionRequest,
    redis_client: redis.Redis,
    ml_channel: grpc.aio.Channel,
    decision_channel: grpc.aio.Channel,
) -> tuple[float, VerdictEnum]:
    """
    Полный синхронный конвейер оценки транзакции:
    1) Чтение 4 признаков из Redis за 1 pipeline
    2) Сборка вектора из 6 признаков (добавляем amount и hour в UTC)
    3) gRPC-вызов ML-сервиса -> score
    4) gRPC-вызов сервиса «Решение» -> verdict (0/1)
    """
    redis_features = await fetch_features(
        redis_client=redis_client,
        account_id=tx.account_id,
        region=tx.region,
        merchant_id=tx.merchant_id,
    )

    features: dict[str, float | int] = {
        "amount": tx.amount,
        "avg_amount_30d": redis_features.avg_amount_30d,
        "tx_count_24h": redis_features.tx_count_24h,
        "geo_risk": redis_features.geo_risk,
        "merchant_risk": redis_features.merchant_risk,
        "hour": _extract_utc_hour(tx),
    }

    # В proto3 нельзя передавать None в string-поле — подставляем account_id как запасной ID
    client_id = tx.client_id or tx.account_id

    score = await call_ml_service(
        channel=ml_channel,
        transaction_id=tx.transaction_id,
        client_id=client_id,
        features=features,
    )
    # Гарантируем попадание в диапазон [0.0, 1.0] для строгого контракта ответа
    score = max(0.0, min(1.0, score))

    verdict = await call_decision_service(
        channel=decision_channel,
        transaction_id=tx.transaction_id,
        score=score,
    )

    return score, verdict