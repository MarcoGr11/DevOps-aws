"""Збирає PDF-звіт лаби 8 з кадрів reports/screens/: .venv/bin/python reports/build_report.py"""

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
TITLE = ParagraphStyle("title", parent=H1, fontSize=20, leading=26, alignment=TA_CENTER)
CENTER = ParagraphStyle("center", parent=BODY, alignment=TA_CENTER)
CAPTION = ParagraphStyle("caption", parent=BODY, fontSize=10, alignment=TA_CENTER, spaceBefore=4)
CODE = ParagraphStyle("code", fontName="Menlo", fontSize=8, leading=10.5, spaceAfter=8)

FRAMES = [
    (
        "8-01-localstack-health",
        "LocalStack у Docker і його health-check",
        "Контейнер localstack/localstack:4.9.2 у стані healthy на 127.0.0.1:4566; сервіси lambda, "
        "apigateway, dynamodb, iam, logs, cloudwatch — running.",
    ),
    (
        "8-02-project-structure",
        "Структура проєкту і маршрутизація в Lambda",
        "Код функції, тести, скрипти розгортання, Makefile. lambda_handler вибирає обробник за "
        "event.resource та event.httpMethod; помилки сховища дають 500.",
    ),
    (
        "8-03-deploy",
        "Перше розгортання ./deploy.sh",
        "За 7 кроків створено таблицю, zip, IAM-роль, функцію, REST API з 5 методами AWS_PROXY, "
        "дозвіл на виклик і stage dev; надруковано URL і відповідь /health.",
    ),
    (
        "8-04-resources",
        "Створені ресурси в LocalStack",
        "Таблиця bookings, функція bookings-api (python3.12, TABLE_NAME), REST API bookings-api "
        "і його ресурси /health, /bookings, /bookings/{id} з методами.",
    ),
    (
        "8-05-post-booking",
        "Створення бронювання: POST /bookings",
        "201 CREATED, Content-Type: application/json; у тілі запис зі згенерованими id та created_at.",
    ),
    (
        "8-06-get-booking",
        "Отримання бронювання: GET /bookings/{id}",
        "200 OK і той самий запис, прочитаний з DynamoDB.",
    ),
    (
        "8-07-list-bookings",
        "Список бронювань: GET /bookings",
        "Після другого POST список містить 2 записи, count = 2.",
    ),
    (
        "8-08-dynamodb-scan",
        "Записи безпосередньо в DynamoDB",
        "awslocal dynamodb scan показує обидва записи з типами атрибутів (S).",
    ),
    (
        "8-09-delete-then-404",
        "Видалення: DELETE /bookings/{id}, потім GET",
        'DELETE повертає 200 {"deleted": id}, наступний GET — 404 booking not found.',
    ),
    (
        "8-10-smoke-test",
        "Автоматична перевірка ./smoke-test.sh",
        "Усі 11 перевірок (health, POST, GET, список, DELETE, 404, 400) пройдено, exit code 0.",
    ),
    (
        "8-11-pytest-ruff",
        "Юніт-тести і лінтер",
        "pytest: 16 passed (CRUD, валідація, 400/404/500, Decimal); ruff check і ruff format --check чисті.",
    ),
    (
        "8-12-deploy-idempotent",
        "Повторний запуск ./deploy.sh (ідемпотентність)",
        "Таблиця, роль, функція і API «вже існують» (той самий API id), оновлено лише код і "
        "створено новий deployment.",
    ),
    (
        "8-13-bad-request-400",
        "Обробка некоректного тіла запиту",
        "Битий JSON → 400 invalid JSON body; порожній user, неіснуюча дата 2026-02-30 і slot "
        "12:00-10:00 → 400 validation failed з переліком помилок.",
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
    "./smoke-test.sh — end-to-end перевірка через curl і jq;",
    "./destroy.sh — видалення ресурсів; docker compose down — зупинка LocalStack.",
]


def p(text, style=BODY):
    return Paragraph(text, style)


def figure(n, name, title, seen, max_h=10.5 * cm):
    path = SCREENS / f"{name}.png"
    img = Image(str(path))
    scale = min(17 * cm / img.imageWidth, max_h / img.imageHeight)
    img.drawWidth, img.drawHeight = img.imageWidth * scale, img.imageHeight * scale
    return KeepTogether([img, p(f"Рис. {n}. {title}", CAPTION), p(f"<b>Що видно:</b> {seen}"), Spacer(1, 10)])


def main():
    story = [
        Spacer(1, 5 * cm),
        p("Лабораторна робота №8", TITLE),
        p("з курсу «Технології DevOps»", CENTER),
        Spacer(1, 1 * cm),
        p("<b>Розгортання serverless-застосунку в локальному AWS-середовищі (LocalStack)</b>", CENTER),
        p("Предметна область: система бронювання коворкінгу", CENTER),
        Spacer(1, 4 * cm),
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
            "стандартний endpoint. Образ LocalStack закріплено на 4.9.2: latest (2026.11) без "
            "LOCALSTACK_AUTH_TOKEN завершується з помилкою активації ліцензії."
        ),
        p("Послідовність розгортання", H1),
        *[p(f"{i}. {s}") for i, s in enumerate(DEPLOY_STEPS, 1)],
        PageBreak(),
        p("Хід виконання", H1),
    ]
    story += [figure(i, *frame) for i, frame in enumerate(FRAMES, 1)]
    story.append(
        KeepTogether(
            [
                p("Висновок", H1),
                p(
                    "У LocalStack 4.9.2 розгорнуто serverless-застосунок: REST API в API Gateway з п'ятьма "
                    "маршрутами викликає Lambda-функцію на Python 3.12, яка зберігає бронювання в DynamoDB. "
                    "Створення (201), отримання (200/404), список і видалення (200/404) та валідація (400) "
                    "перевірені curl-ом вручну і скриптом smoke-test.sh; логіку покрито 16 юніт-тестами. "
                    "Розгортання виконується одним ідемпотентним скриптом deploy.sh — повторний запуск не "
                    "створює дублікатів. Виявлено обмеження LocalStack: тіло з Content-Type "
                    "application/x-www-form-urlencoded перекодовується, тому клієнти мають надсилати "
                    "application/json."
                ),
            ]
        )
    )
    doc = SimpleDocTemplate(
        str(HERE / "lab8-localstack.pdf"),
        pagesize=A4,
        title="Лабораторна робота №8",
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
    )
    doc.build(story)
    print("reports/lab8-localstack.pdf")


if __name__ == "__main__":
    main()
