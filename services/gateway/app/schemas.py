from datetime import datetime
from enum import IntEnum
from pydantic import BaseModel, Field


class VerdictEnum(IntEnum):
    APPROVED = 0
    FRAUD = 1


class TransactionRequest(BaseModel):
    transaction_id: str = Field(..., min_length=1, description="Уникальный ID транзакции из АБС")
    account_id: str = Field(..., min_length=1, description="Идентификатор счёта клиента")
    amount: float = Field(..., gt=0.0, description="Сумма транзакции (строго больше 0.0)")
    currency: str = Field(default="RUB", min_length=1, description="Валюта операции")
    timestamp: datetime = Field(..., description="Время совершения транзакции в формате ISO-8601")

    # Опциональные поля для обогащения признаков из Redis (geo_risk, merchant_risk)
    client_id: str | None = Field(default=None, description="Идентификатор клиента")
    region: str | None = Field(default=None, description="Регион совершения операции")
    merchant_id: str | None = Field(default=None, description="Идентификатор мерчанта")


class TransactionVerdictResponse(BaseModel):
    transaction_id: str = Field(..., description="ID транзакции из АБС")
    score: float = Field(..., ge=0.0, le=1.0, description="Вероятность мошенничества от ML-модели (0..1)")
    verdict: VerdictEnum = Field(..., description="Итоговый вердикт: 0 — одобрено, 1 — фрод")
    evaluated_at: datetime = Field(..., description="Время вынесения вердикта (UTC)")


class ErrorResponse(BaseModel):
    code: str = Field(..., description="Машиночитаемый код ошибки")
    message: str = Field(..., description="Описание ошибки")


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Состояние сервиса")