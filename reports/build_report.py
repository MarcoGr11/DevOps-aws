"""Збирає PDF-звіт лаби 8 зі знімків екрана reports/screens/: .venv/bin/python reports/build_report.py"""

import sys
from pathlib import Path

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
)

STUDENT = "Бабин Богдан Олегович"
GROUP = "443a"

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
SECTIONS = [
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


def p(text, style=BODY):
    return Paragraph(text, style)


def frame_files(code):
    return sorted(SCREENS.glob(f"{code}*.png"))


def figure(n, path, title, seen, head=()):
    img = Image(str(path))
    # на всю ширину сторінки, щоб текст терміналу читався; дуже високі кадри обмежуємо висотою
    scale = min(17 * cm / img.imageWidth, 21 * cm / img.imageHeight)
    img.drawWidth, img.drawHeight = img.imageWidth * scale, img.imageHeight * scale
    parts = [*head, img, p(f"Рис. {n}. {title}", CAPTION)]  # заголовок розділу — разом з першим рисунком
    if seen:
        parts.append(p(f"<b>Що видно:</b> {seen}"))
    return KeepTogether([*parts, Spacer(1, 10)])


def main():
    missing = [code for _, frames in SECTIONS for code, _, _ in frames if not frame_files(code)]
    if missing:
        sys.exit(f"немає знімків у reports/screens/: {', '.join(missing)}")

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
        p("Репозиторій: github.com/MarcoGr11/DevOps-aws", CENTER),
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
    ]
    n = 0
    for heading, frames in SECTIONS:
        head = [p(heading, H2)]
        for code, title, seen in frames:
            files = frame_files(code)
            for k, path in enumerate(files, 1):
                n += 1
                part = f" (частина {k} з {len(files)})" if len(files) > 1 else ""
                story.append(figure(n, path, title + part, seen if k == len(files) else "", head))
                head = []
    story.append(KeepTogether([p("Висновок", H1), *[p(t) for t in CONCLUSION]]))

    doc = SimpleDocTemplate(
        str(HERE / "lab8-localstack.pdf"),
        pagesize=A4,
        title="Лабораторна робота №8",
        author=STUDENT,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
    )
    doc.build(story)
    print(f"reports/lab8-localstack.pdf: {n} рисунків")


if __name__ == "__main__":
    main()
