#!/usr/bin/env bash
# Використання: scripts/lab10/cw-check.sh
# Доступ до CloudWatch API (LocalStack) і список метрик namespace Bookings.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

title "CloudWatch API: $CW_ENDPOINT, namespace ${METRICS_NAMESPACE:-Bookings}"
aws cloudwatch list-metrics --namespace "${METRICS_NAMESPACE:-Bookings}" \
  --query 'Metrics[].[MetricName, Dimensions[0].Name || `-`, Dimensions[0].Value || `(агрегат)`]' \
  --output text | sort | awk '{ printf "  %-13s %-11s %s\n", $1, $2, $3 }'
echo "  усього метрик: $(aws cloudwatch list-metrics --namespace "${METRICS_NAMESPACE:-Bookings}" \
  --query 'length(Metrics)' --output text)"
