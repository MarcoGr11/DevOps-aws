# Лаба 8 — чекліст кадрів

Усі кадри в `reports/screens/` — реальні знімки екрана (`screencapture`), зроблені під час
живого виконання команд проти LocalStack 4.9.2: термінал — 8-01, 8-02, 8-04…8-14;
редактор PyCharm — 8-03; браузер (лише вміст сторінки, без панелі браузера) — 8-15. PDF-звіт:
`.venv/bin/python reports/build_report.py` → `reports/lab8-localstack.pdf`.

Вимоги методички:
1 — LocalStack, AWS CLI, засоби взаємодії з локальними AWS API;
2 — Lambda-функція з обробкою HTTP-запитів;
3 — таблиця DynamoDB;
4 — API Gateway з маршрутизацією до Lambda;
5 — створення, отримання, видалення записів;
6 — перевірка HTTP-клієнтом (curl);
7 — автоматизація розгортання одним скриптом AWS CLI;
8 — документація архітектури і послідовності розгортання.

| Кадр | Що видно | Вимоги |
|---|---|---|
| `8-01` | `docker ps`: `localstack/localstack:4.9.2` healthy; `/_localstack/health`: версія 4.9.2, community, `lambda`/`dynamodb`/`apigateway` доступні | 1 |
| `8-02` | `tree -L 2`: структура проєкту; `docker-compose.yml`: порт 4566, `SERVICES`, `docker.sock`, healthcheck | 1, 8 |
| `8-03` | `lambda/handler.py`: `lambda_handler` маршрутизує за `resource` + `httpMethod`, помилки → 500, невідомий маршрут → 404 | 2 |
| `8-04` (або `8-04a`, `8-04b`) | перший `./deploy.sh` з нуля: таблиця, zip, IAM-роль, Lambda, REST API з 5 методами `AWS_PROXY`, дозвіл, stage `dev`, URL | 3, 4, 7 |
| `8-05` | `awslocal dynamodb list-tables`, `lambda list-functions`, `apigateway get-rest-apis` — створені ресурси | 1, 2, 3, 4 |
| `8-06` | `curl -si POST /bookings` → `201 CREATED` + запис з `id`, `created_at` | 5, 6 |
| `8-07` | `curl -si GET /bookings/{id}` → `200` | 5, 6 |
| `8-08` | `GET /bookings` → список із 2 записів, `count: 2` | 5, 6 |
| `8-09` | `awslocal dynamodb scan --table-name bookings` — записи реально в DynamoDB (`Count: 2`, атрибути типу `S`) | 3, 5 |
| `8-10` | `DELETE /bookings/{id}` → `200`, повторний `GET` → `404` | 5, 6 |
| `8-11` | битий JSON → `400 invalid JSON body`; некоректні поля → `400 validation failed` з трьома помилками | 2, 6 |
| `8-12` | `./smoke-test.sh` — усі перевірки OK | 6, 7 |
| `8-13` | `make test` — `16 passed`, `ruff check` — `All checks passed!` | 2, 7 |
| `8-14` | повторний `./deploy.sh` — «вже існує», той самий api-id (ідемпотентність) | 7 |
| `8-15` | GitHub-репозиторій `DevOps-aws`, список комітів гілки `main` | 8 |

Документація (вимога 8): `README.md` (архітектура, ресурси, послідовність розгортання,
розбір кожного рядка `deploy.sh`), `DEFENSE-LAB8.md`, PDF-звіт.
