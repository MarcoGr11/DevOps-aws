# Шпаргалка для захисту лаби 8

## Простими словами

- **Serverless** — я пишу лише функцію, а сервер, ОС, масштабування і запуск бере на себе
  хмара. Платиш за виклики, а не за час роботи сервера; немає трафіку — немає витрат.
- **AWS Lambda** — сервіс, що запускає мою функцію `lambda_handler(event, context)` у
  відповідь на подію (тут — HTTP-запит). Кожен виклик отримує `event` і має повернути
  результат. Між викликами стан не зберігається, тому дані — в БД.
- **API Gateway** — «вхідні двері»: приймає HTTP-запит, за методом і шляхом
  (`GET /bookings/{id}`) вирішує, куди його віддати. `AWS_PROXY` = весь запит передається в
  Lambda як `event`, а відповідь Lambda (`statusCode`, `headers`, `body`) повертається клієнту.
- **DynamoDB** — NoSQL-база «ключ → документ». Таблиці потрібен лише ключ (`id`), решта
  полів довільні. `PAY_PER_REQUEST` — без резервування потужності.
- **IAM-роль** — «посвідчення» функції: які дії в AWS їй дозволені.
- **LocalStack** — емулятор AWS у Docker-контейнері. Ті самі API на `localhost:4566`, без
  акаунта і без грошей. Lambda він запускає в окремих Docker-контейнерах.
- **awslocal** — `aws` CLI з `--endpoint-url=http://localhost:4566`.

## Жива демонстрація (5–7 хв)

```bash
cd ~/PycharmProjects/DevOps-aws
export DISABLE_DEPRECATION_NOTICE=1 AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1

# 1. LocalStack працює (≈30 с)
docker compose up -d --wait
docker ps --filter name=localstack
curl -s localhost:4566/_localstack/health | jq '.version, .services.lambda, .services.dynamodb, .services.apigateway'

# 2. Розгортання одним скриптом (≈1 хв) — пояснити 7 кроків
./deploy.sh

# 3. Що створилося
awslocal dynamodb list-tables
awslocal lambda list-functions --query 'Functions[].FunctionName'
awslocal apigateway get-rest-apis --query 'items[].[id,name]'

# 4. CRUD руками
API=$(cat .api-url); CT='Content-Type: application/json'
curl -si -X POST "$API/bookings" -H "$CT" -d '{"user":"olena","room":"A-101","date":"2026-12-01","slot":"10:00-12:00"}'
ID=<id з відповіді>
curl -s "$API/bookings/$ID" | jq .
curl -s "$API/bookings" | jq .
awslocal dynamodb scan --table-name bookings      # запис справді в DynamoDB
curl -si -X DELETE "$API/bookings/$ID"
curl -si "$API/bookings/$ID"                       # 404
curl -si -X POST "$API/bookings" -H "$CT" -d '{"user": broken'   # 400

# 5. Автоматичні перевірки
./smoke-test.sh
make test

# 6. Ідемпотентність: повторний деплой нічого не дублює ("вже існує")
./deploy.sh
```

## Ймовірні питання

1. **Чим serverless відрізняється від Django в Kubernetes (лаби 1–7)?**
   Там я керував контейнерами, репліками, сервісами. Тут — лише код функції; запуск і
   масштабування робить платформа. Мінуси: холодний старт, ліміти часу, vendor lock-in.

2. **Що таке `AWS_PROXY` інтеграція?**
   API Gateway передає весь запит (метод, шлях, заголовки, тіло, `pathParameters`) у Lambda
   одним `event` і повертає її відповідь як є. Маршрутизацію за методом/шляхом я роблю в коді.

3. **Чому `integration-http-method POST`, якщо метод GET/DELETE?**
   Це метод виклику Lambda API (`Invoke`) — він завжди POST. Метод клієнта лежить у `event.httpMethod`.

4. **Навіщо `add-permission`?**
   Lambda за замовчуванням нікому не дозволяє себе викликати. Resource-based policy дає
   право `apigateway.amazonaws.com` викликати функцію, `source-arn` обмежує саме моїм API.

5. **Як Lambda в LocalStack знаходить DynamoDB?**
   `localhost` у контейнері функції — сама функція. LocalStack передає `AWS_ENDPOINT_URL`
   з IP свого контейнера; код бере його, а в реальному AWS змінної немає — стандартний endpoint.

6. **Чому `id` — partition key і uuid?**
   Усі операції — за `id`; uuid унікальний без центрального лічильника і рівномірно
   розподіляє дані по партиціях.

7. **У чому ідемпотентність `deploy.sh`?**
   Перед створенням кожного ресурсу перевіряю, чи він є (`describe-table`, `get-role`,
   `get-function`, пошук API за назвою, `get-method`); якщо є — оновлюю, а не створюю.
   Другий запуск дає «вже існує», дублікатів немає.

8. **Чому `scan` для списку — погано в продакшені?**
   Читає всю таблицю (дорого, повільно, ліміт 1 МБ на сторінку). Краще `query` по індексу
   (наприклад GSI `date`) і пагінація через `LastEvaluatedKey`.

9. **Як тестуєте без AWS?**
   Юніт-тести підміняють таблицю заглушкою `FakeTable` (pytest, 16 тестів: CRUD, 400, 404,
   500, Decimal). End-to-end — `smoke-test.sh` через curl проти LocalStack.

10. **Чому LocalStack 4.9.2, а не latest?**
    `latest` (2026.11) вимагає `LOCALSTACK_AUTH_TOKEN` і без нього завершується з кодом 55.
    4.9.2 працює в community-режимі з усіма потрібними сервісами. Токен, якщо знадобиться,
    — лише в `.env` (у `.gitignore`).

Бонус: **що буде з даними після `docker compose down`?** Зникнуть — persistence у
LocalStack платна. Після перезапуску — `./deploy.sh`.
