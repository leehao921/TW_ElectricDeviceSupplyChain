# TW Electronics Scheduler (Docker)

Long-running APScheduler container that runs `ingestion.scheduler` as a background worker.
Talks to companion services on the host via `host.docker.internal`.

## Prerequisites
Companion services already running on host:
- Postgres (news) @ `localhost:5433`
- Postgres (trading/TimescaleDB) @ `localhost:5432`
- FalkorDB @ `localhost:6380`
- Ollama @ `localhost:11434`

## Setup
```bash
cp docker/.env.example docker/.env
# edit docker/.env — set FINMIND_TOKEN and verify DSNs
```

## Build
```bash
docker compose -f docker/docker-compose.yml --env-file docker/.env build
```

## Run (detached)
```bash
docker compose -f docker/docker-compose.yml --env-file docker/.env up -d
```

## Logs
APScheduler logs to stdout; follow with:
```bash
docker logs -f tw-electronics-scheduler
```

## Stop
```bash
docker compose -f docker/docker-compose.yml --env-file docker/.env down
```

## Notes
- The repo is bind-mounted read-only at `/app` for live code reload during development.
- The container exposes no ports (background worker only).
- Runs as non-root user `scheduler`.
- Application code (`ingestion/`, `graph/`, `scripts/utils.py`) is provided via the bind mount at runtime, not baked into the image. This lets the image build before sibling Units have merged. If the container logs `ModuleNotFoundError: No module named 'ingestion'`, it means Unit 2's `ingestion/scheduler.py` has not landed on your branch yet.
- Any extra Python deps required by `ingestion.scheduler` (e.g., `apscheduler`, `asyncpg`, `redis`) must be added to the root `requirements.txt` by the unit that introduces them.

## Config validation
```bash
bash docker/test_config.sh
```
Renders compose config and greps for the expected service, env keys, and mount — useful as a quick smoke test before building.
