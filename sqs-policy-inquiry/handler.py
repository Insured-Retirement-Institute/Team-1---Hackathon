"""
SQS Lambda handler — Policy Inquiry
====================================
Triggered by messages on the POLICY_INQUIRY SQS queue.

Flow
----
1. Parse the SQS message produced by the /trigger-policy-inquiry API route.
2. POST the PolicyInquiryRequest to the internal IIEX/DTCC API
   at {INTERNAL_API_BASE_URL}/policy-inquiry.
3. Write the API response back to the `transact` DynamoDB table
   (keyed on transactionId).
4. Publish a TransactionUpdate event to EventBridge so the frontend
   knows to refresh.

Environment variables
---------------------
INTERNAL_API_BASE_URL   Base URL of the internal API (required, no trailing slash)
TRANSACT_TABLE          DynamoDB table name              (default: "transact")
EVENTBRIDGE_BUS_NAME    EventBridge custom bus name      (default: "hackathon-events")
AWS_REGION              AWS region                       (default: "us-east-1")
"""

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

INTERNAL_API_BASE_URL = os.environ.get(
    "INTERNAL_API_BASE_URL",
    "https://3wn6kzs5h6.execute-api.us-east-1.amazonaws.com/prod",
).rstrip("/")
TRANSACT_TABLE = os.environ.get("TRANSACT_TABLE", "transact")
EVENTBRIDGE_BUS_NAME = os.environ.get("EVENTBRIDGE_BUS_NAME", "hackathon-events")
REGION = os.environ.get("AWS_REGION", "us-east-1")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Step 1 – call internal API
# ---------------------------------------------------------------------------

def call_policy_inquiry_api(transaction_id: str, request_data: dict) -> dict:
    """POST /policy-inquiry on the internal API and return the parsed response."""
    url = f"{INTERNAL_API_BASE_URL}/policy-inquiries/create"
    body_bytes = json.dumps(request_data).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body_bytes,
        headers={
            "Content-Type": "application/json",
            "requestId": transaction_id,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        raise RuntimeError(
            f"Policy inquiry API returned HTTP {exc.code}: {raw}"
        ) from exc


# ---------------------------------------------------------------------------
# Step 2 – persist to DynamoDB
# ---------------------------------------------------------------------------

def update_transact_record(transaction_id: str, api_response: dict) -> None:
    """Upsert the policy inquiry result into the transact table."""
    code = api_response.get("code", "UNKNOWN")
    # Treat IMMEDIATE / RECEIVED as a data-received status; anything else is deferred
    if code in ("IMMEDIATE", "RECEIVED"):
        new_status = "POLICY_INFO_RECEIVED"
    else:
        new_status = "POLICY_INQUIRY_DEFERRED"

    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(TRANSACT_TABLE)

    now = _now()
    table.update_item(
        Key={"pk": transaction_id, "sk": "TRANSACTION"},
        UpdateExpression=(
            "SET #status   = :status, "
            "#updated      = :updated, "
            "#pi_response  = :response, "
            "#history      = list_append(if_not_exists(#history, :empty), :hist)"
        ),
        ExpressionAttributeNames={
            "#status":      "current-status",
            "#updated":     "updated-at",
            "#pi_response": "policy-inquiry-response",
            "#history":     "status-history",
        },
        ExpressionAttributeValues={
            ":status":   new_status,
            ":updated":  now,
            ":response": api_response,
            ":empty":    [],
            ":hist":     [{"status": new_status, "timestamp": now,
                           "notes": "Policy inquiry API response saved"}],
        },
    )
    logger.info(
        "Transact record updated — transactionId=%s status=%s",
        transaction_id, new_status,
    )


# ---------------------------------------------------------------------------
# Step 3 – fire EventBridge event
# ---------------------------------------------------------------------------

def fire_eventbridge_event(transaction_id: str, verb: str) -> None:
    """Publish a UI-facing TransactionUpdate event to EventBridge."""
    events = boto3.client("events", region_name=REGION)
    detail = {
        "verb": verb,
        "transactionId": transaction_id,
        "timestamp": _now(),
    }
    events.put_events(Entries=[{
        "Source":       "hackathon.broker-dealer",
        "DetailType":   "TransactionUpdate",
        "Detail":       json.dumps(detail),
        "EventBusName": EVENTBRIDGE_BUS_NAME,
    }])
    logger.info(
        "EventBridge event fired — transactionId=%s verb=%s",
        transaction_id, verb,
    )


# ---------------------------------------------------------------------------
# Per-record processor
# ---------------------------------------------------------------------------

def process_record(record: dict) -> None:
    body = json.loads(record["body"])
    transaction_id = body["requestId"]
    request_data   = body["requestData"]

    logger.info("Processing policy inquiry — transactionId=%s", transaction_id)

    api_response = call_policy_inquiry_api(transaction_id, request_data)
    logger.info(
        "Policy inquiry API response — code=%s transactionId=%s",
        api_response.get("code"), transaction_id,
    )

    update_transact_record(transaction_id, api_response)
    fire_eventbridge_event(transaction_id, "policy_info_received")


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def handler(event: dict, context) -> dict:
    """
    SQS event source mapping handler.

    Returns a batchItemFailures list so Lambda/SQS can re-drive individual
    failed messages without poisoning the whole batch.
    """
    records = event.get("Records", [])
    logger.info("Received %d SQS record(s)", len(records))

    failures = []
    for record in records:
        message_id = record.get("messageId", "unknown")
        try:
            process_record(record)
        except Exception as exc:
            logger.error(
                "Failed to process record — messageId=%s: %s",
                message_id, exc, exc_info=True,
            )
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}
