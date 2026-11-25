import os
import redis


# Подключение к Redis
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    decode_responses=True
)


def save_aggregates(account_id, aggregates):
    """Сохраняет два агрегата счёта в Redis."""

    key = f"account:{account_id}:aggregates"

    redis_client.hset(
        key,
        mapping={
            "avg_amount_30d": aggregates["avg_amount_30d"],
            "tx_count_24h": aggregates["tx_count_24h"]
        }
    )
