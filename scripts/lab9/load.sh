#!/usr/bin/env bash
# Використання: scripts/lab9/load.sh [N=30] [URL=http://localhost:8080]
# N запитів GET /health через балансувальник + POSTS (за замовч. 3) POST /bookings,
# щоб показати, що різні екземпляри пишуть у спільну таблицю DynamoDB.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

N="${1:-30}"
URL="${2:-$LB_URL}"
POSTS="${POSTS:-3}"

title "$N x GET $URL/health"
burst "$N" "$URL/health" | summary

if ((POSTS > 0)); then
  title "$POSTS x POST $URL/bookings (спільна БД)"
  for ((i = 1; i <= POSTS; i++)); do
    out=$(curl -s -X POST "$URL/bookings" -H 'Content-Type: application/json' \
      -d "{\"user\":\"load-$i\",\"room\":\"C-30$i\",\"date\":\"2026-12-0$i\",\"slot\":\"09:00-10:00\"}" \
      -w '\n%{http_code} %header{x-instance-id}')
    read -r code inst <<<"$(tail -n1 <<<"$out")"
    printf '  POST /bookings -> %s  %-11s id=%s\n' "$code" "$inst" "$(head -n1 <<<"$out" | jq -r .id)"
  done
  out=$(curl -s "$URL/bookings" -w '\n%header{x-instance-id}')
  printf '  GET /bookings  -> count=%s, відповів %s\n' "$(head -n1 <<<"$out" | jq .count)" "$(tail -n1 <<<"$out")"
fi
