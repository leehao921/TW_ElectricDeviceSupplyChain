#!/usr/bin/env bash
# Validates docker-compose.yml by rendering it with `docker compose config`
# and checking that the expected service and env keys are present.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "INFO: $ENV_FILE not found; using .env.example for config validation"
    ENV_FILE="$SCRIPT_DIR/.env.example"
fi

RENDERED="$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" config)"

fail=0
check() {
    local pattern="$1"
    local label="$2"
    if grep -q "$pattern" <<<"$RENDERED"; then
        echo "OK   $label"
    else
        echo "MISS $label (pattern: $pattern)"
        fail=1
    fi
}

check "tw-electronics-scheduler:" "service tw-electronics-scheduler"
check "host.docker.internal[:=]host-gateway" "extra_hosts host-gateway"
check "TZ:" "env TZ"
check "PG_NEWS_DSN:" "env PG_NEWS_DSN"
check "PG_TRADING_DSN:" "env PG_TRADING_DSN"
check "FALKORDB_HOST:" "env FALKORDB_HOST"
check "FALKORDB_PORT:" "env FALKORDB_PORT"
check "OLLAMA_BASE_URL:" "env OLLAMA_BASE_URL"
check "EMBEDDING_MODEL:" "env EMBEDDING_MODEL"
check "GRAPHITI_GROUP_ID:" "env GRAPHITI_GROUP_ID"
check "FINMIND_TOKEN:" "env FINMIND_TOKEN"
check "restart: unless-stopped" "restart policy"
check "read_only: true" "read-only repo mount"

if [[ $fail -ne 0 ]]; then
    echo "FAIL: docker-compose config missing expected keys"
    exit 1
fi
echo "PASS: docker-compose config looks good"
