"""
API Gateway Lambda handler — BD Change Callback
================================================
Receives the asynchronous carrier/IIEX validation response after a BD change
request has been submitted.  This endpoint (POST /bd-change-callback) is called
by IIEX or the insurance carrier once they have finished processing.

Flow
----
1. Validate the inbound CarrierResponse payload.
2. Update the `transact` DynamoDB table with the validation result.
3. Publish a TransactionUpdate event to EventBridge so the frontend
   can show the final approval/rejection status.

Request
-------
Headers:
  transactionId  (required, UUID) – identifies the in-flight transaction
  correlationId  (optional)

Body (CarrierResponse schema):
  carrierId        string   required
  policyNumber     string   required
  validationResult string   required  enum: approved | rejected
  rejectionReason  string   optional
  validationDetails object  optional
  effectiveDate    string   optional  (ISO 8601 date, if approved)
  additionalData   object   optional

Response
--------
200  { code: "RECEIVED", transactionId, message }
400  validation error
500  internal error

Environment variables
---------------------
TRANSACT_TABLE          DynamoDB table name         (default: "transact")
EVENTBRIDGE_BUS_NAME    EventBridge custom bus name (default: "hackathon-events")
AWS_REGION              AWS region                  (default: "us-east-1")
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TRANSACT_TABLE = os.environ.get("TRANSACT_TABLE", "transact")
EVENTBRIDGE_BUS_NAME = os.environ.get("EVENTBRIDGE_BUS_NAME", "hackathon-events")
REGION = os.environ.get("AWS_REGION", "us-east-1")

VALID_RESULTS = {"approved", "rejected"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": (
                "Content-Type,X-Amz-Date,Authorization,"
                "X-Api-Key,X-Amz-Security-Token,transactionId,correlationId"
            ),
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


def _error(code: str, message: str, status_code: int = 400) -> dict:
    return _response(status_code, {"code": code, "message": message})


# ---------------------------------------------------------------------------
# Step 1 – persist result to DynamoDB
# ---------------------------------------------------------------------------

def update_transact_record(
    transaction_id: str,
    callback_body: dict,
    new_status: str,
) -> None:
    """Write the carrier validation result to the transact table."""
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(TRANSACT_TABLE)

    now = _now()
    validation_result = callback_body.get("validationResult")
    notes = (
        f"Carrier validation: {validation_result}"
        + (f" — {callback_body['rejectionReason']}" if callback_body.get("rejectionReason") else "")
    )

    table.update_item(
        Key={"pk": transaction_id, "sk": "TRANSACTION"},
        UpdateExpression=(
            "SET #status      = :status, "
            "#updated         = :updated, "
            "#bd_callback     = :callback, "
            "#history         = list_append(if_not_exists(#history, :empty), :hist)"
        ),
        ExpressionAttributeNames={
            "#status":      "current-status",
            "#updated":     "updated-at",
            "#bd_callback": "bd-change-callback",
            "#history":     "status-history",
        },
        ExpressionAttributeValues={
            ":status":   new_status,
            ":updated":  now,
            ":callback": callback_body,
            ":empty":    [],
            ":hist":     [{"status": new_status, "timestamp": now, "notes": notes}],
        },
    )
    logger.info(
        "Transact record updated — transactionId=%s status=%s",
        transaction_id, new_status,
    )


# ---------------------------------------------------------------------------
# Step 2 – fire EventBridge event
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
# Lambda entry point
# ---------------------------------------------------------------------------

def handler(event: dict, context) -> dict:
    """API Gateway proxy handler for POST /bd-change-callback."""

    # Handle CORS preflight
    if event.get("httpMethod") == "OPTIONS":
        return _response(200, {})

    # --- Extract and validate transaction ID ---
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    transaction_id = headers.get("transactionid")
    if not transaction_id:
        return _error("MISSING_HEADER", "transactionId header is required")

    # --- Parse body ---
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _error("INVALID_PAYLOAD", "Request body must be valid JSON")

    # --- Validate required fields ---
    required = ["carrierId", "policyNumber", "validationResult"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return _error(
            "VALIDATION_ERROR",
            f"Missing required fields: {', '.join(missing)}",
        )

    validation_result = body.get("validationResult", "").lower()
    if validation_result not in VALID_RESULTS:
        return _error(
            "VALIDATION_ERROR",
            f"validationResult must be one of: {', '.join(sorted(VALID_RESULTS))}",
        )

    logger.info(
        "BD change callback received — transactionId=%s carrierId=%s result=%s",
        transaction_id, body.get("carrierId"), validation_result,
    )

    # --- Map result to DB status and EventBridge verb ---
    if validation_result == "approved":
        new_status = "CARRIER_APPROVED"
        verb = "transfer_approved"
    else:
        new_status = "CARRIER_REJECTED"
        verb = "transfer_rejected"

    try:
        update_transact_record(transaction_id, body, new_status)
        fire_eventbridge_event(transaction_id, verb)
    except Exception as exc:
        logger.error(
            "Error handling BD change callback — transactionId=%s: %s",
            transaction_id, exc, exc_info=True,
        )
        return _error("INTERNAL_ERROR", "An internal error occurred", 500)

    return _response(200, {
        "code": "RECEIVED",
        "message": f"BD change callback processed — result: {validation_result}",
        "transactionId": transaction_id,
    })
