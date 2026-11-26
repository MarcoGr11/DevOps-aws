#!/usr/bin/env bash
# Видалення ресурсів, створених deploy.sh, з LocalStack (сам контейнер не зупиняється).
set -euo pipefail
cd "$(dirname "$0")"

ENDPOINT="${LOCALSTACK_ENDPOINT:-http://localhost:4566}"
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}" AWS_PAGER=""
aws() { command aws --endpoint-url="$ENDPOINT" "$@"; }

for id in $(aws apigateway get-rest-apis --query "items[?name=='bookings-api'].id" --output text); do
  aws apigateway delete-rest-api --rest-api-id "$id" && echo "REST API $id видалено"
done
aws lambda delete-function --function-name bookings-api 2>/dev/null && echo "Lambda видалено" || true
for p in service-role/AWSLambdaBasicExecutionRole AmazonDynamoDBFullAccess; do
  aws iam detach-role-policy --role-name bookings-lambda-role --policy-arn "arn:aws:iam::aws:policy/$p" 2>/dev/null || true
done
aws iam delete-role --role-name bookings-lambda-role 2>/dev/null && echo "IAM-роль видалено" || true
aws dynamodb delete-table --table-name bookings >/dev/null 2>&1 && echo "Таблицю видалено" || true
rm -rf build .api-url
echo "Готово"
