FROM python:3.12.9-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
RUN pip install --upgrade pip && \
    pip install ".[dev]"

COPY . /app/

RUN mkdir -p /app/data/raw

EXPOSE 8000

CMD ["uvicorn", "ulpf.main:app", "--host", "0.0.0.0", "--port", "8000"]
