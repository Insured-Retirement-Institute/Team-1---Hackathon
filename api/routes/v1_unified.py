"""
v1 Unified Brokerage Transfer API — Agentic endpoints.

Implements the async 202 + callback pattern for AI-powered endpoints.
Policy inquiry is owned by Sasha — not implemented here.

Blueprints:
  servicing_agent_changes_bp → /v1/servicing-agent-changes/
  transfer_notifications_bp  → /v1/transfer-notifications/
  status_bp                  → /v1/status/
"""

from flask import request, Blueprint
from datetime import datetime, date
from urllib.request import urlopen, Request as URLRequest
from urllib.error import HTTPError, URLError
import logging
import json
import os
import threading

from helpers_v1 import (
    validate_request_id,
    ok_response,
    deferred_response,
    acknowledgment_response,
    error_response,
)

# Reuse existing business logic from insurance_carrier
from routes.insurance_carrier import (
    lookup_policy,
    lookup_policy_from_table,
    _call_carrier_agent,
    CARRIER_CONFIGS,
)
from lib.utils.dynamodb_utils import put_item, get_item, scan_items

logger = logging.getLogger(__name__)

# Where to POST async results. Set via env var; blank = log only (no callback).
CALLBACK_BASE_URL = os.environ.get("CALLBACK_BASE_URL", "")

# DynamoDB table for storing received async responses
REPLY_TABLE = "distributor"
REPLY_PK_PREFIX = "CHANGE_REPLY#"

# ── Blueprints ──────────────────────────────────────────────────────────────

servicing_agent_changes_bp = Blueprint("v1-servicing-agent-changes", __name__)
transfer_notifications_bp = Blueprint("v1-transfer-notifications", __name__)
status_bp = Blueprint("v1-status", __name__)


# ── Shared helpers ──────────────────────────────────────────────────────────

# Map AgentCore NIGO deficiency codes → v1 spec ServicingAgentChangeError codes
_NIGO_CODE_MAP = {
    "SIGNATURE-MISSING": "carrierSpecific",
    "SIGNATURE-STALE": "carrierSpecific",
    "SAME-PRODUCER": "carrierSpecific",
    "PRODUCER-INACTIVE": "carrierSpecific",
    "NOT-APPOINTED": "notAppointedResubmit",
    "NO-EO": "carrierSpecific",
    "NOT-LICENSED": "notLicensed",
    "BD-NOT-CONTRACTED": "noSellingServicingAgreement",
    "POLICY-NOT-FOUND": "policyNotInForce",
}

ALL_US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]


def _build_change_response(determination, carrier_info, policy_numbers, request_id):
    """
    Map an AgentCore IGO/NIGO determination to a v1 ServicingAgentChangeResponse.
    """
    det_value = determination.get("determination", "")
    today = date.today().isoformat()
    policy_statuses = []

    for pn in policy_numbers:
        if det_value == "IGO":
            policy_statuses.append({
                "policyNumber": pn,
                "status": "approved",
                "effectiveDate": today,
                "errors": [],
            })
        else:
            errors = []
            for deficiency in determination.get("deficiencies", []):
                nigo_code = deficiency.get("nigo-code", "")
                spec_code = _NIGO_CODE_MAP.get(nigo_code, "carrierSpecific")
                errors.append({
                    "errorCode": spec_code,
                    "severity": "hard",
                    "message": deficiency.get("message", nigo_code),
                })
            policy_statuses.append({
                "policyNumber": pn,
                "status": "rejected",
                "effectiveDate": None,
                "errors": errors,
            })

    return {
        "requestId": request_id,
        "carrier": carrier_info,
        "policies": policy_statuses,
    }


def _post_callback(url, data, request_id):
    """POST JSON to a callback URL. Log success/failure. No retry."""
    body = json.dumps(data).encode("utf-8")
    req = URLRequest(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("requestId", request_id)
    try:
        with urlopen(req, timeout=30) as resp:
            logger.info(
                "Async callback POST to %s — status %s", url, resp.status
            )
    except (HTTPError, URLError, Exception) as e:
        logger.error("Async callback POST to %s failed: %s", url, e)


# ══════════════════════════════════════════════════════════════════════════════
# SERVICING AGENT CHANGES
# ══════════════════════════════════════════════════════════════════════════════

def _process_change_async(carrier_payload, carrier_info, policy_numbers,
                          request_id, inbound_context, callback_url):
    """
    Background thread: call AgentCore, build response, POST to caller's /reply.

    The inbound AI context from the requesting system is included in the agent
    payload so the carrier's AI can consider it during evaluation. The agent's
    summary becomes the outbound context in the response.
    """
    # Include inbound AI context in the payload so the agent sees it
    if inbound_context:
        carrier_payload["context"] = inbound_context

    logger.info("Async agent processing started — requestId=%s", request_id)
    determination = _call_carrier_agent(carrier_payload)

    if "error" in determination and "determination" not in determination:
        logger.error(
            "Async agent error for requestId=%s: %s", request_id, determination
        )
        return  # nothing to callback with

    response = _build_change_response(
        determination, carrier_info, policy_numbers, request_id
    )

    # Outbound AI context: the carrier agent's analysis and summary
    summary = determination.get("summary")
    if summary:
        response["context"] = summary

    logger.info(
        "Async agent complete — requestId=%s, determination=%s",
        request_id,
        determination.get("determination"),
    )

    # Always persist the result so it's retrievable via GET /reply/{requestId}
    from datetime import datetime as _dt
    now = _dt.utcnow().isoformat() + "Z"
    item = {
        "pk": f"{REPLY_PK_PREFIX}{request_id}",
        "sk": "RESPONSE",
        "requestId": request_id,
        "receivedAt": now,
        "response": json.dumps(response),
        "carrier": carrier_info.get("carrierName", ""),
        "determination": response.get("policies", [{}])[0].get("status", "") if response.get("policies") else "",
        "context": response.get("context", ""),
    }
    put_item(REPLY_TABLE, item)
    logger.info("Async result persisted in DynamoDB — requestId=%s", request_id)

    if callback_url:
        reply_url = f"{callback_url.rstrip('/')}/v1/servicing-agent-changes/reply"
        _post_callback(reply_url, response, request_id)
    else:
        logger.info(
            "No CALLBACK_BASE_URL configured — response logged only:\n%s",
            json.dumps(response, indent=2),
        )


@servicing_agent_changes_bp.route("/create", methods=["POST"])
def create_servicing_agent_change():
    """
    POST /v1/servicing-agent-changes/create

    Accept a servicing agent change request, return 202 immediately,
    and process via AgentCore in a background thread. When the agent
    completes, POST the ServicingAgentChangeResponse to the caller's
    /servicing-agent-changes/reply endpoint.
    """
    request_id, err = validate_request_id(request.headers)
    if err:
        return err
    correlation_id = request.headers.get("correlationId")

    data = request.get_json()
    if not data:
        return error_response("VALIDATION_ERROR", "Request body is required", request_id)

    for field in ("requestingFirm", "carrier", "client"):
        if field not in data:
            return error_response(
                "VALIDATION_ERROR", f"Missing required field: {field}", request_id
            )

    requesting_firm = data.get("requestingFirm", {})
    carrier = data.get("carrier", {})
    client = data.get("client", {})
    servicing_agent = requesting_firm.get("servicingAgent", {})
    policy_numbers = client.get("policyNumbers", [])
    body_request_id = data.get("requestId", request_id)
    inbound_context = data.get("context", "")

    logger.info(
        "v1 servicing agent change — requestId=%s, carrier=%s, policies=%s, agent=%s",
        body_request_id,
        carrier.get("carrierName"),
        policy_numbers,
        servicing_agent.get("npn"),
    )

    # ── Fast path: look up SSN from DynamoDB (~100ms) ──────────────────────
    client_ssn = ""
    for pn in policy_numbers:
        policy = lookup_policy(pn)
        if not policy:
            for cfg in CARRIER_CONFIGS.values():
                policy = lookup_policy_from_table(pn, cfg["table"], cfg["carrierName"])
                if policy:
                    break
        if policy:
            client_ssn = policy.get("ownerSSN", "")
            break

    today = date.today().isoformat()

    # ── Build the AgentCore payload ────────────────────────────────────────
    carrier_payload = {
        "request-id": body_request_id,
        "submission-date": today,
        "client": {
            "ssn": client_ssn,
            "client-name": client.get("clientName", ""),
            "contract-numbers": policy_numbers,
        },
        "receiving-agent": {
            "npn": servicing_agent.get("npn", ""),
            "agent-name": servicing_agent.get("agentName", ""),
            "status": "ACTIVE",
            "carrier-appointed": True,
            "e-o-coverage": True,
            "licensed-states": ALL_US_STATES,
        },
        "receiving-broker": {
            "broker-id": requesting_firm.get("firmId", ""),
            "broker-name": requesting_firm.get("firmName", ""),
            "status": "ACTIVE",
            "contracted-with-carrier": True,
        },
        "signatures": {
            "client-signed": True,
            "bd-authorized-signed": True,
            "signature-date": today,
        },
    }

    carrier_info = {
        "carrierName": carrier.get("carrierName"),
        "carrierId": carrier.get("carrierId"),
    }

    # ── Spawn background thread and return 202 immediately ─────────────────
    callback_url = CALLBACK_BASE_URL
    threading.Thread(
        target=_process_change_async,
        args=(carrier_payload, carrier_info, policy_numbers,
              body_request_id, inbound_context, callback_url),
        daemon=True,
    ).start()

    return deferred_response(
        body_request_id,
        "Servicing agent change request accepted for processing",
        "PT1M",
        correlation_id,
    )


@servicing_agent_changes_bp.route("/reply", methods=["POST"])
def reply_servicing_agent_change():
    """
    POST /v1/servicing-agent-changes/reply

    Receive a servicing agent change response (from carrier async processing
    or forwarded by clearinghouse). Stores the response and returns
    AcknowledgmentResponse.
    """
    request_id, err = validate_request_id(request.headers)
    if err:
        return err
    correlation_id = request.headers.get("correlationId")

    data = request.get_json()
    if not data:
        return error_response("VALIDATION_ERROR", "Request body is required", request_id)

    # Store the response in DynamoDB
    resp_request_id = data.get("requestId", request_id)
    now = datetime.utcnow().isoformat() + "Z"
    item = {
        "pk": f"{REPLY_PK_PREFIX}{resp_request_id}",
        "sk": "RESPONSE",
        "requestId": resp_request_id,
        "receivedAt": now,
        "response": json.dumps(data),
        "carrier": data.get("carrier", {}).get("carrierName", ""),
        "determination": data.get("policies", [{}])[0].get("status", "") if data.get("policies") else "",
        "context": data.get("context", ""),
    }
    put_item(REPLY_TABLE, item)

    logger.info("v1 servicing agent change reply stored in DynamoDB — requestId=%s", resp_request_id)
    return acknowledgment_response(
        request_id,
        "Servicing agent change response received successfully",
        correlation_id,
    )


@servicing_agent_changes_bp.route("/reply", methods=["GET"])
def list_change_responses():
    """
    GET /v1/servicing-agent-changes/reply

    List all received servicing agent change responses from DynamoDB.
    """
    from boto3.dynamodb.conditions import Attr
    items = scan_items(REPLY_TABLE, filter_expression=Attr("pk").begins_with(REPLY_PK_PREFIX))
    results = []
    for item in items:
        record = {
            "requestId": item.get("requestId"),
            "receivedAt": item.get("receivedAt"),
            "carrier": item.get("carrier"),
            "determination": item.get("determination"),
            "context": item.get("context", ""),
        }
        # Include full response if stored
        raw = item.get("response")
        if raw:
            try:
                record["response"] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                record["response"] = raw
        results.append(record)
    return ok_response(results)


@servicing_agent_changes_bp.route("/reply/<request_id>", methods=["GET"])
def get_change_response(request_id):
    """
    GET /v1/servicing-agent-changes/reply/<requestId>

    Retrieve a specific servicing agent change response by requestId.
    """
    item = get_item(REPLY_TABLE, f"{REPLY_PK_PREFIX}{request_id}", "RESPONSE")
    if not item:
        return error_response(
            "NOT_FOUND",
            f"No response found for requestId: {request_id}",
            status=404,
        )
    record = {
        "requestId": item.get("requestId"),
        "receivedAt": item.get("receivedAt"),
        "carrier": item.get("carrier"),
        "determination": item.get("determination"),
        "context": item.get("context", ""),
    }
    raw = item.get("response")
    if raw:
        try:
            record["response"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            record["response"] = raw
    return ok_response(record)


# ══════════════════════════════════════════════════════════════════════════════
# TRANSFER NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════

@transfer_notifications_bp.route("/create", methods=["POST"])
def create_transfer_notification():
    """
    POST /v1/transfer-notifications/create

    Receive a transfer notification. Returns AcknowledgmentResponse.
    """
    request_id, err = validate_request_id(request.headers)
    if err:
        return err
    correlation_id = request.headers.get("correlationId")

    data = request.get_json()
    if not data:
        return error_response("VALIDATION_ERROR", "Request body is required", request_id)

    if "notificationType" not in data or "policyNumber" not in data:
        return error_response(
            "VALIDATION_ERROR",
            "notificationType and policyNumber are required",
            request_id,
        )

    logger.info(
        "v1 transfer notification — requestId=%s, type=%s, policy=%s",
        request_id,
        data.get("notificationType"),
        data.get("policyNumber"),
    )

    return acknowledgment_response(
        request_id, "Transfer notification received successfully", correlation_id
    )


@transfer_notifications_bp.route("/reply", methods=["POST"])
def reply_transfer_notification():
    """
    POST /v1/transfer-notifications/reply

    Receive a transfer confirmation. Returns AcknowledgmentResponse.
    """
    request_id, err = validate_request_id(request.headers)
    if err:
        return err
    correlation_id = request.headers.get("correlationId")

    data = request.get_json()
    if not data:
        return error_response("VALIDATION_ERROR", "Request body is required", request_id)

    if "policyNumber" not in data or "confirmationStatus" not in data:
        return error_response(
            "VALIDATION_ERROR",
            "policyNumber and confirmationStatus are required",
            request_id,
        )

    logger.info(
        "v1 transfer confirmation — requestId=%s, policy=%s, status=%s",
        request_id,
        data.get("policyNumber"),
        data.get("confirmationStatus"),
    )

    return acknowledgment_response(
        request_id, "Transfer confirmation received successfully", correlation_id
    )


# ══════════════════════════════════════════════════════════════════════════════
# STATUS
# ══════════════════════════════════════════════════════════════════════════════

@status_bp.route("/<request_id>", methods=["GET"])
def query_request_status(request_id):
    """
    GET /v1/status/<requestId>

    Query current status for a request. Returns RequestStatus.
    """
    correlation_id = request.headers.get("correlationId")
    now = datetime.utcnow().isoformat() + "Z"

    status_data = {
        "currentStatus": "COMPLETE",
        "createdAt": now,
        "updatedAt": now,
        "policiesAffected": [],
    }

    return ok_response(status_data, 200, correlation_id)
