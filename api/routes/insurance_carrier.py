"""
Insurance Carrier API — Blueprint for /api/insurance-carriers/*

Key endpoint: POST /api/insurance-carriers/receive-bd-change-request

This endpoint receives a servicing-agent change request from the clearinghouse or
broker-dealer, dispatches it synchronously to the Amazon Bedrock AgentCore carrier
validation agent, and returns a structured IGO/NIGO determination.

The AgentCore agent (iri_producer_change_agent) performs the following steps:
  1. Looks up each policy in the carrier DynamoDB table by contract number.
  2. Evaluates all 9 business rules against the inbound request data.
  3. Returns a structured JSON determination that includes per-rule results,
     deficiency codes, corrective actions, and a plain-language summary.

Request payload (carrier_change_request.schema.json):
  {
    "request-id": "uuid",                       # echoed back in response
    "submission-date": "YYYY-MM-DD",
    "client": {
      "ssn": "...",
      "client-name": "...",
      "contract-numbers": ["ATH-100053"]
    },
    "receiving-agent": {
      "npn": "...",
      "agent-name": "...",
      "status": "ACTIVE",                       # ACTIVE | SUSPENDED | TERMINATED | INACTIVE
      "carrier-appointed": true,
      "e-o-coverage": true,
      "licensed-states": ["TX", "CA"]
    },
    "receiving-broker": {
      "broker-id": "...",
      "broker-name": "...",
      "crd-number": "...",
      "status": "ACTIVE",                       # ACTIVE | SUSPENDED | TERMINATED
      "contracted-with-carrier": true
    },
    "signatures": {
      "client-signed": true,
      "bd-authorized-signed": true,
      "signature-date": "YYYY-MM-DD"
    }
  }

Response payload (carrier_determination.schema.json) wrapped in StandardResponse:
  {
    "code": "APPROVED" | "REJECTED" | "ERROR",
    "message": "...",
    "transactionId": "...",
    "processingMode": "immediate",
    "payload": {
      "request-id": "...",
      "determination": "IGO" | "NIGO",
      "ruleset-version": "1.0.0",
      "evaluated-at": "ISO-8601 timestamp",
      "policies-evaluated": [...],
      "rule-results": [...],
      "deficiencies": [...],
      "corrective-actions": [...],
      "summary": "..."
    }
  }
"""

from flask import request, jsonify, Blueprint
from datetime import datetime, date
import sys
import uuid
import json
import logging
from urllib.request import urlopen, Request as URLRequest
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import boto3
from helpers import (create_response,
                     create_error_response,
                     validate_transaction_id)
sys.path.insert(0, "../")
sys.path.insert(0, "../../")
from lib.utils.dynamodb_utils import get_item, scan_items, Attr

# Blueprint registered at /api/insurance-carriers (plural, per spec)
BP = Blueprint('insurance-carriers', __name__)
URL_PREFIX = "/api/insurance-carriers"

AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:762233730742:runtime/iri_producer_change_agent-nLtgj9FbJl"
AGENT_REGION = "us-east-1"
AGENT_HOST = f"bedrock-agentcore.{AGENT_REGION}.amazonaws.com"


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrier table mapping by policy prefix
CARRIER_TABLES = {
    "ATH": {"table": "carrier", "carrierName": "Athene"},
    "PAC": {"table": "carrier-2", "carrierName": "Pacific Life"},
    "PRU": {"table": "carrier-3", "carrierName": "Prudential"},
}

# Carrier-specific configurations for direct carrier endpoints
# Policy numbers are stored without prefix in carrier-specific tables
CARRIER_CONFIGS = {
    "athene": {"table": "carrier", "carrierName": "Athene", "carrierId": "ATH1"},
    "paclife": {"table": "carrier-2", "carrierName": "Pacific Life", "carrierId": "PAC1"},
    "prudential": {"table": "carrier-3", "carrierName": "Prudential", "carrierId": "PRU1"},
}

# Value mappings from carrier DB format to API spec format
ACCOUNT_TYPE_MAP = {
    "Fixed Annuity": "individual",
    "Variable Annuity": "joint",
    "Indexed Annuity": "trust",
}

PLAN_TYPE_MAP = {
    "IRA": "traditionalIra",
    "Roth IRA": "rothIra",
    "Non-Qualified": "nonQualified",
    "SEP IRA": "sep",
    "SIMPLE IRA": "simple",
}

POLICY_STATUS_MAP = {
    "Active": "active",
    "Surrendered": "surrendered",
    "Death Claim Pending": "death claim pending",
}


# ── AgentCore dispatch helpers ──────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    """Strip markdown code fences the LLM sometimes adds around JSON output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _call_carrier_agent(payload: dict) -> dict:
    """
    Invoke the AgentCore carrier validation agent via SigV4-signed HTTP POST.

    Uses botocore (always present in the Lambda runtime) for request signing —
    no custom boto3 service model is required.

    The agent is invoked with a fresh session ID per request so each
    determination is stateless and independent.

    Args:
        payload: Carrier agent input dict matching carrier_change_request.schema.json.

    Returns:
        Parsed JSON determination dict matching carrier_determination.schema.json,
        or an error dict with keys "error" (and optionally "message"/"raw").
    """
    session = boto3.Session()
    creds = session.get_credentials().get_frozen_credentials()

    session_id = str(uuid.uuid4())
    encoded_arn = quote(AGENT_ARN, safe="")
    url = f"https://{AGENT_HOST}/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    body_bytes = json.dumps(payload).encode("utf-8")

    # Build and SigV4-sign the request using botocore primitives
    aws_request = AWSRequest(
        method="POST",
        url=url,
        data=body_bytes,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Each invocation gets a unique session so state is never shared
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        },
    )
    SigV4Auth(creds, "bedrock-agentcore", AGENT_REGION).add_auth(aws_request)

    req = URLRequest(url, data=body_bytes, headers=dict(
        aws_request.headers), method="POST")

    try:
        with urlopen(req, timeout=300) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        logger.error("AgentCore HTTP %s: %s", e.code, error_body)
        return {"error": f"AgentCore HTTP {e.code}", "message": error_body}
    except URLError as e:
        logger.error("AgentCore connection error: %s", e)
        return {"error": "AgentCore connection error", "message": str(e)}
    except Exception as e:
        logger.error("Unexpected error calling AgentCore: %s", e, exc_info=True)
        return {"error": "AgentCore invocation failed", "message": str(e)}

    # Response may arrive as SSE ("data: {...}" lines) or plain JSON.
    # Handle both defensively.
    lines = raw.splitlines()
    data_lines = [ln[6:] for ln in lines if ln.startswith("data: ")]
    raw = "".join(data_lines).strip() if data_lines else raw.strip()
    raw = _strip_fences(raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Non-JSON agent response (first 500 chars): %s", raw[:500])
        return {"error": "Agent returned non-JSON response", "raw": raw[:500]}


# ── Policy inquiry helpers (unchanged) ─────────────────────────────────────────

def get_carrier_table(policy_number: str) -> tuple:
    """
    Determine carrier table and name from policy number prefix.
    Returns (table_name, carrier_name) or (None, None) if unknown.
    """
    if not policy_number or "-" not in policy_number:
        return None, None
    prefix = policy_number.split("-")[0]
    carrier_info = CARRIER_TABLES.get(prefix)
    if carrier_info:
        return carrier_info["table"], carrier_info["carrierName"]
    return None, None


def lookup_policy(policy_number: str) -> dict:
    """
    Look up a policy from the appropriate carrier table.
    Returns the policy record or None if not found.
    """
    table_name, carrier_name = get_carrier_table(policy_number)
    if not table_name:
        return None

    policy = get_item(
        table_name,
        f"POLICY#{policy_number}",
        f"POLICY#{policy_number}"
    )

    if policy:
        policy["_carrierName"] = carrier_name
    return policy


def lookup_policy_from_table(policy_number: str, table_name: str, carrier_name: str) -> dict:
    """
    Look up a policy from a specific carrier table.
    Policy numbers are stored without carrier prefix.
    Returns the policy record or None if not found.
    """
    policy = get_item(
        table_name,
        f"POLICY#{policy_number}",
        f"POLICY#{policy_number}"
    )

    if policy:
        policy["_carrierName"] = carrier_name
    return policy


def format_policy_for_response(policy: dict, client_ssn: str = None) -> dict:
    """
    Format a carrier DB policy record to PolicyInquiryResponse DetailedPolicyInfo format.
    """
    errors = []

    if client_ssn and policy.get("ownerSSN") != client_ssn:
        errors.append({
            "errorCode": "ssnContractMismatch",
            "message": "Client's SSN does not match the contract on file"
        })

    policy_status = policy.get("policyStatus", "Active")
    if policy_status != "Active":
        errors.append({
            "errorCode": "policyInactive",
            "message": f"Policy is {policy_status.lower()}"
        })

    return {
        "policyNumber": policy.get("policyNumber"),
        "carrierName": policy.get("_carrierName", "Unknown"),
        "accountType": ACCOUNT_TYPE_MAP.get(policy.get("accountType"), "individual"),
        "planType": PLAN_TYPE_MAP.get(policy.get("planType"), "nonQualified"),
        "ownership": policy.get("ownership", "single"),
        "productName": policy.get("productName"),
        "cusip": policy.get("cusip"),
        "trailingCommission": policy.get("trailingCommission", False),
        "contractStatus": POLICY_STATUS_MAP.get(policy_status, "active"),
        "withdrawalStructure": {
            "systematicInPlace": False
        },
        "errors": errors
    }


def validate_producer(agent_name: str, npn: str) -> list:
    """
    Validate producer licensing and appointments.
    For hackathon demo, always returns valid (empty errors).
    """
    return []


# ── Route handlers ──────────────────────────────────────────────────────────────

@BP.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "insurance-carrier-api",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


def _process_carrier_policy_inquiry(carrier_key: str):
    """
    Common policy inquiry logic for carrier-specific endpoints.
    Looks up policies only from the specified carrier's table.
    """
    carrier_config = CARRIER_CONFIGS.get(carrier_key)
    if not carrier_config:
        return create_error_response(
            "INVALID_CARRIER",
            f"Unknown carrier: {carrier_key}",
            400
        )

    table_name = carrier_config["table"]
    carrier_name = carrier_config["carrierName"]

    transaction_id, error = validate_transaction_id(request.headers)
    if error:
        return error

    try:
        data = request.get_json()
        if not data:
            return create_error_response(
                "INVALID_PAYLOAD",
                "Request body is required",
                400
            )

        if 'requestingFirm' not in data or 'client' not in data:
            return create_error_response(
                "VALIDATION_ERROR",
                "requestingFirm and client are required fields",
                400
            )

        requesting_firm = data.get('requestingFirm', {})
        client = data.get('client', {})
        servicing_agent = requesting_firm.get('servicingAgent', {})

        logger.info(f"[{carrier_name}] Policy inquiry - Transaction ID: {transaction_id}")
        logger.info(f"[{carrier_name}] Client: {client.get('clientName')}")
        logger.info(f"[{carrier_name}] Policy Numbers: {client.get('policyNumbers', [])}")

        client_ssn = client.get('ssn')
        policy_numbers = client.get('policyNumbers', [])

        producer_errors = validate_producer(
            servicing_agent.get('agentName'),
            servicing_agent.get('npn')
        )

        policies = []
        client_name_from_db = None
        ssn_last4 = client_ssn[-4:] if client_ssn and len(client_ssn) >= 4 else None

        for policy_number in policy_numbers:
            # Look up policy directly (no prefix validation needed)
            policy = lookup_policy_from_table(policy_number, table_name, carrier_name)
            if policy:
                if not client_name_from_db:
                    client_name_from_db = policy.get('clientName')
                    if not ssn_last4 and policy.get('ownerSSN'):
                        ssn_last4 = policy.get('ownerSSN')[-4:]

                formatted_policy = format_policy_for_response(policy, client_ssn)
                policies.append(formatted_policy)
            else:
                policies.append({
                    "policyNumber": policy_number,
                    "carrierName": carrier_name,
                    "errors": [{
                        "errorCode": "policyNotFound",
                        "message": f"Policy {policy_number} not found in {carrier_name} records"
                    }]
                })

        response_payload = {
            "requestingFirm": {
                "firmName": requesting_firm.get('firmName'),
                "firmId": requesting_firm.get('firmId'),
                "servicingAgent": {
                    "agentName": servicing_agent.get('agentName'),
                    "npn": servicing_agent.get('npn')
                }
            },
            "producerValidation": {
                "agentName": servicing_agent.get('agentName'),
                "npn": servicing_agent.get('npn'),
                "errors": producer_errors
            },
            "client": {
                "clientName": client_name_from_db or client.get('clientName'),
                "ssnLast4": ssn_last4,
                "policies": policies
            },
            "enums": {
                "accountType": ["individual", "joint", "trust", "custodial", "entity"],
                "planType": ["nonQualified", "rothIra", "traditionalIra", "sep", "simple"]
            }
        }

        logger.info(
            f"[{carrier_name}] Returning {len(policies)} policies for transaction {transaction_id}")

        return create_response(
            "IMMEDIATE",
            f"Policy inquiry processed successfully by {carrier_name}",
            transaction_id,
            response_payload,
            200,
            processing_mode="immediate"
        )

    except Exception as e:
        logger.error(f"[{carrier_name}] Error processing policy inquiry: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/athene/policy-inquiry', methods=['POST'])
def athene_policy_inquiry():
    """
    Athene-specific policy inquiry endpoint.
    Looks up policies from the 'carrier' table (Athene policies with ATH- prefix).
    """
    return _process_carrier_policy_inquiry("athene")


@BP.route('/paclife/policy-inquiry', methods=['POST'])
def paclife_policy_inquiry():
    """
    Pacific Life-specific policy inquiry endpoint.
    Looks up policies from the 'carrier-2' table (Pacific Life policies with PAC- prefix).
    """
    return _process_carrier_policy_inquiry("paclife")


@BP.route('/prudential/policy-inquiry', methods=['POST'])
def prudential_policy_inquiry():
    """
    Prudential-specific policy inquiry endpoint.
    Looks up policies from the 'carrier-3' table (Prudential policies with PRU- prefix).
    """
    return _process_carrier_policy_inquiry("prudential")


@BP.route('/policy-inquiry', methods=['POST'])
def policy_inquiry():
    """
    Process policy inquiry request (direct or via clearinghouse).

    Accept policy inquiry request to provide policy information for specified accounts.
    Carrier responds immediately with policy data from carrier tables.

    Unified API endpoint - replaces /submit-policy-inquiry-request
    """
    transaction_id, error = validate_transaction_id(request.headers)
    if error:
        return error

    try:
        data = request.get_json()
        if not data:
            return create_error_response("INVALID_PAYLOAD", "Request body is required", 400)

        if 'requestingFirm' not in data:
            return create_error_response("VALIDATION_ERROR", "Missing required field: requestingFirm", 400)
        if 'client' not in data:
            return create_error_response("VALIDATION_ERROR", "Missing required field: client", 400)

        requesting_firm = data.get('requestingFirm', {})
        client = data.get('client', {})
        servicing_agent = requesting_firm.get('servicingAgent', {})

        logger.info("Policy inquiry - Transaction: %s, Firm: %s, Policies: %s",
                    transaction_id, requesting_firm.get('firmName'),
                    client.get('policyNumbers', []))

        client_ssn = client.get('ssn')
        policy_numbers = client.get('policyNumbers', [])

        producer_errors = validate_producer(
            servicing_agent.get('agentName'),
            servicing_agent.get('npn')
        )

        policies = []
        client_name_from_db = None
        ssn_last4 = client_ssn[-4:] if client_ssn and len(client_ssn) >= 4 else None

        for policy_number in policy_numbers:
            policy = lookup_policy(policy_number)
            if policy:
                if not client_name_from_db:
                    client_name_from_db = policy.get('clientName')
                    if not ssn_last4 and policy.get('ownerSSN'):
                        ssn_last4 = policy.get('ownerSSN')[-4:]
                policies.append(format_policy_for_response(policy, client_ssn))
            else:
                policies.append({
                    "policyNumber": policy_number,
                    "carrierName": None,
                    "accountType": None,
                    "planType": None,
                    "ownership": None,
                    "productName": None,
                    "cusip": None,
                    "trailingCommission": False,
                    "contractStatus": None,
                    "withdrawalStructure": {"systematicInPlace": False},
                    "errors": [{"errorCode": "policyNotFound",
                                "message": f"Policy {policy_number} not found in carrier records"}]
                })

        response_payload = {
            "requestingFirm": {
                "firmName": requesting_firm.get('firmName'),
                "firmId": requesting_firm.get('firmId'),
                "servicingAgent": {
                    "agentName": servicing_agent.get('agentName'),
                    "npn": servicing_agent.get('npn')
                }
            },
            "producerValidation": {
                "agentName": servicing_agent.get('agentName'),
                "npn": servicing_agent.get('npn'),
                "errors": producer_errors
            },
            "client": {
                "clientName": client_name_from_db or client.get('clientName'),
                "ssnLast4": ssn_last4,
                "policies": policies
            },
            "enums": {
                "accountType": ["individual", "joint", "trust", "custodial", "entity"],
                "planType": ["nonQualified", "rothIra", "traditionalIra", "sep", "simple"]
            }
        }

        logger.info("Returning %d policies for transaction %s",
                    len(policies), transaction_id)
        return create_response("IMMEDIATE", "Policy inquiry processed successfully",
                               transaction_id, response_payload, 200, processing_mode="immediate")

    except Exception as e:
        logger.error("Error processing policy inquiry request: %s", str(e))
        return create_error_response("INTERNAL_ERROR", "Internal server error occurred", 500)


@BP.route('/policy-inquiry-callback', methods=['POST'])
def policy_inquiry_callback():
    """
    Policy inquiry callback - submit policy inquiry response.

    Submit detailed policy information response to clearinghouse after
    processing a deferred request.

    Unified API endpoint - replaces /submit-policy-inquiry-response
    """
    transaction_id, error = validate_transaction_id(request.headers)
    if error:
        return error

    try:
        data = request.get_json()
        if not data:
            return create_error_response("INVALID_PAYLOAD", "Request body is required", 400)

        required_fields = ['requestingFirm', 'producerValidation', 'client', 'enums']
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        logger.info("Policy inquiry response submitted - Transaction: %s", transaction_id)
        return create_response("RECEIVED", "Policy inquiry response submitted successfully",
                               transaction_id, None, 200)

    except Exception as e:
        logger.error("Error submitting policy inquiry response: %s", str(e))
        return create_error_response("INTERNAL_ERROR", "Internal server error occurred", 500)


@BP.route('/receive-bd-change-request', methods=['POST'])
@BP.route('/bd-change', methods=['POST'])
def receive_bd_change_request():
    """
    Receive a BD change validation request and return a synchronous IGO/NIGO determination.

    This is the primary integration point between the clearinghouse/BD and the carrier's
    AI-powered validation engine (Amazon Bedrock AgentCore).

    Routes: POST /receive-bd-change-request  (canonical)
            POST /bd-change                   (alias per Unified Brokerage Transfer API spec)

    The AgentCore carrier agent evaluates all 9 business rules:
      RULE-001 through RULE-009 (signatures, agent status, appointment, E&O, licensing,
      broker selling agreement).

    Response codes:
      APPROVED  — IGO: all hard-stop rules passed
      REJECTED  — NIGO: one or more rules failed; payload has per-rule results
      ERROR     — AgentCore invocation failed
    """
    transaction_id, error = validate_transaction_id(request.headers)
    if error:
        return error

    try:
        data = request.get_json()
        if not data:
            return create_error_response("INVALID_PAYLOAD", "Request body is required", 400)

        # Validate spec-required BdChangeRequest fields
        required_fields = ['receivingBrokerId',
                           'deliveringBrokerId', 'carrierId', 'policyNumber']
        missing_fields = [f for f in required_fields if not data.get(f)]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        broker_details = data.get('brokerDetails', {})
        policy_number = data.get('policyNumber', '')
        today = date.today().isoformat()

        # Build carrier agent payload from spec's BdChangeRequest format.
        # brokerDetails contains the receiving agent validation fields;
        # top-level fields contain signature and client info.
        license_state = broker_details.get('licenseState')
        licensed_states = (
            broker_details.get('licensedStates')       # preferred: list
            or ([license_state] if license_state else [])  # fallback: single string
        )

        carrier_payload = {
            "request-id": data.get('requestId', transaction_id),
            "submission-date": data.get('submissionDate', today),
            "client": {
                "ssn": data.get('clientSSN', data.get('ssn', '')),
                "client-name": data.get('clientName', ''),
                "contract-numbers": [policy_number] if policy_number else [],
            },
            "receiving-agent": {
                "npn": broker_details.get('npn', ''),
                "agent-name": broker_details.get('agentName', ''),
                "status": broker_details.get('agentStatus', 'ACTIVE'),
                "carrier-appointed": broker_details.get('carrierAppointed', True),
                "e-o-coverage": broker_details.get('eoInPlace', True),
                "licensed-states": licensed_states,
            },
            "receiving-broker": {
                "broker-id": data.get('receivingBrokerId', ''),
                "broker-name": broker_details.get('firmName', ''),
                "status": data.get('brokerStatus', 'ACTIVE'),
                "contracted-with-carrier": data.get('contractedWithCarrier', True),
            },
            "signatures": {
                "client-signed": data.get('clientSigned', True),
                "bd-authorized-signed": data.get('bdAuthorizedSigned', True),
                "signature-date": data.get('signatureDate', today),
            },
        }

        logger.info(
            "BD change validation — Transaction: %s, Policy: %s, "
            "Carrier: %s, Receiving broker: %s, Agent NPN: %s",
            transaction_id,
            policy_number,
            data.get('carrierId'),
            data.get('receivingBrokerId'),
            broker_details.get('npn'),
        )

        # Dispatch to AgentCore carrier agent for synchronous IGO/NIGO determination
        logger.info("Dispatching to AgentCore carrier validation agent")
        determination = _call_carrier_agent(carrier_payload)

        if "error" in determination and "determination" not in determination:
            logger.error("Carrier agent error: %s", determination)
            return create_error_response(
                "AGENT_ERROR",
                determination.get("error", "Carrier agent invocation failed"),
                500
            )

        det_value = determination.get("determination", "")
        if det_value == "IGO":
            code = "APPROVED"
            message = "Servicing agent change approved — all business rules passed"
        elif det_value == "NIGO":
            deficiencies = determination.get("deficiencies", [])
            nigo_codes = ", ".join(d.get("nigo-code", "")
                                   for d in deficiencies if d.get("nigo-code"))
            summary = determination.get("summary", f"Deficiency codes: {nigo_codes}")
            code = "REJECTED"
            message = f"Servicing agent change rejected — {summary}"
        else:
            code = "RECEIVED"
            message = "Validation completed"

        logger.info("Determination: %s for transaction %s", det_value, transaction_id)

        return create_response(
            code,
            message,
            transaction_id,
            determination,   # full IGO/NIGO detail in payload
            200,
            processing_mode="immediate"
        )

    except Exception as e:
        logger.error("Error processing BD change request: %s", str(e), exc_info=True)
        return create_error_response("INTERNAL_ERROR", "Internal server error occurred", 500)


@BP.route('/transfer-notification', methods=['POST'])
def transfer_notification():
    """
    Transfer notification - accept transfer-related notifications.
    Supports various notification types per TransferNotification schema.

    Unified API endpoint - replaces /receive-transfer-notification
    """
    transaction_id, error = validate_transaction_id(request.headers)
    if error:
        return error

    try:
        data = request.get_json()
        if not data:
            return create_error_response("INVALID_PAYLOAD", "Request body is required", 400)

        # Validate required fields per TransferNotification schema
        required_fields = ['notificationType', 'policyNumber']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        notification_type = data.get('notificationType')
        valid_types = ['transfer-approved', 'transfer-initiated', 'transfer-confirmed',
                       'transfer-complete', 'service-agent-change-complete']
        if notification_type not in valid_types:
            return create_error_response(
                "VALIDATION_ERROR",
                f"notificationType must be one of: {', '.join(valid_types)}",
                400
            )

        logger.info(
            "Transfer notification received — Transaction: %s, Policy: %s, "
            "Carrier: %s, New Broker: %s, Effective: %s",
            transaction_id,
            data.get('policyNumber'),
            data.get('carrierId'),
            data.get('receivingBrokerId'),
            data.get('effectiveDate'),
        )

        # TODO: Update policy servicing agent records and trigger internal workflows.

        return create_response(
            "RECEIVED",
            f"Transfer notification '{notification_type}' received and processed",
            transaction_id,
            None,
            200,
            processing_mode="immediate"
        )

    except Exception as e:
        logger.error("Error processing transfer notification: %s", str(e))
        return create_error_response("INTERNAL_ERROR", "Internal server error occurred", 500)


@BP.route('/bd-change-callback', methods=['POST'])
def bd_change_callback():
    """
    BD change callback - submit carrier validation response.
    Used to report approval/rejection to clearinghouse.

    Unified API endpoint.
    """
    transaction_id, error = validate_transaction_id(request.headers)
    if error:
        return error

    try:
        data = request.get_json()
        if not data:
            return create_error_response(
                "INVALID_PAYLOAD",
                "Request body is required",
                400
            )

        # Validate required fields per CarrierResponse schema
        required_fields = ['carrierId', 'policyNumber', 'validationResult']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        validation_result = data.get('validationResult')
        if validation_result not in ['approved', 'rejected']:
            return create_error_response(
                "VALIDATION_ERROR",
                "validationResult must be either 'approved' or 'rejected'",
                400
            )

        logger.info(f"Submitting carrier response - Transaction ID: {transaction_id}")
        logger.info(f"Carrier: {data.get('carrierId')}")
        logger.info(f"Policy Number: {data.get('policyNumber')}")
        logger.info(f"Validation Result: {validation_result}")

        # TODO: Forward to clearinghouse
        # - Send response to clearinghouse endpoint
        # - Update local transaction status

        return create_response(
            "RECEIVED",
            f"Carrier validation response submitted - {validation_result}",
            transaction_id,
            None,
            200
        )

    except Exception as e:
        logger.error(f"Error submitting carrier response: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/transfer-confirmation', methods=['POST'])
def transfer_confirmation():
    """
    Transfer confirmation - accept transfer confirmation.

    Unified API endpoint.
    """
    transaction_id, error = validate_transaction_id(request.headers)
    if error:
        return error

    try:
        data = request.get_json()
        if not data:
            return create_error_response(
                "INVALID_PAYLOAD",
                "Request body is required",
                400
            )

        # Validate required fields per TransferConfirmation schema
        required_fields = ['policyNumber', 'confirmationStatus']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        confirmation_status = data.get('confirmationStatus')
        if confirmation_status not in ['confirmed', 'failed', 'pending']:
            return create_error_response(
                "VALIDATION_ERROR",
                "confirmationStatus must be one of: 'confirmed', 'failed', 'pending'",
                400
            )

        logger.info(f"Received transfer confirmation - Transaction ID: {transaction_id}")
        logger.info(f"Policy Number: {data.get('policyNumber')}")
        logger.info(f"Confirmation Status: {confirmation_status}")

        # TODO: Process transfer confirmation
        # - Update policy records
        # - Finalize broker change

        return create_response(
            "RECEIVED",
            f"Transfer confirmation received - {confirmation_status}",
            transaction_id,
            None,
            200
        )

    except Exception as e:
        logger.error(f"Error processing transfer confirmation: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/query-status/<transaction_id>', methods=['GET'])
def query_status(transaction_id):
    """
    Query transaction status by transaction ID.
    """
    try:
        try:
            uuid.UUID(transaction_id)
        except ValueError:
            return create_error_response(
                "INVALID_TRANSACTION_ID",
                "Transaction ID must be a valid UUID",
                400
            )

        logger.info("Status query for transaction: %s", transaction_id)

        # TODO: Retrieve from request-tracking DynamoDB table.
        # Returning mock data for hackathon demo.
        status_data = {
            "currentStatus": "CARRIER_APPROVED",
            "createdAt": "2026-02-25T10:30:00Z",
            "updatedAt": "2026-02-25T11:00:00Z",
            "statusHistory": [
                {
                    "status": "CARRIER_VALIDATION_PENDING",
                    "timestamp": "2026-02-25T10:30:00Z",
                    "notes": "BD change validation request received from clearinghouse"
                },
                {
                    "status": "CARRIER_APPROVED",
                    "timestamp": "2026-02-25T11:00:00Z",
                    "notes": "All 9 business rules passed — IGO determination"
                }
            ],
            "carrierValidationDetails": {
                "validatedBy": "AgentCore carrier agent (iri_producer_change_agent)",
                "validationTimestamp": "2026-02-25T11:00:00Z"
            },
            "policiesAffected": [],
            "additionalData": {}
        }

        return jsonify(status_data), 200

    except Exception as e:
        logger.error("Error querying transaction status: %s", str(e))
        return create_error_response("INTERNAL_ERROR", "Internal server error occurred", 500)
