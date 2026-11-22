import logging

import grpc

from .config import settings
from .generated import ml_service_pb2, ml_service_pb2_grpc
from .schemas import VerdictEnum

logger = logging.getLogger("gateway.grpc")


class UpstreamTimeoutError(Exception):
    """Внутренний gRPC-сервис не уложился в таймаут (маппится в HTTP 504)."""


class UpstreamUnavailableError(Exception):
    """Внутренний gRPC-сервис недоступен или вернул ошибку (маппится в HTTP 503)."""


async def call_ml_service(
    channel: grpc.aio.Channel,
    transaction_id: str,
    client_id: str,
    features: dict[str, float | int],
) -> float:
    """Асинхронный gRPC-вызов ML-сервиса с жёстким таймаутом."""
    stub = ml_service_pb2_grpc.MLServiceStub(channel)
    request = ml_service_pb2.InferenceRequest(
        transaction_id=transaction_id,
        client_id=client_id,
        features=ml_service_pb2.InferenceFeatures(
            amount=float(features["amount"]),
            avg_amount_30d=float(features["avg_amount_30d"]),
            tx_count_24h=int(features["tx_count_24h"]),
            geo_risk=float(features["geo_risk"]),
            merchant_risk=float(features["merchant_risk"]),
            hour=int(features["hour"]),
        ),
    )

    try:
        response = await stub.CheckTransaction(
            request,
            timeout=settings.ml_timeout_sec,
        )
        return float(response.score)
    except grpc.aio.AioRpcError as exc:
        if exc.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
            logger.error("ML gRPC timeout for tx=%s", transaction_id)
            raise UpstreamTimeoutError("Превышен таймаут ожидания ML-сервиса") from exc
        logger.error("ML gRPC error for tx=%s: %s (%s)", transaction_id, exc.code().name, exc.details())
        raise UpstreamUnavailableError(f"ML-сервис недоступен ({exc.code().name})") from exc


async def call_decision_service(
    channel: grpc.aio.Channel,
    transaction_id: str,
    score: float,
) -> VerdictEnum:
    """
    Вызов сервиса «Решение» по gRPC.
    Пока в репозитории нет decision.proto от Компонента 5, используется локальный порог (score >= 0.5).
    Как только появится decision.proto — заменить тело функции на вызов DecisionServiceStub
    с timeout=settings.decision_timeout_sec по аналогии с call_ml_service.
    """
    _ = (channel, transaction_id)
    return VerdictEnum.FRAUD if score >= 0.5 else VerdictEnum.APPROVED