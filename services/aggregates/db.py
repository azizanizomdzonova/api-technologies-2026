
import os
import psycopg


def load_transactions():
    """Получает транзакции за последние 30 дней из PostgreSQL."""

    connection = psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "antifraud"),
        user=os.getenv("POSTGRES_USER", "antifraud"),
        password=os.getenv("POSTGRES_PASSWORD", "antifraud")
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT account_id, amount, timestamp
                FROM transactions
                WHERE timestamp >= NOW() - INTERVAL '30 days'
                  AND timestamp < NOW()
            """)

            rows = cursor.fetchall()

            return [
                {
                    "account_id": str(account_id),
                    "amount": float(amount),
                    "timestamp": timestamp
                }
                for account_id, amount, timestamp in rows
            ]

    finally:
        connection.close()
