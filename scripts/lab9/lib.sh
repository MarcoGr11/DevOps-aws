# Спільні функції скриптів лаби 9 (підключається через source).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LB_URL="${LB_URL:-http://localhost:8080}"

# --progress quiet: без рядків "Container ... Started", щоб вивід скриптів був компактним
compose() { docker compose --progress quiet -f "$ROOT/docker-compose.lab9.yml" "$@"; }

# burst N URL -> N рядків "код екземпляр час_с"; код 000 = з'єднання не встановлено
burst() {
  local n=$1 url=$2 i
  for ((i = 1; i <= n; i++)); do
    curl -s -o /dev/null --max-time 5 \
      -w '%{http_code} %header{x-instance-id} %{time_total}\n' "$url" || true
  done | awk '{ print $1, ($3 == "" ? "-" : $2), ($3 == "" ? $2 : $3) }'
}

# summary < рядки burst: розподіл за X-Instance-Id, коди відповіді, час
summary() {
  awk '
    { n++; inst[$2]++; code[$1]++; t += $3; if ($3 > max) max = $3; if ($1 == 200) ok++ }
    END {
      print "  Розподіл за X-Instance-Id:"
      for (k in inst) printf "    %3d  %s\n", inst[k], k | "sort -k2"
      close("sort -k2")
      print "  Коди відповіді:"
      for (k in code) printf "    %3d  %s\n", code[k], (k == "000" ? "000 (немає з\x27єднання)" : k) | "sort -k2"
      close("sort -k2")
      printf "  Успіх (200): %d/%d = %.0f%%;  час: середній %.3f с, макс. %.3f с\n", ok, n, 100 * ok / n, t / n, max
    }'
}

# wait_healthy SERVICE: чекає статус healthy контейнера (макс. 60 с)
wait_healthy() {
  local id i
  id=$(compose ps -q "$1")
  for ((i = 0; i < 60; i++)); do
    [[ $(docker inspect -f '{{.State.Health.Status}}' "$id") == healthy ]] && return 0
    sleep 1
  done
  echo "$1 не став healthy за 60 с" >&2
  return 1
}

title() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
