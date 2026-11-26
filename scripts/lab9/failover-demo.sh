#!/usr/bin/env bash
# Failover і відновлення: зупиняємо app2, дивимось розподіл, запускаємо знову.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

N="${1:-30}"
URL="$LB_URL/health"
log=$(mktemp)
trap 'rm -f "$log"' EXIT

title "1/4 Стан до відмови: $N запитів"
burst "$N" "$URL" | tee "$log.1" | summary

title "2/4 docker compose stop app2"
compose stop app2
compose ps -a app2 --format '  {{.Service}}: {{.Status}}'

title "3/4 Після зупинки app2: $N запитів (перші можуть бути повільнішими)"
burst "$N" "$URL" | tee "$log.2" | summary
echo "  Перші 5 запитів (код екземпляр час_с):"
head -5 "$log.2" | sed 's/^/    /'

title "4/4 docker compose start app2 -> healthy -> $N запитів"
compose start app2
wait_healthy app2
compose ps app2 --format '  {{.Service}}: {{.Status}}'
# app2 міг бути виключений nginx на fail_timeout=5s — чекаємо, поки nginx знову його спробує
sleep 6
burst "$N" "$URL" | tee "$log.3" | summary

title "Підсумок"
printf '  %5s %5s %6s %6s %6s  %s\n' "200" "інше" "app1" "app2" "app3" "етап"
for i in 1 2 3; do
  label=$(sed -n "${i}p" <<<$'до відмови\napp2 зупинено\napp2 відновлено')
  awk -v l="$label" '{ n++; if ($1 == 200) ok++; c[$2]++ }
    END { printf "  %5d %5d %6d %6d %6d  %s\n", ok, n - ok, c["instance-1"], c["instance-2"], c["instance-3"], l }' "$log.$i"
done
rm -f "$log".[123]
