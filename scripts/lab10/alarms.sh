#!/usr/bin/env bash
# Використання: scripts/lab10/alarms.sh
# Ідемпотентно створює SNS-топік bookings-alerts, чергу SQS bookings-alerts-queue
# (підписана на топік) і два alarm. put-metric-alarm з тим самим іменем перезаписує
# alarm, тож повторний запуск нічого не дублює.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
NS="${METRICS_NAMESPACE:-Bookings}"

title "SNS bookings-alerts -> SQS bookings-alerts-queue"
TOPIC=$(aws sns create-topic --name bookings-alerts --query TopicArn --output text)
QUEUE=$(aws sqs create-queue --queue-name bookings-alerts-queue --query QueueUrl --output text)
QARN=$(aws sqs get-queue-attributes --queue-url "$QUEUE" --attribute-names QueueArn \
  --query Attributes.QueueArn --output text)
if ! aws sns list-subscriptions-by-topic --topic-arn "$TOPIC" --query 'Subscriptions[].Endpoint' \
  --output text | grep -q "$QARN"; then
  aws sns subscribe --topic-arn "$TOPIC" --protocol sqs --notification-endpoint "$QARN" >/dev/null
fi
echo "  topic: $TOPIC"
echo "  queue: $QARN"

# alarm NAME METRIC STAT THRESHOLD DESCRIPTION
alarm() {
  aws cloudwatch put-metric-alarm --alarm-name "$1" --alarm-description "$5" \
    --namespace "$NS" --metric-name "$2" --statistic "$3" \
    --period 60 --evaluation-periods 1 --threshold "$4" \
    --comparison-operator GreaterThanThreshold --treat-missing-data notBreaching \
    --alarm-actions "$TOPIC" --ok-actions "$TOPIC"
  echo "  $1: $3($2) > $4 за 60 с"
}
title "Alarms (period 60 с, evaluation-periods 1, missing data = notBreaching)"
alarm bookings-high-errors ErrorCount Sum 10 "more than 10 HTTP 5xx per minute"
alarm bookings-high-latency Latency Average 200 "average latency above 200 ms per minute"

title "describe-alarms"
aws cloudwatch describe-alarms --alarm-names "${ALARMS[@]}" \
  --query 'MetricAlarms[].[AlarmName, StateValue, MetricName, Statistic, ComparisonOperator, Threshold]' \
  --output table
