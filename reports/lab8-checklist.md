# Лаба 8 — чекліст кадрів

Кадри — реальний вивід команд, виконаних наживо проти LocalStack 4.9.2; скрипт
`reports/make_screens.py` виконує команди кадру й рендерить їхній вивід у PNG
(`.venv/bin/python reports/make_screens.py`, перед цим `docker compose up -d --wait`).
Вимоги методички: 1 — LocalStack/AWS CLI; 2 — Lambda з HTTP; 3 — DynamoDB; 4 — API Gateway;
5 — створення/отримання/видалення; 6 — перевірка curl; 7 — автоматизація скриптом; 8 — документація.

| Кадр | Що показує | Вимога |
|---|---|---|
| `8-01-localstack-health.png` | `docker ps` — контейнер `localstack/localstack:4.9.2` healthy; `/_localstack/health` — lambda, apigateway, dynamodb, iam, logs, cloudwatch `running` | 1 |
| `8-02-project-structure.png` | `tree` проєкту і маршрутизація в `lambda_handler` | 2, 8 |
| `8-03-deploy.png` | повний вивід першого `./deploy.sh`: таблиця, zip, роль, функція, API з 5 методами, stage `dev`, URL | 3, 4, 7 |
| `8-04-resources.png` | `awslocal dynamodb list-tables`, `lambda list-functions`, `apigateway get-rest-apis`, `get-resources` | 1, 2, 3, 4 |
| `8-05-post-booking.png` | `curl -i POST /bookings` → `201 CREATED` + запис з `id`, `created_at` | 5, 6 |
| `8-06-get-booking.png` | `curl -i GET /bookings/{id}` → `200` | 5, 6 |
| `8-07-list-bookings.png` | ще один POST і `GET /bookings` → список із 2 записів | 5, 6 |
| `8-08-dynamodb-scan.png` | `awslocal dynamodb scan --table-name bookings` — записи в самій DynamoDB | 3 |
| `8-09-delete-then-404.png` | `DELETE /bookings/{id}` → `200`, потім `GET` → `404` | 5, 6 |
| `8-10-smoke-test.png` | `./smoke-test.sh` — 11 перевірок OK, exit code 0 | 6, 7 |
| `8-11-pytest-ruff.png` | `pytest -v` 16 passed, `ruff check` + `ruff format --check` чисто | 2 |
| `8-12-deploy-idempotent.png` | повторний `./deploy.sh` — «вже існує», той самий API id | 7 |
| `8-13-bad-request-400.png` | битий JSON → `400 invalid JSON body`; некоректні поля → `400 validation failed` + деталі | 2, 5 |

Документація (вимога 8): `README.md` (архітектура, ресурси, послідовність розгортання,
розбір `deploy.sh`), `DEFENSE-LAB8.md`, PDF-звіт `reports/lab8-localstack.pdf`
(`.venv/bin/python reports/build_report.py`).

## Якщо викладач вимагає знімки екрана саме з терміналу

Ті самі команди можна виконати вручну в терміналі й зняти `⌘⇧4` → пробіл → клік по вікну,
зберігши під тими самими іменами в `reports/screens/`. Команди кожного кадру — у списку
`FRAMES` у `reports/make_screens.py` (для 8-03 спочатку `./destroy.sh`, щоб показати
створення з нуля). Перед кадрами з `curl`: `API=$(cat .api-url); CT='Content-Type: application/json'`,
для `awslocal`: `export DISABLE_DEPRECATION_NOTICE=1`.
