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
3. Publish a RequestUpdate event to EventBridge so the frontend
   can show the final approval/rejection status.

Request
-------
Headers:
  requestId  (required, ULID) – identifies the in-flight transaction
  correlationId  (optional)

Body (ServicingAgentChangeResponse schema v0.1.1):
  policies         array    required  list of PolicyStatus objects
    policyNumber   string   required
    status         string   required  enum: approved | rejected | pendingAppointment
    errors         array    optional  list of ServicingAgentChangeError objects
    effectiveDate  string   optional  (ISO 8601 date, if approved)
  context          string   optional  AI-generated insights

Response
--------
200  { code: "RECEIVED", requestId, message }
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

VALID_STATUSES = {"approved", "rejected", "pendingAppointment"}


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
                "X-Api-Key,X-Amz-Security-Token,requestId,correlationId"
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
    request_id: str,
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
        Key={"pk": request_id, "sk": "REQUEST"},
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
        "Transact record updated — requestId=%s status=%s",
        request_id, new_status,
    )


# ---------------------------------------------------------------------------
# Step 2 – fire EventBridge event
# ---------------------------------------------------------------------------

def fire_eventbridge_event(request_id: str, verb: str) -> None:
    """Publish a UI-facing RequestUpdate event to EventBridge."""
    events = boto3.client("events", region_name=REGION)
    detail = {
        "verb": verb,
        "requestId": request_id,
        "timestamp": _now(),
    }
    events.put_events(Entries=[{
        "Source":       "hackathon.broker-dealer",
        "DetailType":   "RequestUpdate",
        "Detail":       json.dumps(detail),
        "EventBusName": EVENTBRIDGE_BUS_NAME,
    }])
    logger.info(
        "EventBridge event fired — requestId=%s verb=%s",
        request_id, verb,
    )


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def handler(event: dict, context) -> dict:
    """API Gateway proxy handler for POST /bd-change-callback."""

    # Handle CORS preflight
    if event.get("httpMethod") == "OPTIONS":
        return _response(200, {})

    # --- Extract and validate request ID (ULID per spec v0.1.1) ---
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    request_id = headers.get("requestid")
    if not request_id:
        return _error("MISSING_HEADER", "requestId header is required")

    # --- Parse body ---
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _error("INVALID_PAYLOAD", "Request body must be valid JSON")

    # --- Validate required fields (ServicingAgentChangeResponse schema v0.1.1) ---
    policies = body.get("policies")
    if not policies or not isinstance(policies, list):
        return _error("VALIDATION_ERROR", "policies array is required")

    for p in policies:
        if not p.get("policyNumber"):
            return _error("VALIDATION_ERROR", "Each policy must have a policyNumber")
        status = p.get("status", "")
        if status not in VALID_STATUSES:
            return _error(
                "VALIDATION_ERROR",
                f"policy status must be one of: {', '.join(sorted(VALID_STATUSES))}",
            )

    logger.info(
        "Servicing agent change callback received — requestId=%s policies=%d",
        request_id, len(policies),
    )

    # --- Determine overall result for DB status and EventBridge verb ---
    statuses = {p.get("status") for p in policies}
    if statuses == {"approved"}:
        new_status = "CARRIER_APPROVED"
        verb = "transfer_approved"
    elif "rejected" in statuses:
        new_status = "CARRIER_REJECTED"
        verb = "transfer_rejected"
    else:
        new_status = "CARRIER_PENDING_APPOINTMENT"
        verb = "transfer_pending_appointment"

    try:
        update_transact_record(request_id, body, new_status)
        fire_eventbridge_event(request_id, verb)
    except Exception as exc:
        logger.error(
            "Error handling BD change callback — requestId=%s: %s",
            request_id, exc, exc_info=True,
        )
        return _error("INTERNAL_ERROR", "An internal error occurred", 500)

    return _response(200, {
        "code": "RECEIVED",
        "message": f"BD change callback processed — result: {new_status}",
        "requestId": request_id,
    })
