from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .db import load_transactions
from .redis_storage import save_aggregates


def to_datetime(value):
    """Приводит дату к UTC."""

    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def calculate_account_aggregates(transactions, as_of_time):
    """Рассчитывает среднюю сумму за 30 дней и количество операций за 24 часа."""

    start_30d = as_of_time - timedelta(days=30)
    start_24h = as_of_time - timedelta(hours=24)

    history = [
        tx for tx in transactions
        if start_30d <= to_datetime(tx["timestamp"]) < as_of_time
    ]

    if not history:
        return None

    avg_amount_30d = (
        sum(float(tx["amount"]) for tx in history) / len(history)
    )

    tx_count_24h = sum(
        1 for tx in history
        if start_24h <= to_datetime(tx["timestamp"]) < as_of_time
    )

    return {
        "avg_amount_30d": avg_amount_30d,
        "tx_count_24h": tx_count_24h
    }


def refresh_redis_from_database():
    """Получает транзакции, рассчитывает агрегаты и сохраняет их в Redis."""

    as_of_time = datetime.now(timezone.utc)

    transactions = load_transactions()

    accounts = defaultdict(list)

    for tx in transactions:
        accounts[str(tx["account_id"])].append(tx)

    for account_id, account_transactions in accounts.items():

        aggregates = calculate_account_aggregates(
            account_transactions,
            as_of_time
        )

        if aggregates is not None:
            save_aggregates(account_id, aggregates)