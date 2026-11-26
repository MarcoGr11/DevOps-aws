#!/usr/bin/env bash
# Використання:
#   scripts/lab10/alarm-watch.sh            поточний стан alarm (StateValue, StateReason)
#   scripts/lab10/alarm-watch.sh --watch 5  опитування кожні 5 с; переходи друкуються з причиною
#   scripts/lab10/alarm-watch.sh --history  describe-alarm-history
#   scripts/lab10/alarm-watch.sh --queue    сповіщення SNS у черзі SQS bookings-alerts-queue
#                                           (читаються з visibility-timeout 0 — не видаляються)
set -euo pipefail
source "$(dirname "$0")/lib.sh"

# state NAME -> "STATE|оновлено|причина|точки" (точки — recentDatapoints з StateReasonData)
state() {
  aws cloudwatch describe-alarms --alarm-names "$1" --output json | jq -r '.MetricAlarms[0] |
    [.StateValue, (.StateUpdatedTimestamp | sub("\\.[0-9]+"; "") | sub("T"; " ")), .StateReason,
     ((.StateReasonData // "{}") | fromjson | .recentDatapoints // [] | map(. * 10 | round / 10 | tostring)
      | join(", "))]
    | join("|")'
}

show() {
  local a s
  for a in "${ALARMS[@]}"; do
    IFS='|' read -r st upd reason pts <<<"$(state "$a")"
    printf '  %-22s %-17s з %s\n      StateReason: %s%s\n' "$a" "$st" "$upd" "$reason" \
      "${pts:+ (останні точки: $pts)}"
  done
}

case "${1:-}" in
--watch)
  every="${2:-5}"
  declare -a prev=("" "")
  title "Стежу за alarms кожні $every с (Ctrl+C — вихід)"
  while true; do
    line="$(date +%T)"
    for i in 0 1; do
      IFS='|' read -r st upd reason pts <<<"$(state "${ALARMS[$i]}")"
      line+="  ${ALARMS[$i]#bookings-}=$st"
      if [[ -n "${prev[$i]}" && "${prev[$i]}" != "$st" ]]; then
        printf '%s  >>> %s: %s -> %s (StateUpdated %s)\n      StateReason: %s%s\n' "$(date +%T)" \
          "${ALARMS[$i]}" "${prev[$i]}" "$st" "${upd#* }" "$reason" "${pts:+ (останні точки: $pts)}"
      fi
      prev[$i]="$st"
    done
    echo "$line"
    pause "$every"
  done
  ;;
--history)
  title "describe-alarm-history (StateUpdate)"
  # час переходу беремо з queryDate у HistoryData: поле Timestamp у LocalStack 4.9.2 для
  # переходів, крім першого, показує момент попереднього оновлення (див. LAB10.md)
  for a in "${ALARMS[@]}"; do
    aws cloudwatch describe-alarm-history --alarm-name "$a" --history-item-type StateUpdate \
      --output json | jq -r --arg a "$a" '.AlarmHistoryItems | sort_by(.Timestamp)[] |
      (.HistoryData | fromjson) as $h |
      [($h.newState.stateReasonData.queryDate // .Timestamp | .[0:19] + "Z" | fromdate
        | strflocaltime("%H:%M:%S")), $a,
       "\($h.oldState.stateValue) -> \($h.newState.stateValue)",
       ($h.newState.stateReasonData.recentDatapoints // [] | map(. * 10 | round / 10 | tostring) | join(", "))]
      | @tsv'
  done | sort | while IFS=$'\t' read -r t a tr pts; do
    printf '  %s  %s  %s\n            recentDatapoints: %s\n' "$t" "$a" "$tr" "${pts:--}"
  done
  ;;
--queue)
  title "SNS bookings-alerts -> SQS bookings-alerts-queue"
  q=$(aws sqs get-queue-url --queue-name bookings-alerts-queue --query QueueUrl --output text)
  aws sqs receive-message --queue-url "$q" --max-number-of-messages 10 --visibility-timeout 0 \
    --output json | jq -r '.Messages // [] | map(.Body | fromjson | .Message | fromjson)
      | sort_by(.StateChangeTime)[] | (.StateChangeTime[0:19] + "Z" | fromdate | strflocaltime("%H:%M:%S"))
      + "  \(.AlarmName)  \(.OldStateValue) -> \(.NewStateValue)"' | sed 's/^/  /'
  ;;
*)
  title "Стан alarms ($(date +%T))"
  show
  ;;
esac
