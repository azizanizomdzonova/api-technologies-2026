import asyncio
import statistics
import time
from datetime import datetime, timezone

import httpx

URL = "http://localhost:8000/v1/transactions/evaluate"
TOTAL_REQUESTS = 1000
CONCURRENCY = 2


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


async def send_one(client: httpx.AsyncClient, sem: asyncio.Semaphore, idx: int) -> tuple[int, float]:
    payload = {
        "transaction_id": f"bench-tx-{idx}",
        "account_id": f"acc-{idx % 20}",
        "amount": 1500.50 + (idx % 500),
        "currency": "RUB",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "region": "RU-MOW",
        "merchant_id": "merch-42",
    }
    async with sem:
        t0 = time.perf_counter()
        resp = await client.post(URL, json=payload)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return resp.status_code, elapsed_ms


async def main() -> None:
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(timeout=5.0) as client:
        # 5 прогревочных запросов, чтобы исключить холодный старт соединений
        for i in range(5):
            await send_one(client, sem, -1 - i)

        t_start = time.perf_counter()
        results = await asyncio.gather(*(send_one(client, sem, i) for i in range(TOTAL_REQUESTS)))
        total_sec = time.perf_counter() - t_start

    ok_latencies = sorted(ms for code, ms in results if code == 200)
    errors = [code for code, _ in results if code != 200]

    print(f"Total requests : {TOTAL_REQUESTS} (concurrency={CONCURRENCY})")
    print(f"200 OK         : {len(ok_latencies)} | Errors: {len(errors)}")
    print(f"Throughput     : {TOTAL_REQUESTS / total_sec:.1f} RPS")
    if ok_latencies:
        p50 = percentile(ok_latencies, 50)
        p95 = percentile(ok_latencies, 95)
        p99 = percentile(ok_latencies, 99)
        avg = statistics.mean(ok_latencies)
        print(f"Latency (ms)   : avg={avg:.2f} | p50={p50:.2f} | p95={p95:.2f} | p99={p99:.2f}")
        print(f"SLA p95<=100ms : {'PASS' if p95 <= 100.0 else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())