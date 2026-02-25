"""
SQS Lambda handler — BD Change (Transfer Request)
===================================================
Triggered by messages on the BD_CHANGE SQS queue.

Flow
----
1. Parse the SQS message produced by the /trigger-transfer-request API route.
2. POST the BdChangeRequest to the internal IIEX/DTCC API
   at {INTERNAL_API_BASE_URL}/bd-change.
3. Write the initial "pending" state back to the `transact` DynamoDB table.
4. Publish a TransactionUpdate event to EventBridge so the frontend
   knows the transfer request has been submitted.

Note: the actual approval/rejection arrives asynchronously via the
api-bd-change-callback Lambda, which handles the /bd-change-callback
endpoint called by IIEX or the carrier.

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
from datetime import datetime, timezone

import boto3
import urllib3

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

_http = urllib3.PoolManager()


def call_bd_change_api(transaction_id: str, request_data: dict) -> dict:
    """POST /servicing-agent-changes/create on the internal API and return the parsed response."""
    url = f"{INTERNAL_API_BASE_URL}/servicing-agent-changes/create"

    resp = _http.request(
        "POST",
        url,
        body=json.dumps(request_data).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "requestId": transaction_id,
        },
        timeout=30,
    )

    if resp.status >= 400:
        raise RuntimeError(
            f"BD change API returned HTTP {resp.status}: {resp.data.decode('utf-8')}"
        )

    return json.loads(resp.data.decode("utf-8"))


# ---------------------------------------------------------------------------
# Step 2 – persist to DynamoDB
# ---------------------------------------------------------------------------

def update_transact_record(
    transaction_id: str,
    request_data: dict,
    api_response: dict,
) -> None:
    """Record the BD change submission in the transact table."""
    code = api_response.get("code", "UNKNOWN")
    # The bd-change endpoint almost always responds DEFERRED/RECEIVED because
    # carrier validation is async.  We set status accordingly.
    if code == "IMMEDIATE":
        new_status = "BD_CHANGE_SUBMITTED"
    else:
        new_status = "BD_CHANGE_PENDING"

    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(TRANSACT_TABLE)

    now = _now()
    table.update_item(
        Key={"pk": transaction_id, "sk": "TRANSACTION"},
        UpdateExpression=(
            "SET #status       = :status, "
            "#updated          = :updated, "
            "#bd_request       = :bd_request, "
            "#bd_ack           = :bd_ack, "
            "#history          = list_append(if_not_exists(#history, :empty), :hist)"
        ),
        ExpressionAttributeNames={
            "#status":     "current-status",
            "#updated":    "updated-at",
            "#bd_request": "bd-change-request",
            "#bd_ack":     "bd-change-acknowledgement",
            "#history":    "status-history",
        },
        ExpressionAttributeValues={
            ":status":     new_status,
            ":updated":    now,
            ":bd_request": request_data,
            ":bd_ack":     api_response,
            ":empty":      [],
            ":hist":       [{"status": new_status, "timestamp": now,
                             "notes": "BD change request submitted to IIEX/carrier"}],
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

    logger.info("Processing BD change — transactionId=%s", transaction_id)

    api_response = call_bd_change_api(transaction_id, request_data)
    logger.info(
        "BD change API response — code=%s transactionId=%s",
        api_response.get("code"), transaction_id,
    )

    update_transact_record(transaction_id, request_data, api_response)
    fire_eventbridge_event(transaction_id, "transfer_request_submitted")


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
