import json

import pytest

import handler


class FakeTable:
    """Мінімальна заглушка DynamoDB Table: зберігає записи у словнику."""

    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[Item["id"]] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(Key["id"])
        return {"Item": item} if item else {}

    def scan(self):
        return {"Items": list(self.items.values())}

    def delete_item(self, Key, ReturnValues):
        old = self.items.pop(Key["id"], None)
        return {"Attributes": old} if old else {}


@pytest.fixture(autouse=True)
def table(monkeypatch):
    fake = FakeTable()
    monkeypatch.setattr(handler, "_table", fake)
    return fake


def call(method, resource, body=None, booking_id=None):
    event = {
        "httpMethod": method,
        "resource": resource,
        "pathParameters": {"id": booking_id} if booking_id else None,
        "body": body if body is None or isinstance(body, str) else json.dumps(body),
    }
    resp = handler.lambda_handler(event, None)
    assert resp["headers"]["Content-Type"] == "application/json"
    return resp["statusCode"], json.loads(resp["body"]) if resp["body"] else None


VALID = {"user": "olena", "room": "A-101", "date": "2026-12-01", "slot": "10:00-12:00"}


def test_crud_flow(table):
    status, created = call("POST", "/bookings", VALID)
    assert status == 201
    assert created["id"] and created["created_at"] and created["room"] == "A-101"

    assert call("GET", "/bookings/{id}", booking_id=created["id"]) == (200, created)

    status, listing = call("GET", "/bookings")
    assert status == 200 and listing["count"] == 1

    assert call("DELETE", "/bookings/{id}", booking_id=created["id"])[0] == 200
    assert call("GET", "/bookings/{id}", booking_id=created["id"])[0] == 404
    assert call("DELETE", "/bookings/{id}", booking_id=created["id"])[0] == 404
    assert table.items == {}


@pytest.mark.parametrize("body", ["{not json", "", None])
def test_bad_json_is_400(body):
    status, data = call("POST", "/bookings", body)
    assert status == 400 and data["error"] == "invalid JSON body"


@pytest.mark.parametrize(
    "patch",
    [
        {"user": ""},
        {"room": None},
        {"date": "01.12.2026"},
        {"date": "2026-02-30"},
        {"slot": "10-12"},
        {"slot": "12:00-10:00"},
    ],
)
def test_validation_errors(patch, table):
    status, data = call("POST", "/bookings", {**VALID, **patch})
    assert status == 400 and data["details"]
    assert table.items == {}


def test_body_must_be_object():
    assert call("POST", "/bookings", "[1, 2]")[0] == 400


def test_health():
    status, data = call("GET", "/health")
    assert status == 200 and data["status"] == "ok" and data["instance"]


def test_unknown_route_is_404():
    assert call("PUT", "/bookings")[0] == 404


def test_decimal_is_serialized(table):
    table.items["x"] = {"id": "x", "seats": handler.Decimal("2"), "price": handler.Decimal("1.5")}
    assert call("GET", "/bookings/{id}", booking_id="x")[1] == {"id": "x", "seats": 2, "price": 1.5}


def test_storage_error_is_500(table, monkeypatch):
    def boom(**_):
        raise RuntimeError("dynamodb down")

    monkeypatch.setattr(table, "put_item", boom)
    assert call("POST", "/bookings", VALID)[0] == 500


def test_all_validation_errors_reported_at_once():
    status, data = call(
        "POST", "/bookings", {"user": "", "room": "A-101", "date": "2026-02-30", "slot": "12:00-10:00"}
    )
    assert status == 400
    assert data["details"] == [
        "'user' is required",
        "'date' is not a valid calendar date",
        "'slot' start must be before end",
    ]
