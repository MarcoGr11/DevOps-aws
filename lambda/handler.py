"""Lambda-обробник HTTP-запитів API бронювання коворкінгу (API Gateway, AWS_PROXY)."""

import json
import os
import re
import socket
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import boto3

TABLE_NAME = os.environ.get("TABLE_NAME", "bookings")
REQUIRED_FIELDS = ("user", "room", "date", "slot")
SLOT_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_table = None


def _endpoint_url():
    # Усередині Lambda-контейнера LocalStack "localhost" — це сам контейнер функції,
    # тому до DynamoDB треба йти на контейнер LocalStack. LocalStack 4.9 сам передає у
    # функцію AWS_ENDPOINT_URL=http://<IP LocalStack у docker-мережі>:4566 (перевірено
    # docker inspect), а старіші версії — лише LOCALSTACK_HOSTNAME + EDGE_PORT.
    # У справжньому AWS жодної з цих змінних немає -> None -> стандартний endpoint.
    if os.environ.get("AWS_ENDPOINT_URL"):
        return os.environ["AWS_ENDPOINT_URL"]
    host = os.environ.get("LOCALSTACK_HOSTNAME")
    if host:
        return f"http://{host}:{os.environ.get('EDGE_PORT', '4566')}"
    return None


def get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", endpoint_url=_endpoint_url()).Table(TABLE_NAME)
    return _table


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def response(status, body=None):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": "" if body is None else json.dumps(body, default=_json_default, ensure_ascii=False),
    }


def validate(data):
    """Повертає список помилок валідації (порожній, якщо все гаразд)."""
    if not isinstance(data, dict):
        return ["body must be a JSON object"]
    # кожне поле перевіряється окремо, щоб клієнт одразу побачив усі помилки
    present = {f for f in REQUIRED_FIELDS if isinstance(data.get(f), str) and data[f].strip()}
    errors = [f"'{f}' is required" for f in REQUIRED_FIELDS if f not in present]
    if "date" in present:
        if not DATE_RE.match(data["date"]):
            errors.append("'date' must be YYYY-MM-DD")
        else:
            try:
                datetime.strptime(data["date"], "%Y-%m-%d")
            except ValueError:
                errors.append("'date' is not a valid calendar date")
    if "slot" in present:
        if not SLOT_RE.match(data["slot"]):
            errors.append("'slot' must be HH:MM-HH:MM")
        elif data["slot"][:5] >= data["slot"][6:]:
            errors.append("'slot' start must be before end")
    return errors


def create_booking(event):
    try:
        data = json.loads(event.get("body") or "")
    except (json.JSONDecodeError, TypeError):
        return response(400, {"error": "invalid JSON body"})
    errors = validate(data)
    if errors:
        return response(400, {"error": "validation failed", "details": errors})
    item = {f: data[f].strip() for f in REQUIRED_FIELDS}
    item["id"] = str(uuid.uuid4())
    item["created_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    get_table().put_item(Item=item)
    return response(201, item)


def get_booking(booking_id):
    item = get_table().get_item(Key={"id": booking_id}).get("Item")
    return response(200, item) if item else response(404, {"error": "booking not found"})


def list_bookings():
    # ponytail: scan без пагінації (до 1 МБ даних) — для демо достатньо, далі LastEvaluatedKey
    items = get_table().scan().get("Items", [])
    items.sort(key=lambda i: i.get("created_at", ""))
    return response(200, {"items": items, "count": len(items)})


def delete_booking(booking_id):
    # ReturnValues=ALL_OLD дозволяє одним запитом дізнатися, чи існував запис
    old = get_table().delete_item(Key={"id": booking_id}, ReturnValues="ALL_OLD").get("Attributes")
    return response(200, {"deleted": booking_id}) if old else response(404, {"error": "booking not found"})


def health():
    # instance: заготовка для лаби 9 (кілька екземплярів за балансувальником)
    return response(200, {"status": "ok", "instance": os.environ.get("INSTANCE_ID", socket.gethostname())})


def lambda_handler(event, context):
    method = event.get("httpMethod")
    resource = event.get("resource")
    booking_id = (event.get("pathParameters") or {}).get("id")
    try:
        if resource == "/health" and method == "GET":
            return health()
        if resource == "/bookings" and method == "POST":
            return create_booking(event)
        if resource == "/bookings" and method == "GET":
            return list_bookings()
        if resource == "/bookings/{id}" and method == "GET":
            return get_booking(booking_id)
        if resource == "/bookings/{id}" and method == "DELETE":
            return delete_booking(booking_id)
    except Exception as exc:  # помилки DynamoDB тощо -> 500, деталі в CloudWatch Logs
        print(f"ERROR {method} {resource}: {exc!r}")
        return response(500, {"error": "internal error"})
    return response(404, {"error": f"route {method} {resource} not found"})
