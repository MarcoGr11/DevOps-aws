"""Збирає PDF-звіти лаб 8 і 9 зі знімків екрана reports/screens/.

.venv/bin/python reports/build_report.py        # обидва звіти
.venv/bin/python reports/build_report.py 9      # лише лаба 9
"""

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

STUDENT = "Бабин Богдан Олегович"
GROUP = "443a"  # лаба 8 (як було в її звіті)
GROUP_LAB9 = "143a"
UNIVERSITY = "Чернівецький національний університет імені Юрія Федьковича"
INSTITUTE = "Навчально-науковий інститут фізико-технічних та комп'ютерних наук"
REPO = "github.com/MarcoGr11/DevOps-aws"

HERE = Path(__file__).resolve().parent
SCREENS = HERE / "screens"
FONTS = Path("/System/Library/Fonts/Supplemental")
pdfmetrics.registerFont(TTFont("Arial", FONTS / "Arial Unicode.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", FONTS / "Arial Bold.ttf"))
pdfmetrics.registerFont(TTFont("Menlo", "/System/Library/Fonts/Menlo.ttc"))

BODY = ParagraphStyle("body", fontName="Arial", fontSize=11, leading=15, spaceAfter=6)
H1 = ParagraphStyle(
    "h1", parent=BODY, fontName="Arial-Bold", fontSize=16, leading=20, spaceBefore=8, spaceAfter=8
)
H2 = ParagraphStyle("h2", parent=H1, fontSize=13, leading=17, spaceBefore=6, spaceAfter=6)
TITLE = ParagraphStyle("title", parent=H1, fontSize=20, leading=26, alignment=TA_CENTER)
CENTER = ParagraphStyle("center", parent=BODY, alignment=TA_CENTER)
RIGHT = ParagraphStyle("right", parent=BODY, alignment=2)
CAPTION = ParagraphStyle("caption", parent=BODY, fontSize=10, alignment=TA_CENTER, spaceBefore=4)
CODE = ParagraphStyle("code", fontName="Menlo", fontSize=8, leading=10.5, spaceAfter=8)

# (вимога методички, [(код кадру, підпис, що видно)]); код — префікс імені файлу в screens/,
# кадр може бути розбитий на частини: 8-04a-..., 8-04b-...
SECTIONS = [  # лаба 8
    (
        "Вимога 1. LocalStack, AWS CLI і засоби взаємодії з локальними AWS API",
        [
            (
                "8-01",
                "LocalStack у Docker і його health-check",
                "Контейнер localstack/localstack:4.9.2 у стані healthy; /_localstack/health показує "
                "edition community, сервіси lambda, dynamodb, apigateway доступні.",
            ),
            (
                "8-02",
                "Структура проєкту і docker-compose.yml",
                "Код Lambda, тести, скрипти deploy/destroy/smoke-test, Makefile; сервіс localstack з "
                "портом 4566, списком SERVICES, docker.sock і healthcheck.",
            ),
        ],
    ),
    (
        "Вимога 2. Lambda-функція з обробкою HTTP-запитів",
        [
            (
                "8-03",
                "Маршрутизація і обробка помилок у lambda/handler.py",
                "lambda_handler вибирає обробник за event.resource і event.httpMethod; виняток сховища "
                "перетворюється на 500, невідомий маршрут — на 404.",
            ),
        ],
    ),
    (
        "Вимоги 3–4. Таблиця DynamoDB і API Gateway з маршрутизацією до Lambda",
        [
            (
                "8-05",
                "Створені ресурси в LocalStack",
                "Таблиця bookings, функція bookings-api (python3.12, handler.lambda_handler) і REST API "
                "bookings-api з id dohs5f21ur — той самий id, що в URL з кадру 8-04.",
            ),
        ],
    ),
    (
        "Вимоги 5–6. Створення, отримання, видалення записів і перевірка через curl",
        [
            (
                "8-06",
                "Створення бронювання: POST /bookings",
                "201 CREATED, Content-Type: application/json; у тілі запис зі згенерованими id і created_at.",
            ),
            (
                "8-07",
                "Отримання бронювання: GET /bookings/{id}",
                "200 OK і той самий запис, прочитаний з DynamoDB.",
            ),
            (
                "8-08",
                "Список бронювань: GET /bookings",
                "Після другого POST список містить обидва записи, count = 2.",
            ),
            (
                "8-09",
                "Дані безпосередньо в DynamoDB: dynamodb scan",
                "Count = 2; атрибути запису збережені як рядки (тип S) з тими самими значеннями, "
                "що повернув API.",
            ),
            (
                "8-10",
                "Видалення: DELETE /bookings/{id} і повторний GET",
                'DELETE повертає 200 {"deleted": id}, наступний GET — 404 booking not found.',
            ),
            (
                "8-11",
                "Некоректне тіло запиту",
                "Битий JSON → 400 invalid JSON body; порожній user, дата 2026-02-30 і slot 12:00-10:00 → "
                "400 validation failed з усіма трьома помилками.",
            ),
        ],
    ),
    (
        "Вимога 7. Автоматизація розгортання скриптом AWS CLI",
        [
            (
                "8-04",
                "Перше розгортання ./deploy.sh (з нуля)",
                "За 7 кроків створено таблицю, zip, IAM-роль, функцію, REST API з 5 методами AWS_PROXY, "
                "дозвіл на виклик і stage dev; надруковано URL і відповідь /health.",
            ),
            (
                "8-14",
                "Повторний запуск ./deploy.sh (ідемпотентність)",
                "Таблиця, роль, функція і API «вже існують» з тим самим api-id; оновлено лише код і "
                "створено новий deployment.",
            ),
            (
                "8-12",
                "Автоматична перевірка ./smoke-test.sh",
                "Усі перевірки (health, POST, GET, список, DELETE, 404, 400) — OK.",
            ),
            (
                "8-13",
                "Юніт-тести і лінтер: make test",
                "pytest — 16 passed (DynamoDB замінено заглушкою), ruff check — All checks passed.",
            ),
        ],
    ),
    (
        "Вимога 8. Документація і репозиторій",
        [
            (
                "8-15",
                "Репозиторій DevOps-aws на GitHub",
                "Історія комітів гілки main: LocalStack, Lambda з тестами, скрипти, документація, звіт.",
            ),
        ],
    ),
]

ARCH = """\
 curl / smoke-test.sh
        │ HTTP :4566
 ┌──────▼─────────── Docker: контейнер localstack 4.9.2 ───────────
 │  API Gateway: REST API bookings-api, stage dev
 │    GET /health · GET, POST /bookings · GET, DELETE /bookings/{id}
 │        │ AWS_PROXY (дозвіл lambda:InvokeFunction)
 │        ▼
 │  Lambda bookings-api: python3.12, роль bookings-lambda-role
 │    (окремий контейнер)  ── print() ──▶ CloudWatch Logs
 │        │ boto3, endpoint з AWS_ENDPOINT_URL
 │        ▼
 │  DynamoDB: таблиця bookings, PK id (S), PAY_PER_REQUEST
 └─────────────────────────────────────────────────────────────────"""

DEPLOY_STEPS = [
    "docker compose up -d --wait — запуск LocalStack 4.9.2 і очікування healthcheck;",
    "./deploy.sh: 1) чекає готовності lambda/apigateway/dynamodb/iam; 2) створює таблицю bookings, "
    "якщо її немає; 3) пакує lambda/ у build/function.zip; 4) створює або оновлює IAM-роль; "
    "5) створює функцію або оновлює її код і конфігурацію; 6) створює REST API, ресурси, методи, "
    "AWS_PROXY-інтеграції і дозвіл lambda:InvokeFunction; 7) публікує stage dev, перевіряє /health "
    "і зберігає базовий URL у .api-url;",
    "./smoke-test.sh і make test — end-to-end перевірка через curl і юніт-тести;",
    "./destroy.sh — видалення ресурсів; docker compose down — зупинка LocalStack.",
]

CONCLUSION = [
    "У LocalStack розгорнуто serverless-застосунок бронювання коворкінгу: REST API в API Gateway з "
    "п'ятьма маршрутами через AWS_PROXY викликає Lambda-функцію на Python 3.12, яка зберігає записи в "
    "таблиці DynamoDB bookings. Створення (201), отримання (200/404), список, видалення (200/404) і "
    "валідацію (400) перевірено curl-ом наживо, скриптом smoke-test.sh і 16 юніт-тестами. Розгортання "
    "виконується одним ідемпотентним скриптом deploy.sh: повторний запуск не створює дублікатів, а "
    "оновлює код функції і публікує новий deployment.",
    "Версія LocalStack. Образ localstack/localstack:latest (2026.11) без LOCALSTACK_AUTH_TOKEN "
    "завершується з помилкою активації ліцензії. Тег 4.9.2 працює в community-режимі без акаунта і "
    "містить усі потрібні сервіси, тому його закріплено в docker-compose.yml; це робить середовище "
    "відтворюваним і не потребує секретів у репозиторії.",
    "Квірк Content-Type. curl -d без заголовка надсилає application/x-www-form-urlencoded, і API "
    "Gateway у LocalStack 4.9.2 перекодовує таке тіло у form-формат, тож Lambda отримує не JSON і "
    "відповідає 400. У справжньому AWS proxy-інтеграція передає тіло без змін. Причину знайдено через "
    "логування тіла в CloudWatch Logs; клієнти мають надсилати Content-Type: application/json, що "
    "зафіксовано в README.",
]


# ---------------------------------------------------------------- лаба 9
GOAL9 = (
    "Розгорнути кілька екземплярів HTTP-застосунку бронювання коворкінгу з лаби 8, налаштувати "
    "балансування вхідних запитів і дослідити поведінку системи при зміні кількості доступних "
    "екземплярів, а також порівняти її з варіантом без балансувальника."
)

ARCH9 = """\
     curl / load.sh / failover-demo.sh / compare.sh
                      │ HTTP 127.0.0.1:8080
     ┌────────────────▼────────────────────────────┐
     │ nginx 1.28: upstream bookings_backend,      │
     │ round-robin, max_fails=2 fail_timeout=5s    │
     └──────┬────────────────┬────────────────┬────┘
            │ .11:8000       │ .12:8000       │ .13:8000
     ┌──────▼─────┐   ┌──────▼─────┐   ┌──────▼─────┐
     │ app1       │   │ app2       │   │ app3       │  образ bookings-app:lab9
     │ instance-1 │   │ instance-2 │   │ instance-3 │  (server.py + handler.py)
     └──────┬─────┘   └──────┬─────┘   └──────┬─────┘
            └────────────────┼────────────────┘  boto3, AWS_ENDPOINT_URL
                    ┌────────▼─────────┐
                    │ LocalStack 4.9.2 │  DynamoDB: таблиця bookings
                    └──────────────────┘  (створює init-table, одноразово)

     app-single (профіль nolb): той самий образ напряму на 127.0.0.1:8081"""

ARCH9_TEXT = [
    "Бізнес-логіку лаби 8 не переписано. Тонкий адаптер app/server.py (stdlib http.server) "
    "перетворює HTTP-запит на подію у форматі API Gateway proxy (httpMethod, resource, "
    "pathParameters, headers, body) і викликає той самий lambda_handler. Dockerfile збирається з "
    "кореня репозиторію й копіює lambda/handler.py без дублювання коду. Образ: python:3.12-slim, "
    "непривілейований користувач, HEALTHCHECK на /health.",
    "Ідентифікатор екземпляра задає змінна INSTANCE_ID. Він повертається в тілі /health і в "
    "заголовку X-Instance-Id кожної відповіді. Стан зберігається лише в DynamoDB, тому будь-який "
    "екземпляр може обробити будь-який запит. Стек описано окремим docker-compose.lab9.yml, і "
    "файли лаби 8 не змінювались.",
    "Фіксовані IP бекендів (extra_hosts у nginx) замість DNS Docker: з resolve один запит із 30 "
    "отримав 502 через гонку між повтором і перерезолвленням імені зупиненого екземпляра.",
]

STEPS9 = [
    "docker compose -f docker-compose.lab9.yml up -d --build --wait — збірка образу, LocalStack, "
    "init-table (ідемпотентно створює таблицю), app1–app3, nginx; nginx стартує лише після "
    "healthy-стану трьох бекендів (depends_on: service_healthy);",
    "curl /health і scripts/lab9/load.sh 30 — розподіл запитів за X-Instance-Id і POST через "
    "балансувальник у спільну таблицю;",
    "docker compose stop app2 → load.sh: поведінка балансувальника при відмові екземпляра;",
    "docker compose start app2 → healthy → load.sh: повернення екземпляра в ротацію;",
    "scripts/lab9/compare.sh — порівняння з балансувальником (:8080) і без (app-single на :8081);",
    "make test — юніт-тести адаптера і лаби 8, ruff; прибирання: docker compose "
    "-f docker-compose.lab9.yml --profile nolb down.",
]

SECTIONS9 = [
    (
        "Вимога 1. Контейнеризована версія застосунку",
        [
            (
                "9-01",
                "Структура проєкту і app/Dockerfile",
                "Додано app/ (адаптер, Dockerfile, ініціалізація таблиці), nginx/, scripts/lab9/ і "
                "docker-compose.lab9.yml. Dockerfile копіює lambda/handler.py, запускає застосунок від "
                "користувача app (uid 10001) і має HEALTHCHECK на /health.",
            ),
        ],
    ),
    (
        "Вимоги 2 і 4. Три екземпляри з власним ідентифікатором, endpoint /health",
        [
            (
                "9-03",
                "Запуск стеку: docker compose up --wait і ps",
                "app1–app3 (один образ bookings-app:lab9), nginx і localstack у стані healthy; "
                "init-table завершився з кодом 0 після створення таблиці.",
            ),
            (
                "9-04",
                "Шість запитів GET /health через балансувальник",
                "Кожна відповідь — 200 з заголовком X-Instance-Id і полем instance у тілі; екземпляри "
                "чергуються 1 → 2 → 3 → 1 → 2 → 3.",
            ),
        ],
    ),
    (
        "Вимога 3. Балансувальник для маршрутизації запитів",
        [
            (
                "9-02",
                "Сервіси compose і конфігурація nginx (без коментарів)",
                "Сервіси localstack, init-table, app1–app3, nginx. Upstream з трьох серверів з "
                "max_fails=2 fail_timeout=5s, /nginx-health, короткий connect-таймаут і "
                "proxy_next_upstream для повтору на іншому екземплярі.",
            ),
        ],
    ),
    (
        "Вимога 5. Серія запитів і розподіл між екземплярами",
        [
            (
                "9-05",
                "load.sh 30: розподіл і запис у спільну БД",
                "30 запитів розподілено рівно 10/10/10, усі 200. Три POST обробили три різні "
                "екземпляри, а список, отриманий з instance-1, містить усі 3 записи.",
            ),
            (
                "9-06",
                "Запис, створений одним екземпляром, читають інші",
                "POST обробив instance-2 (201). Два GET того самого id повернули запис з instance-3 і "
                "instance-1, тобто дані спільні, а не в пам'яті екземпляра.",
            ),
        ],
    ),
    (
        "Вимога 6. Виведення екземпляра з роботи",
        [
            (
                "9-07",
                "docker compose stop app2",
                "app2 — Exited (0); app1, app3, nginx і localstack працюють далі (healthy).",
            ),
            (
                "9-08",
                "load.sh 30 при зупиненому app2",
                "30/30 відповідей 200, лише instance-1 (14) і instance-3 (16). Середній час 0,070 с, "
                "максимальний 1,025 с: запити, які nginx спрямував на app2, чекали connect-таймаут 1 с "
                "і були повторені на іншому екземплярі.",
            ),
        ],
    ),
    (
        "Вимога 7. Відновлення екземпляра",
        [
            (
                "9-09",
                "docker compose start app2 і ps",
                "Через 7 с після старту app2 у стані healthy. init-table повторно відпрацював "
                "ідемпотентно (таблиця вже існувала).",
            ),
            (
                "9-10",
                "load.sh 30 після відновлення",
                "app2 знову в ротації: розподіл 10/10/10, 30/30 відповідей 200, максимальний час 0,017 с.",
            ),
        ],
    ),
    (
        "Вимога 8. Порівняння системи з балансуванням і без",
        [
            (
                "9-11",
                "compare.sh: з балансувальником (:8080) і без (app-single на :8081)",
                "Коли всі екземпляри працюють, обидва варіанти дають 100% успіху з однаковим середнім "
                "часом 0,002 с. При відмові одного екземпляра з балансувальником успіх 100% (сер. час "
                "0,070 с), без нього — 0% (з'єднання відхилено).",
            ),
        ],
    ),
    (
        "Тести і репозиторій",
        [
            (
                "9-12",
                "make test: pytest і ruff",
                "21 тест пройдено: 16 тестів лаби 8 без змін і 5 тестів адаптера (перетворення "
                "запиту в подію, X-Instance-Id, /health, реальний HTTP-обмін). ruff — без зауважень.",
            ),
            (
                "9-13",
                "Історія комітів у репозиторії DevOps-aws",
                "Лаба 9 додана окремими комітами (адаптер, балансувальник, скрипти, документація) "
                "поверх комітів лаби 8.",
                10,  # сторінка браузера: шрифт крупніший, ніж у терміналі
            ),
        ],
    ),
]

EXTRA = {
    "9-10": lambda: KeepTogether(
        [
            p("Підсумок етапів (за трьома вимірюваннями load.sh 30 вище):", BODY),
            table(
                [
                    ["Етап", "200", "Помилки", "app1", "app2", "app3", "Сер. час, с", "Макс., с"],
                    ["усі працюють", "30", "0", "10", "10", "10", "0,002", "0,007"],
                    ["app2 зупинено", "30", "0", "14", "0", "16", "0,070", "1,025"],
                    ["app2 відновлено", "30", "0", "10", "10", "10", "0,004", "0,017"],
                ],
                [3.4, 1.2, 1.6, 1.3, 1.3, 1.3, 2.2, 1.7],
            ),
            Spacer(1, 12),
        ]
    ),
    "9-11": lambda: KeepTogether(
        [
            p("Таблиця порівняння (30 запитів GET /health на сценарій):", BODY),
            table(
                [
                    ["Сценарій", "Всього", "200", "Помилки", "Успіх, %", "Сер. час, с"],
                    ["з балансуванням, працюють 3 з 3", "30", "30", "0", "100", "0,002"],
                    ["без балансування, працює 1 з 1", "30", "30", "0", "100", "0,002"],
                    ["з балансуванням, працюють 2 з 3", "30", "30", "0", "100", "0,070"],
                    ["без балансування, працює 0 з 1", "30", "0", "30", "0", "—"],
                ],
                [5.8, 1.5, 1.2, 1.7, 1.7, 2.1],
            ),
            Spacer(1, 12),
        ]
    ),
}

CONCLUSION9 = [
    "Застосунок лаби 8 контейнеризовано без зміни бізнес-логіки й запущено в трьох екземплярах за "
    "nginx. Запити розподіляються по черзі (10/10/10 на 30 запитів). Дані спільні: запис, створений "
    "одним екземпляром, читають інші. Після зупинки одного екземпляра всі 30 запитів успішні, а після "
    "його запуску він знову отримує свою третину запитів. Без балансувальника відмова єдиного "
    "екземпляра дає 100% помилок, з балансувальником — 0%.",
    "Ціна доступності — затримка в момент виявлення відмови. Open-source nginx має лише пасивні "
    "health-check: про зупинений екземпляр він дізнається з невдалої спроби з'єднання, тому окремі "
    "запити тривали ≈1 с (proxy_connect_timeout), а середній час зріс з 0,002 до 0,070 с. Після двох "
    "невдач екземпляр виключається на 5 с. Активні перевірки дали б змогу виключати його заздалегідь.",
    "Обмеження: round-robin не враховує навантаження екземплярів; nginx і DynamoDB лишаються "
    "єдиними точками відмови; фіксовані IP бекендів забезпечують детермінований failover, але "
    "ускладнюють динамічне масштабування. Усі числа виміряно на одному комп'ютері з невеликим "
    "навантаженням з одного клієнта, тож вони ілюструють поведінку, а не продуктивність.",
]


def p(text, style=BODY):
    return Paragraph(text, style)


def frame_files(code):
    return sorted(SCREENS.glob(f"{code}*.png"))


def figure(n, path, title, seen, head=(), width=17 * cm, max_h=21 * cm):
    img = Image(str(path))
    # ширина — щоб текст терміналу читався; дуже високі кадри обмежуємо висотою
    scale = min(width / img.imageWidth, max_h / img.imageHeight)
    img.drawWidth, img.drawHeight = img.imageWidth * scale, img.imageHeight * scale
    parts = [*head, img, p(f"Рис. {n}. {title}", CAPTION)]  # заголовок розділу — разом з першим рисунком
    if seen:
        parts.append(p(f"<b>Що видно:</b> {seen}"))
    return KeepTogether([*parts, Spacer(1, 10)])


def figures(sections, width=17 * cm, max_h=21 * cm, head=()):
    missing = [f[0] for _, frames in sections for f in frames if not frame_files(f[0])]
    if missing:
        sys.exit(f"немає знімків у reports/screens/: {', '.join(missing)}")
    story, n = [], 0
    for heading, frames in sections:
        head = [*head, p(heading, H2)]
        for code, title, seen, *w in frames:
            files = frame_files(code)
            for k, path in enumerate(files, 1):
                n += 1
                part = f" (частина {k} з {len(files)})" if len(files) > 1 else ""
                last = k == len(files)
                story.append(
                    figure(
                        n, path, title + part, seen if last else "", head, w[0] * cm if w else width, max_h
                    )
                )
                head = []
                if last and code in EXTRA:
                    story.append(EXTRA[code]())
    return story, n


def write(name, title, story, n):
    doc = SimpleDocTemplate(
        str(HERE / name),
        pagesize=A4,
        title=title,
        author=STUDENT,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
    )
    doc.build(story)
    print(f"reports/{name}: {n} рисунків, {doc.page} с.")


def lab8():
    body, n = figures(SECTIONS)
    story = [
        Spacer(1, 5 * cm),
        p("Лабораторна робота №8", TITLE),
        p("з курсу «Технології DevOps»", CENTER),
        Spacer(1, 1 * cm),
        p("<b>Розгортання serverless-застосунку в локальному AWS-середовищі (LocalStack)</b>", CENTER),
        p("Предметна область: система бронювання коворкінгу", CENTER),
        Spacer(1, 4 * cm),
        p(f"Виконав: студент групи {GROUP}", RIGHT),
        p(STUDENT, RIGHT),
        Spacer(1, 1 * cm),
        p(f"Репозиторій: {REPO}", CENTER),
        PageBreak(),
        p("Мета", H1),
        p(
            "Розробити HTTP-застосунок для AWS Lambda, розгорнути його в LocalStack із доступом через "
            "API Gateway і зберіганням даних у DynamoDB; реалізувати створення, отримання, список і "
            "видалення бронювань, перевірити їх curl-ом і автоматизувати розгортання одним скриптом AWS CLI."
        ),
        p("Архітектура", H1),
        Preformatted(ARCH, CODE),
        p(
            "Lambda отримує весь HTTP-запит як event (AWS_PROXY) і маршрутизує його за resource та "
            "httpMethod. Адресу DynamoDB усередині LocalStack функція бере зі змінної AWS_ENDPOINT_URL, яку "
            "LocalStack передає в контейнер функції; у реальному AWS змінної немає і використовується "
            "стандартний endpoint."
        ),
        p("Послідовність розгортання", H1),
        *[p(f"{i}. {s}") for i, s in enumerate(DEPLOY_STEPS, 1)],
        PageBreak(),
        p("Хід виконання", H1),
        *body,
        KeepTogether([p("Висновок", H1), *[p(t) for t in CONCLUSION]]),
    ]
    write("lab8-localstack.pdf", "Лабораторна робота №8", story, n)


def table(rows, widths):
    t = Table(rows, colWidths=[w * cm for w in widths], hAlign="CENTER")
    t.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Arial", 9.5),
                ("FONT", (0, 0), (-1, 0), "Arial-Bold", 9.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def lab9():
    # 11 см: по два кадри на сторінку, текст терміналу ще читається (≈8–9 pt)
    body, n = figures(SECTIONS9, width=11 * cm, max_h=19 * cm, head=[p("Хід виконання", H1)])
    story = [
        p(UNIVERSITY, CENTER),
        p(INSTITUTE, CENTER),
        Spacer(1, 4 * cm),
        p("Лабораторна робота №9", TITLE),
        p("з курсу «Технології DevOps»", CENTER),
        Spacer(1, 1 * cm),
        p("<b>Балансування навантаження та забезпечення доступності хмарного застосунку</b>", CENTER),
        p("Предметна область: система бронювання коворкінгу", CENTER),
        Spacer(1, 4 * cm),
        p(f"Виконав: студент групи {GROUP_LAB9}", RIGHT),
        p(STUDENT, RIGHT),
        Spacer(1, 1 * cm),
        p(f"Репозиторій: {REPO}", CENTER),
        PageBreak(),
        p("Мета", H1),
        p(GOAL9),
        p("Архітектура", H1),
        Preformatted(ARCH9, CODE),
        *[p(t) for t in ARCH9_TEXT],
        p("Послідовність запуску і дослідження", H1),
        *[p(f"{i}. {s}") for i, s in enumerate(STEPS9, 1)],
        PageBreak(),
        *body,
        KeepTogether([p("Висновок", H1), *[p(t) for t in CONCLUSION9]]),
    ]
    write("lab9-loadbalancing.pdf", "Лабораторна робота №9", story, n)


def main():
    labs = {"8": lab8, "9": lab9}
    for key in sys.argv[1:] or labs:
        labs[key]()


if __name__ == "__main__":
    main()
