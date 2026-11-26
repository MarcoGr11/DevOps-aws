#!/usr/bin/env bash
# Порівняння: з балансувальником (:8080, 3 екземпляри) і без (:8081, один app-single).
set -euo pipefail
source "$(dirname "$0")/lib.sh"

N="${1:-30}"
DIRECT_URL="${DIRECT_URL:-http://localhost:8081}"
rows=()

run() { # run "сценарій" URL
  local res
  res=$(burst "$N" "$2/health" | awk '{ n++; if ($1 == 200) ok++; t += $3 }
    END { printf "%d %d %d %.0f %.3f", n, ok, n - ok, 100 * ok / n, t / n }')
  rows+=("$1|$res")
  read -r n ok _ <<<"$res"
  echo "  $1: 200 = $ok/$n"
}

title "Підготовка: app-single (профіль nolb) на $DIRECT_URL"
compose --profile nolb up -d --wait app-single

title "Усі екземпляри працюють"
run "LB, 3/3" "$LB_URL"
run "без LB, 1/1" "$DIRECT_URL"

title "Відмова одного екземпляра: stop app2 і stop app-single"
compose stop app2
compose --profile nolb stop app-single
run "LB, 2/3" "$LB_URL"
run "без LB, 0/1" "$DIRECT_URL"

title "Відновлення: start app2, start app-single"
compose start app2
compose --profile nolb start app-single
wait_healthy app2
wait_healthy app-single

title "Результат ($N x GET /health; LB = nginx :8080, без LB = app-single :8081)"
printf '  %6s %5s %7s %7s %9s  %s\n' "всього" "200" "помилки" "успіх,%" "сер.час,с" "живих"
for r in "${rows[@]}"; do
  IFS='|' read -r name res <<<"$r"
  read -r n ok err pct avg <<<"$res"
  printf '  %6s %5s %7s %7s %9s  %s\n' "$n" "$ok" "$err" "$pct" "$avg" "$name"
done
