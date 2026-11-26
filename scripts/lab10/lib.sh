# Спільні функції скриптів лаби 10 (підключається через source).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LB_URL="${LB_URL:-http://localhost:8080}"
CW_ENDPOINT="${CW_ENDPOINT:-http://localhost:4567}"   # LocalStack стека лаби 10
PY="$ROOT/.venv/bin/python"
# фіктивні ключі LocalStack (не секрет); реальні ключі тут не потрібні й не використовуються
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}" AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}" CW_ENDPOINT

aws() { command aws --endpoint-url "$CW_ENDPOINT" "$@"; }
compose() {
  docker compose --progress quiet -f "$ROOT/docker-compose.lab9.yml" -f "$ROOT/docker-compose.lab10.yml" "$@"
}
title() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
pause() { perl -e "select(undef, undef, undef, $1)"; }   # sleep з дробовими секундами

ALARMS=(bookings-high-errors bookings-high-latency)
