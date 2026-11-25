import time

from .aggregates import refresh_redis_from_database


REFRESH_INTERVAL = 60


if __name__ == "__main__":
    while True:
        start_time = time.monotonic()

        try:
            refresh_redis_from_database()

        except Exception as error:
            print(f"Ошибка обновления агрегатов: {error}")

        elapsed = time.monotonic() - start_time
        time.sleep(max(0, REFRESH_INTERVAL - elapsed))
