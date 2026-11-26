#!/usr/bin/env bash
# Smoke-тест розгорнутого API: POST -> GET id -> GET список -> DELETE -> GET id (404) + 400.
# Завершується з ненульовим кодом при першій розбіжності.
set -euo pipefail
cd "$(dirname "$0")"

API_URL="${API_URL:-$(cat .api-url 2>/dev/null || true)}"
[[ -n "$API_URL" ]] || { echo "Немає .api-url: спочатку ./deploy.sh" >&2; exit 1; }
BODY=$(mktemp); trap 'rm -f "$BODY"' EXIT
ok()   { printf '\033[32m  OK\033[0m   %s\n' "$*"; }
fail() { printf '\033[31m  FAIL\033[0m %s\n' "$*"; cat "$BODY"; echo; exit 1; }

# req МЕТОД ШЛЯХ ОЧІКУВАНИЙ_КОД [JSON]
req() {
  local code
  code=$(curl -s -o "$BODY" -w '%{http_code}' -X "$1" -H 'Content-Type: application/json' \
         ${4:+--data "$4"} "$API_URL$2")
  [[ "$code" == "$3" ]] || fail "$1 $2: очікував $3, отримав $code"
  ok "$1 $2 -> $code"
}

echo "API: $API_URL"
req GET /health 200
jq -e '.status == "ok"' "$BODY" >/dev/null || fail "health.status != ok"

req POST /bookings 201 '{"user":"smoke","room":"A-101","date":"2026-12-01","slot":"10:00-12:00"}'
ID=$(jq -er '.id' "$BODY") || fail "у відповіді немає id"
jq -e '.room == "A-101" and .created_at != null' "$BODY" >/dev/null || fail "некоректний запис"
ok "створено id=$ID"

req GET "/bookings/$ID" 200
jq -e --arg id "$ID" '.id == $id and .user == "smoke"' "$BODY" >/dev/null || fail "GET повернув інший запис"

req GET /bookings 200
jq -e --arg id "$ID" 'any(.items[]; .id == $id)' "$BODY" >/dev/null || fail "запису немає в списку"
ok "запис є у списку (count=$(jq .count "$BODY"))"

req DELETE "/bookings/$ID" 200
req GET "/bookings/$ID" 404
req DELETE "/bookings/$ID" 404

req POST /bookings 400 '{"user":"smoke"'
req POST /bookings 400 '{"user":"smoke","room":"A-101","date":"2026-13-01","slot":"10:00-12:00"}'

printf '\n\033[1;32mУсі перевірки пройдено\033[0m\n'
