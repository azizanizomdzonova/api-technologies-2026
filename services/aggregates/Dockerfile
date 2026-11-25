
FROM python:3.12-slim

WORKDIR /app

COPY services/aggregates/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY services/aggregates/ ./services/aggregates/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "services.aggregates.refresh_worker"]
