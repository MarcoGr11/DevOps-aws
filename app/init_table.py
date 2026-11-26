"""Одноразова ідемпотентна ініціалізація таблиці DynamoDB для лаби 9 (init-контейнер)."""

import os

import boto3
from botocore.exceptions import ClientError

name = os.environ.get("TABLE_NAME", "bookings")
ddb = boto3.client("dynamodb", endpoint_url=os.environ["AWS_ENDPOINT_URL"])
try:
    ddb.create_table(
        TableName=name,
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        BillingMode="PAY_PER_REQUEST",
    )
    print(f"table '{name}': created")
except ClientError as exc:
    if exc.response["Error"]["Code"] != "ResourceInUseException":
        raise
    print(f"table '{name}': already exists")
ddb.get_waiter("table_exists").wait(TableName=name)
