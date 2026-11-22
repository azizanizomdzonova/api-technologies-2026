import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import grpc
import httpx
import redis.asyncio as redis
from fastapi import BackgroundTasks, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import settings
from .grpc_clients import UpstreamTimeoutError, UpstreamUnavailableError
from .orchestrator import evaluate_transaction_flow
from .schemas import (
    ErrorResponse,
    HealthResponse,
    TransactionRequest,
    TransactionVerdictResponse,
)

logger = logging.getLogger("gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=True,
        socket_timeout=settings.redis_timeout_sec,
        socket_connect_timeout=settings.redis_timeout_sec,
    )
    app.state.ml_channel = grpc.aio.insecure_channel(settings.ml_grpc_addr)
    app.state.decision_channel = grpc.aio.insecure_channel(settings.decision_grpc_addr)
    app.state.http_client = httpx.AsyncClient(
        base_url=settings.updater_url,
        timeout=settings.updater_timeout_sec,
    )
    logger.info("Gateway clients initialized")

    yield

    await app.state.redis.aclose()
    await app.state.ml_channel.close()
    await app.state.decision_channel.close()
    await app.state.http_client.aclose()
    logger.info("Gateway clients closed")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()

    if any(err.get("type") == "json_invalid" for err in errors):
        payload = ErrorResponse(
            code="BAD_REQUEST",
            message="Некорректный синтаксис JSON в теле запроса",
        )
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=payload.model_dump())

    invalid_fields = ", ".join(
        ".".join(str(part) for part in err.get("loc", []) if part != "body")
        for err in errors
    )
    payload = ErrorResponse(
        code="VALIDATION_ERROR",
        message=f"Ошибка валидации полей: {invalid_fields or 'некорректные данные'}",
    )
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload.model_dump())


@app.exception_handler(UpstreamTimeoutError)
async def upstream_timeout_handler(request: Request, exc: UpstreamTimeoutError) -> JSONResponse:
    payload = ErrorResponse(
        code="UPSTREAM_TIMEOUT",
        message=str(exc),
    )
    return JSONResponse(status_code=status.HTTP_504_GATEWAY_TIMEOUT, content=payload.model_dump())


@app.exception_handler(UpstreamUnavailableError)
async def upstream_unavailable_handler(request: Request, exc: UpstreamUnavailableError) -> JSONResponse:
    payload = ErrorResponse(
        code="UPSTREAM_UNAVAILABLE",
        message=str(exc),
    )
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled internal error: %s", exc)
    payload = ErrorResponse(
        code="INTERNAL_ERROR",
        message="Внутренняя ошибка сервиса",
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload.model_dump())


async def notify_updater(http_client: httpx.AsyncClient, tx: TransactionRequest, verdict: int) -> None:
    """Фоновая отправка прошедшей транзакции в сервис обновления агрегатов (не влияет на SLA 100 мс)."""
    body = {
        "transaction_id": tx.transaction_id,
        "account_id": tx.account_id,
        "amount": tx.amount,
        "timestamp": tx.timestamp.isoformat(),
        "verdict": verdict,
    }
    try:
        response = await http_client.post("/v1/aggregates/update", json=body)
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Failed to notify updater for tx=%s: %s", tx.transaction_id, exc)


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["System"],
)
async def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post(
    "/v1/transactions/evaluate",
    response_model=TransactionVerdictResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    tags=["Transactions"],
)
async def evaluate_transaction(
    tx: TransactionRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> TransactionVerdictResponse:
    score, verdict = await evaluate_transaction_flow(
        tx=tx,
        redis_client=request.app.state.redis,
        ml_channel=request.app.state.ml_channel,
        decision_channel=request.app.state.decision_channel,
    )

    background_tasks.add_task(
        notify_updater,
        request.app.state.http_client,
        tx,
        int(verdict),
    )

    return TransactionVerdictResponse(
        transaction_id=tx.transaction_id,
        score=score,
        verdict=verdict,
        evaluated_at=datetime.now(timezone.utc),
    )