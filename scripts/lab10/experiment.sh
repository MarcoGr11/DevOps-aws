#!/usr/bin/env bash
# Використання: scripts/lab10/experiment.sh [full|quick]
#   full  (за замовч.): фази 1–2 по PHASE=120 с, 3–4 по FAULT=180 с, 5 — RECOVER=300 с;
#         межі фаз — на межах хвилин, тож похвилинні точки CloudWatch не змішують фази
#   quick: PHASE=30, FAULT=90, RECOVER=90 — для налагодження (OK може не встигнути, див. LAB10.md)
# Параметри середовища: RATE (запитів/с у нормі, 2), PHASE, FAULT, RECOVER, FRESH=1 (перестворити
# стек, щоб CloudWatch містив лише дані цього прогону).
# Результати: reports/lab10-run.log (журнал з мітками часу), reports/lab10-phases.json (фази),
# reports/lab10-stats.json (підсумок по фазах), reports/graphs/*.png.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

MODE="${1:-full}"
if [[ $MODE == quick ]]; then
  PHASE="${PHASE:-30}" FAULT="${FAULT:-90}" RECOVER="${RECOVER:-90}"
else
  PHASE="${PHASE:-120}" FAULT="${FAULT:-180}" RECOVER="${RECOVER:-300}"
fi
RATE="${RATE:-2}"
FRESH="${FRESH:-1}"
LOG="$ROOT/reports/lab10-run.log"
PHASES="$ROOT/reports/lab10-phases.json"
cd "$ROOT"
: >"$LOG"
# кожен рядок виводу -> мітка часу, термінал і журнал
exec > >(while IFS= read -r l; do printf '[%s] %s\n' "$(date +%T)" "$l"; done | tee -a "$LOG") 2>&1

iso() { date -u -r "$1" +%Y-%m-%dT%H:%M:%SZ; }
next_minute() { echo $(( ($(date +%s) / 60 + 1) * 60 )); }
wait_until() { while (($(date +%s) < $1)); do pause 0.2; done; }
chaos() {   # chaos PORT JSON
  echo "\$ curl -s -X POST localhost:$1/admin/chaos -d '$2'"
  curl -s -X POST "localhost:$1/admin/chaos" -H 'Content-Type: application/json' -d "$2"
  echo
}
chaos_all() { local p; for p in 8101 8102 8103; do chaos "$p" "$1"; done; }
# add_phase ID TITLE START END RATE CHAOS [ALARM CHAOS_AT]
add_phase() {
  local tmp; tmp=$(mktemp)
  jq --argjson id "$1" --arg title "$2" --arg s "$(iso "$3")" --arg e "$(iso "$4")" --argjson rate "$5" \
    --arg chaos "$6" --arg alarm "${7:-}" --arg at "${8:+$(iso "${8:-0}")}" \
    '.phases += [{id: $id, title: $title, start: $s, end: $e, rate: $rate, chaos: $chaos}
      + (if $alarm == "" then {} else {alarm: $alarm, chaos_at: $at} end)]' "$PHASES" >"$tmp"
  mv "$tmp" "$PHASES"
}
# first_transition ALARM STATE SINCE -> epoch першого переходу в STATE не раніше SINCE (з історії;
# час — queryDate оцінки, бо Timestamp історії в LocalStack 4.9.2 неточний)
first_transition() {
  aws cloudwatch describe-alarm-history --alarm-name "$1" --history-item-type StateUpdate --output json |
    jq -r --arg st "$2" --argjson since "$3" '[.AlarmHistoryItems[] | .HistoryData | fromjson
      | select(.newState.stateValue == $st) | .newState.stateReasonData.queryDate // empty
      | .[0:19] + "Z" | fromdate | select(. >= $since)] | min // empty'
}
at() {      # at EPOCH REF TEXT -> "о 07:41:50 (+50 с TEXT)" або "не настав"
  if [[ -n $1 ]]; then echo "о $(date -r "$1" +%T) (+$(($1 - $2)) с $3)"; else echo "не настав"; fi
}
load() {    # load RATE END LABEL
  "$PY" scripts/lab10/loadgen.py --rate "$1" --until "$2" --label "$3" --report 20
}

echo "Експеримент лаби 10: режим $MODE, RATE=$RATE/с, PHASE=${PHASE}s, FAULT=${FAULT}s, RECOVER=${RECOVER}s"
jq -n --arg mode "$MODE" --argjson rate "$RATE" --argjson phase "$PHASE" --argjson fault "$FAULT" \
  '{mode: $mode, rate: $rate, phase_s: $phase, fault_s: $fault, phases: []}' >"$PHASES"

title "Фаза 0: розгортання, alarms, перевірка"
if [[ $FRESH == 1 ]]; then
  compose --profile nolb down
fi
compose up -d --build --wait
compose ps --format 'table {{.Service}}\t{{.Status}}'
chaos_all '{"fail_rate": 0, "latency_ms": 0}'
"$PY" scripts/lab10/loadgen.py --rate "$RATE" --duration 10 --report 0 --label warmup | tail -4
pause 2
scripts/lab10/cw-check.sh
scripts/lab10/alarms.sh

T=$(next_minute)
if ((T - $(date +%s) < 30)); then T=$((T + 60)); fi   # щонайменше 30 с паузи перед фазою 1
echo "Фаза 1 почнеться о $(date -r "$T" +%T) (межа хвилини)"
wait_until "$T"

title "Фаза 1: норма, $RATE запит/с"
S=$T; E=$((S + PHASE)); load "$RATE" "$E" "1 норма"
add_phase 1 "1 норма" "$S" "$E" "$RATE" "—"

R3=$((RATE * 3))
title "Фаза 2: навантаження x3, $R3 запитів/с"
S=$E; E=$((S + PHASE)); load "$R3" "$E" "2 x3"
add_phase 2 "2 навантаження x3" "$S" "$E" "$R3" "—"

title "Фаза 3: fail_rate=0.5 лише на app2 (instance-2), $RATE запит/с"
S=$E; E=$((S + FAULT))
chaos 8102 '{"fail_rate": 0.5}'
load "$RATE" "$E" "3 помилки"
add_phase 3 "3 помилки app2" "$S" "$E" "$RATE" "app2 fail_rate=0.5" bookings-high-errors "$S"

title "Фаза 4: latency_ms=400 на всіх екземплярах, помилки вимкнено"
S=$E; E=$((S + FAULT))
chaos 8102 '{"fail_rate": 0}'
chaos_all '{"latency_ms": 400}'
load "$RATE" "$E" "4 затримка"
add_phase 4 "4 затримка 400 мс" "$S" "$E" "$RATE" "latency_ms=400 (усі)" bookings-high-latency "$S"

title "Фаза 5: відновлення, chaos вимкнено"
S=$E; E=$((S + RECOVER))
chaos_all '{"fail_rate": 0, "latency_ms": 0}'
load "$RATE" "$E" "5 відновлення"
add_phase 5 "5 відновлення" "$S" "$E" "$RATE" "—"

pause 5   # останній пакет метрик (інтервал відправки 1 с)
title "Реакція alarms (з describe-alarm-history)"
tmp=$(mktemp)
for id in 3 4; do
  read -r alarm since until <<<"$(jq -r ".phases[] | select(.id == $id)
    | [.alarm, (.start | fromdate), (.end | fromdate)] | @tsv" "$PHASES")"
  on=$(first_transition "$alarm" ALARM "$since")
  off=$(first_transition "$alarm" OK "$until")
  echo "  $alarm: chaos $(date -r "$since" +%T)–$(date -r "$until" +%T);" \
    "ALARM $(at "$on" "$since" "від початку");" "OK $(at "$off" "$until" "після зняття")"
  jq --argjson id "$id" --arg on "$on" --arg off "$off" '(.phases[] | select(.id == $id)) +=
    {alarm_at: (if $on == "" then null else ($on | tonumber | todate) end),
     ok_at: (if $off == "" then null else ($off | tonumber | todate) end)}' "$PHASES" >"$tmp"
  mv "$tmp" "$PHASES"
done
scripts/lab10/alarm-watch.sh

title "Статистика (GetMetricStatistics / GetMetricData)"
"$PY" scripts/lab10/stats.py --phases "$PHASES" --instances --json "$ROOT/reports/lab10-stats.json"

title "Графіки"
"$PY" scripts/lab10/plot.py --phases "$PHASES" --out "$ROOT/reports/graphs"
echo "Готово. Журнал: reports/lab10-run.log"
