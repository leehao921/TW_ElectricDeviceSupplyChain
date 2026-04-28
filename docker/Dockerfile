FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Taipei

RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata ca-certificates \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash scheduler

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Application code (ingestion/, graph/, scripts/utils.py) is provided at
# runtime via the bind mount declared in docker-compose.yml (../:/app:ro).
# This keeps the build context tight and lets the container start even
# before sibling Units have merged their modules into the repo.

RUN mkdir -p /app/ingestion /app/graph /app/scripts \
 && chown -R scheduler:scheduler /app

USER scheduler

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python3 -c "import asyncpg" || exit 1

ENTRYPOINT ["python3", "-u", "-m", "ingestion.scheduler"]
