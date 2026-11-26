#!/usr/bin/env bash
# Розгортання API бронювання коворкінгу в LocalStack: DynamoDB + Lambda + API Gateway.
# Скрипт ідемпотентний: повторний запуск оновлює код і нічого не дублює.
set -euo pipefail
cd "$(dirname "$0")"

# --- Налаштування -------------------------------------------------------------
ENDPOINT="${LOCALSTACK_ENDPOINT:-http://localhost:4566}"
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test   # фейкові ключі LocalStack
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}" AWS_PAGER=""
REGION="$AWS_DEFAULT_REGION"
TABLE=bookings
FUNCTION=bookings-api
ROLE=bookings-lambda-role
API_NAME=bookings-api
STAGE=dev
ZIP=build/function.zip
aws() { command aws --endpoint-url="$ENDPOINT" "$@"; }       # усі виклики — у LocalStack
log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# --- 1. Очікування готовності LocalStack ---------------------------------------
log "1/7 Чекаю на LocalStack ($ENDPOINT)"
for _ in $(seq 1 60); do
  ready=$(curl -sf "$ENDPOINT/_localstack/health" \
    | jq -r '[.services.lambda, .services.apigateway, .services.dynamodb, .services.iam]
             | all(. == "available" or . == "running")' 2>/dev/null || true)
  [[ "$ready" == true ]] && break
  sleep 2
done
[[ "${ready:-}" == true ]] || { echo "LocalStack не готовий: запустіть 'docker compose up -d'" >&2; exit 1; }
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "LocalStack готовий, account=$ACCOUNT, region=$REGION"

# --- 2. Таблиця DynamoDB --------------------------------------------------------
log "2/7 Таблиця DynamoDB '$TABLE'"
if aws dynamodb describe-table --table-name "$TABLE" >/dev/null 2>&1; then
  echo "вже існує"
else
  aws dynamodb create-table --table-name "$TABLE" \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  aws dynamodb wait table-exists --table-name "$TABLE"
  echo "створено"
fi

# --- 3. Пакування коду ----------------------------------------------------------
log "3/7 Пакую lambda/ у $ZIP"
mkdir -p build && rm -f "$ZIP"
(cd lambda && zip -qr "../$ZIP" . -x '__pycache__/*' '*.pyc')   # boto3 вже є в runtime
unzip -Z1 "$ZIP"

# --- 4. IAM-роль для Lambda -----------------------------------------------------
log "4/7 IAM-роль '$ROLE'"
TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
if aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam update-assume-role-policy --role-name "$ROLE" --policy-document "$TRUST"
  echo "вже існує, trust policy оновлено"
else
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document "$TRUST" >/dev/null
  echo "створено"
fi
# LocalStack не перевіряє IAM-права, але в реальному AWS функції потрібні логи і DynamoDB
aws iam attach-role-policy --role-name "$ROLE" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam attach-role-policy --role-name "$ROLE" \
  --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
ROLE_ARN=$(aws iam get-role --role-name "$ROLE" --query Role.Arn --output text)

# --- 5. Lambda-функція ----------------------------------------------------------
log "5/7 Lambda-функція '$FUNCTION'"
ENV_VARS="Variables={TABLE_NAME=$TABLE}"
if aws lambda get-function --function-name "$FUNCTION" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FUNCTION" --zip-file "fileb://$ZIP" >/dev/null
  aws lambda wait function-updated-v2 --function-name "$FUNCTION"
  aws lambda update-function-configuration --function-name "$FUNCTION" \
    --environment "$ENV_VARS" --timeout 15 >/dev/null
  aws lambda wait function-updated-v2 --function-name "$FUNCTION"
  echo "код і конфігурацію оновлено"
else
  aws lambda create-function --function-name "$FUNCTION" \
    --runtime python3.12 --handler handler.lambda_handler \
    --role "$ROLE_ARN" --zip-file "fileb://$ZIP" \
    --timeout 15 --memory-size 128 --environment "$ENV_VARS" >/dev/null
  aws lambda wait function-active-v2 --function-name "$FUNCTION"
  echo "створено"
fi
FN_ARN=$(aws lambda get-function --function-name "$FUNCTION" --query Configuration.FunctionArn --output text)

# --- 6. API Gateway (REST API) --------------------------------------------------
log "6/7 API Gateway '$API_NAME'"
API_ID=$(aws apigateway get-rest-apis --query "items[?name=='$API_NAME'].id | [0]" --output text)
if [[ "$API_ID" == None || -z "$API_ID" ]]; then
  API_ID=$(aws apigateway create-rest-api --name "$API_NAME" \
    --endpoint-configuration types=REGIONAL --query id --output text)
  echo "створено API $API_ID"
else
  echo "вже існує API $API_ID"
fi

# id ресурсу за шляхом; створює ресурс, якщо його ще немає
resource_id() {  # $1 = повний шлях, $2 = id батька, $3 = path part
  local id
  id=$(aws apigateway get-resources --rest-api-id "$API_ID" \
       --query "items[?path=='$1'].id | [0]" --output text)
  if [[ "$id" == None || -z "$id" ]]; then
    id=$(aws apigateway create-resource --rest-api-id "$API_ID" \
         --parent-id "$2" --path-part "$3" --query id --output text)
  fi
  echo "$id"
}

# метод + проксі-інтеграція з Lambda (put-integration перезаписує, тож це ідемпотентно)
method() {  # $1 = resource id, $2 = HTTP-метод, $3 = шлях (для логу)
  aws apigateway get-method --rest-api-id "$API_ID" --resource-id "$1" --http-method "$2" >/dev/null 2>&1 \
    || aws apigateway put-method --rest-api-id "$API_ID" --resource-id "$1" \
         --http-method "$2" --authorization-type NONE >/dev/null
  aws apigateway put-integration --rest-api-id "$API_ID" --resource-id "$1" \
    --http-method "$2" --type AWS_PROXY --integration-http-method POST \
    --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/$FN_ARN/invocations" >/dev/null
  echo "  $2 $3 -> AWS_PROXY -> $FUNCTION"
}

ROOT_ID=$(aws apigateway get-resources --rest-api-id "$API_ID" --query "items[?path=='/'].id | [0]" --output text)
HEALTH_ID=$(resource_id /health "$ROOT_ID" health)
BOOKINGS_ID=$(resource_id /bookings "$ROOT_ID" bookings)
BOOKING_ID=$(resource_id '/bookings/{id}' "$BOOKINGS_ID" '{id}')

method "$HEALTH_ID"   GET    /health
method "$BOOKINGS_ID" GET    /bookings
method "$BOOKINGS_ID" POST   /bookings
method "$BOOKING_ID"  GET    '/bookings/{id}'
method "$BOOKING_ID"  DELETE '/bookings/{id}'

# дозвіл API Gateway викликати функцію (видаляємо старий, щоб не було конфлікту statement-id)
aws lambda remove-permission --function-name "$FUNCTION" --statement-id apigateway-invoke >/dev/null 2>&1 || true
aws lambda add-permission --function-name "$FUNCTION" --statement-id apigateway-invoke \
  --action lambda:InvokeFunction --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$REGION:$ACCOUNT:$API_ID/*/*/*" >/dev/null
echo "  дозвіл lambda:InvokeFunction для apigateway.amazonaws.com"

# --- 7. Розгортання stage і вивід URL ------------------------------------------
log "7/7 Розгортаю stage '$STAGE'"
DEPLOY_ID=$(aws apigateway create-deployment --rest-api-id "$API_ID" --stage-name "$STAGE" \
  --description "deploy.sh $(date -u +%FT%TZ)" --query id --output text)
echo "deployment $DEPLOY_ID"

# LocalStack підтримує два формати URL; перший потребує DNS *.localhost.localstack.cloud
URL_DNS="http://$API_ID.execute-api.localhost.localstack.cloud:4566/$STAGE"
URL_PATH="$ENDPOINT/restapis/$API_ID/$STAGE/_user_request_"
API_URL=""
for _ in $(seq 1 30); do   # перший виклик стартує контейнер Lambda, тому чекаємо
  for url in "$URL_DNS" "$URL_PATH"; do
    if [[ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$url/health")" == 200 ]]; then
      API_URL=$url; break 2
    fi
  done
  sleep 2
done
[[ -n "$API_URL" ]] || { echo "GET /health не відповідає 200" >&2; exit 1; }
echo "$API_URL" > .api-url

log "Готово"
echo "API URL: $API_URL   (збережено в .api-url)"
curl -s "$API_URL/health"; echo
