"""
Broker-Dealer API Flask Application
Implements the OpenAPI specification for broker-dealer endpoints
Integrated with DynamoDB distributor tables.
"""

from flask import request, jsonify, Blueprint
from datetime import datetime, timezone, date
import sys
import uuid
import base64
import json
import io
import os
import logging
from urllib.request import urlopen, Request as URLRequest
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from dotenv import load_dotenv
import boto3
from fpdf import FPDF
load_dotenv(override=False)
sys.path.insert(0, "../")
sys.path.insert(0, "../../")
from helpers import (create_response,
                     create_error_response,
                     validate_request_id)
from lib.utils.dynamodb_utils import get_item, put_item, update_item, scan_items, Attr

BP = Blueprint('broker-dealer', __name__)
URL_PREFIX = "/v1/broker-dealer"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Distributor table mapping by broker ID prefix
DISTRIBUTOR_TABLES = {
    "BD-1001": "distributor",
    "BD-2002": "distributor",
    "BD-3003": "distributor",
    "BD-4004": "distributor",
    "BD-5005": "distributor-2",
}

DEFAULT_DISTRIBUTOR_TABLE = "distributor"


def get_distributor_table(broker_id: str) -> str:
    """Get the distributor table for a broker ID."""
    return DISTRIBUTOR_TABLES.get(broker_id, DEFAULT_DISTRIBUTOR_TABLE)


def get_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def find_transaction_by_id(request_id: str, table_name: str = None):
    """
    Find a transaction by ID across distributor tables.
    Returns (record, table_name) or (None, None).
    """
    tables_to_search = [table_name] if table_name else ["distributor", "distributor-2"]

    for table in tables_to_search:
        try:
            items = scan_items(
                table,
                Attr("request-id").eq(request_id)
            )
            if items:
                return items[0], table
        except Exception as e:
            logger.error(f"Error scanning {table}: {e}")

    return None, None


def create_transaction_record(
    request_id: str,
    npn: str,
    broker_id: str,
    broker_role: str,
    policy_id: str,
    carrier_id: str,
    client_details: dict,
    firm_details: dict,
    agent_details: dict,
    other_broker: dict,
) -> dict:
    """Create a new transaction record for the distributor table."""
    timestamp = get_timestamp()

    record = {
        "pk": f"NPN#{npn}",
        "sk": f"TRANSACTION#{request_id}",
        "request-id": request_id,
        "policy-id": policy_id,
        "carrier-id": carrier_id,
        "broker-id": broker_id,
        "broker-role": broker_role,
        "current-status": "MANIFEST_REQUESTED",
        "status-history": [{
            "status": "MANIFEST_REQUESTED",
            "timestamp": timestamp,
            "notes": "Transaction initiated"
        }],
        "created-at": timestamp,
        "updated-at": timestamp,
        "client-details": client_details,
        "firm-details": firm_details,
        "agent-details": agent_details,
    }

    # Add counterparty info based on role
    if broker_role == "receiving":
        record["delivering-broker"] = other_broker
        record["receiving-broker"] = firm_details
    else:
        record["receiving-broker"] = other_broker
        record["delivering-broker"] = firm_details

    return record


def update_transaction_status(
    table_name: str,
    pk: str,
    sk: str,
    new_status: str,
    notes: str = None
) -> dict:
    """Update transaction status and append to history."""
    timestamp = get_timestamp()

    history_item = {"status": new_status, "timestamp": timestamp}
    if notes:
        history_item["notes"] = notes

    return update_item(
        table_name,
        pk,
        sk,
        update_expression="SET #status = :status, #updated = :updated, #history = list_append(#history, :history_item)",
        expression_values={
            ":status": new_status,
            ":updated": timestamp,
            ":history_item": [history_item]
        },
        expression_names={
            "#status": "current-status",
            "#updated": "updated-at",
            "#history": "status-history"
        }
    )


@BP.route('/health', methods=['GET'], strict_slashes=False)
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "broker-dealer-api",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


@BP.route('/policy-inquiries/create', methods=['POST'], strict_slashes=False)
def policy_inquiry():
    """
    Process policy inquiry request.
    Endpoint for delivering broker-dealer - receives from clearinghouse or direct.
    Stores the request in the distributor table.

    Unified API endpoint - replaces /submit-policy-inquiry-request
    """
    request_id, error = validate_request_id(request.headers)
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

        # Validate required fields
        if 'requestingFirm' not in data or 'client' not in data:
            return create_error_response(
                "VALIDATION_ERROR",
                "requestingFirm and client are required fields",
                400
            )

        requesting_firm = data.get('requestingFirm', {})
        client = data.get('client', {})
        servicing_agent = requesting_firm.get('servicingAgent', {})

        logger.info(f"Received policy inquiry request - Transaction ID: {request_id}")
        logger.info(f"Requesting Firm: {requesting_firm.get('firmName')}")
        logger.info(f"Client: {client.get('clientName')}")

        # Store manifest request in distributor table
        npn = servicing_agent.get('npn', 'UNKNOWN')
        broker_id = requesting_firm.get('firmId', 'UNKNOWN')
        table_name = get_distributor_table(broker_id)

        policy_numbers = client.get('policyNumbers', [])
        policy_id = policy_numbers[0] if policy_numbers else "UNKNOWN"

        # Determine carrier from policy prefix
        if policy_id.startswith("ATH"):
            carrier_id = "carrier"
        elif policy_id.startswith("PAC"):
            carrier_id = "carrier-2"
        elif policy_id.startswith("PRU"):
            carrier_id = "carrier-3"
        else:
            carrier_id = "unknown"

        record = create_transaction_record(
            request_id=request_id,
            npn=npn,
            broker_id=broker_id,
            broker_role="delivering",
            policy_id=policy_id,
            carrier_id=carrier_id,
            client_details={
                "client-name": client.get('clientName'),
                "ssn": client.get('ssn'),
                "contract-numbers": policy_numbers,
            },
            firm_details={
                "firm-id": broker_id,
                "firm-name": requesting_firm.get('firmName'),
            },
            agent_details={
                "agent-name": servicing_agent.get('agentName'),
                "npn": npn,
            },
            other_broker={
                "broker-id": requesting_firm.get('firmId'),
                "broker-name": requesting_firm.get('firmName'),
            }
        )

        # Store manifest request details
        record["manifest-request"] = {
            "requesting-firm": requesting_firm,
            "client": client,
            "request-timestamp": get_timestamp(),
        }

        put_item(table_name, record)
        logger.info(f"Stored transaction {request_id} in {table_name}")

        return create_response(
            "RECEIVED",
            "Policy inquiry request received and stored",
            request_id,
            processing_mode="deferred"
        )

    except Exception as e:
        logger.error(f"Error processing policy inquiry request: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/policy-inquiries/reply', methods=['POST'], strict_slashes=False)
def policy_inquiry_callback():
    """
    Policy inquiry callback - receive policy inquiry response.
    Endpoint for receiving broker-dealer - receives from clearinghouse or direct.
    Updates the transaction status to MANIFEST_RECEIVED.

    Unified API endpoint - replaces /receive-policy-inquiry-response
    """
    request_id, error = validate_request_id(request.headers)
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

        # Validate required fields
        required_fields = ['requestingFirm', 'producerValidation', 'client', 'enums']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        logger.info(
            f"Received policy inquiry response - Transaction ID: {request_id}")
        logger.info(f"Client: {data.get('client', {}).get('clientName')}")

        # Find and update existing transaction
        record, table_name = find_transaction_by_id(request_id)

        if record:
            update_transaction_status(
                table_name,
                record["pk"],
                record["sk"],
                "MANIFEST_RECEIVED",
                "Policy inquiry response received from clearinghouse"
            )
            logger.info(f"Updated transaction {request_id} to MANIFEST_RECEIVED")
        else:
            logger.warning(
                f"Transaction {request_id} not found in distributor tables")

        return create_response(
            "RECEIVED",
            "Policy inquiry response received successfully",
            request_id
        )

    except Exception as e:
        logger.error(f"Error processing policy inquiry response: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/servicing-agent-changes/create', methods=['POST'], strict_slashes=False)
def bd_change():
    """
    Brokerage dealer change request.
    Endpoint for receiving broker-dealer - receives from clearinghouse or direct.
    Updates transaction status.

    Unified API endpoint - replaces /receive-bd-change-request
    """
    request_id, error = validate_request_id(request.headers)
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

        # Validate required fields
        required_fields = ['request-id', 'receiving-broker-id', 'delivering-broker-id',
                           'carrier-id', 'policy-id']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        logger.info(f"Received BD change request - Transaction ID: {request_id}")
        logger.info(f"Policy ID: {data.get('policy-id')}")
        logger.info(f"Receiving Broker: {data.get('receiving-broker-id')}")
        logger.info(f"Delivering Broker: {data.get('delivering-broker-id')}")

        # Find and update existing transaction
        record, table_name = find_transaction_by_id(request_id)

        if record:
            update_transaction_status(
                table_name,
                record["pk"],
                record["sk"],
                "DUE_DILIGENCE_COMPLETE",
                "BD change request received, due diligence complete"
            )
            logger.info(f"Updated transaction {request_id} to DUE_DILIGENCE_COMPLETE")

        return create_response(
            "RECEIVED",
            "BD change request received successfully",
            request_id
        )

    except Exception as e:
        logger.error(f"Error processing BD change request: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/transfer-notifications/create', methods=['POST'], strict_slashes=False)
def transfer_notification():
    """
    Transfer notification - accept transfer-related notifications.
    Receives from clearinghouse or direct.
    Accepts transfer-related notifications and updates status.

    Unified API endpoint - replaces /receive-transfer-notification
    """
    request_id, error = validate_request_id(request.headers)
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
        valid_types = ['transfer-approved', 'transfer-initiated',
                       'transfer-confirmed', 'transfer-complete', 'service-agent-change-complete']
        if notification_type not in valid_types:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Invalid notificationType. Must be one of: {', '.join(valid_types)}",
                400
            )

        logger.info(f"Received transfer notification - Transaction ID: {request_id}")
        logger.info(f"Notification Type: {notification_type}")
        logger.info(f"Policy Number: {data.get('policyNumber')}")

        # Map notification type to status
        notification_to_status = {
            "transfer-approved": "CARRIER_APPROVED",
            "transfer-initiated": "TRANSFER_INITIATED",
            "transfer-confirmed": "TRANSFER_CONFIRMED",
            "transfer-complete": "COMPLETE",
        }
        new_status = notification_to_status.get(notification_type, "TRANSFER_PROCESSING")

        # Find and update existing transaction
        record, table_name = find_transaction_by_id(request_id)

        if record:
            # Update status
            update_transaction_status(
                table_name,
                record["pk"],
                record["sk"],
                new_status,
                f"Transfer notification: {notification_type}"
            )

            # Store latest notification
            update_item(
                table_name,
                record["pk"],
                record["sk"],
                updates={
                    "latest-notification": {
                        "notificationType": notification_type,
                        "notificationTimestamp": get_timestamp(),
                        "policyNumber": data.get('policyNumber'),
                    }
                }
            )
            logger.info(f"Updated transaction {request_id} to {new_status}")

        return create_response(
            "RECEIVED",
            f"Transfer notification '{notification_type}' received successfully",
            request_id
        )

    except Exception as e:
        logger.error(f"Error processing transfer notification: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


# ── SQS Trigger Routes ──────────────────────────────────────────────────────────
# UI-facing endpoints that enqueue async work onto SQS queues.
# The actual API calls are handled by standalone SQS-triggered Lambdas.

_SQS_REGION = os.environ.get("SQS_REGION", "us-east-1")


@BP.route('/trigger-policy-inquiry', methods=['POST'])
def trigger_policy_inquiry():
    """
    Trigger a policy inquiry request via SQS.

    Called by the UI (button click) to initiate a policy info fetch from
    DTCC/IIEX.  Enqueues an SQS message; the sqs-policy-inquiry Lambda
    handles the actual API call, DB update, and EventBridge notification.

    Required header:  requestId (ULID, per spec v0.1.1)
    Required body:    requestingFirm, client  (per PolicyInquiryRequest schema)
    Returns:          202 with code=QUEUED
    """
    request_id = request.headers.get("requestId") or request.headers.get("requestid")
    if not request_id:
        return create_error_response("MISSING_HEADER", "requestId header is required", 400)

    data = request.get_json(silent=True)
    if not data:
        return create_error_response("INVALID_PAYLOAD", "JSON request body is required", 400)

    missing = [f for f in ("requestingFirm", "client") if f not in data]
    if missing:
        return create_error_response(
            "VALIDATION_ERROR",
            f"Missing required fields: {', '.join(missing)}",
            400,
        )

    queue_url = os.environ.get("POLICY_INQUIRY_SQS_URL")
    if not queue_url:
        return create_error_response(
            "CONFIGURATION_ERROR",
            "Policy inquiry queue not configured",
            500,
        )

    message = {
        "requestId": request_id,
        "action": "POLICY_INQUIRY",
        "requestData": data,
        "timestamp": get_timestamp(),
    }

    try:
        sqs = boto3.client("sqs", region_name=_SQS_REGION)
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message),
            MessageAttributes={
                "action": {"StringValue": "POLICY_INQUIRY", "DataType": "String"},
            },
        )
    except Exception as e:
        logger.error("Failed to enqueue policy inquiry — requestId=%s: %s", request_id, e)
        return create_error_response("QUEUE_ERROR", "Failed to enqueue policy inquiry request", 500)

    logger.info("Policy inquiry enqueued — requestId=%s", request_id)
    return create_response(
        "QUEUED",
        "Policy inquiry request queued for processing",
        request_id,
        status_code=202,
        processing_mode="deferred",
        estimated_response_time="PT30S",
    )


@BP.route('/trigger-transfer-request', methods=['POST'])
def trigger_transfer_request():
    """
    Trigger a BD change / transfer request via SQS.

    Called by the UI (button click) to initiate a broker-dealer change.
    Enqueues an SQS message; the sqs-bd-change Lambda handles the actual
    /servicing-agent-changes/create API call, DB update, and EventBridge
    notification.  The async carrier response arrives later via the
    api-bd-change-callback Lambda endpoint.

    Required header:  requestId (ULID, per spec v0.1.1)
    Required body:    requestingFirm, carrier, client
                      (per ServicingAgentChangeRequest schema v0.1.1)
    Returns:          202 with code=QUEUED
    """
    request_id = request.headers.get("requestId") or request.headers.get("requestid")
    if not request_id:
        return create_error_response("MISSING_HEADER", "requestId header is required", 400)

    data = request.get_json(silent=True)
    if not data:
        return create_error_response("INVALID_PAYLOAD", "JSON request body is required", 400)

    required = ["requestingFirm", "carrier", "client"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return create_error_response(
            "VALIDATION_ERROR",
            f"Missing required fields: {', '.join(missing)}",
            400,
        )

    queue_url = os.environ.get("BD_CHANGE_SQS_URL")
    if not queue_url:
        return create_error_response(
            "CONFIGURATION_ERROR",
            "BD change queue not configured",
            500,
        )

    message = {
        "requestId": request_id,
        "action": "BD_CHANGE",
        "requestData": data,
        "timestamp": get_timestamp(),
    }

    try:
        sqs = boto3.client("sqs", region_name=_SQS_REGION)
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message),
            MessageAttributes={
                "action": {"StringValue": "BD_CHANGE", "DataType": "String"},
            },
        )
    except Exception as e:
        logger.error("Failed to enqueue BD change — requestId=%s: %s", request_id, e)
        return create_error_response("QUEUE_ERROR", "Failed to enqueue transfer request", 500)

    logger.info("BD change enqueued — requestId=%s", request_id)
    return create_response(
        "QUEUED",
        "Transfer request queued for processing",
        request_id,
        status_code=202,
        processing_mode="deferred",
        estimated_response_time="PT5M",
    )


# ── PDF Policy Statement Extractor ─────────────────────────────────────────────
# Uses Claude via Bedrock converse() with a native document block.
# No text-extraction library needed — Claude reads the PDF layout directly.

_PDF_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
_PDF_REGION = "us-east-1"

_PDF_SYSTEM_PROMPT = """You are a document data extraction specialist for annuity policy statements.

Your job: read the provided policy statement PDF and extract every relevant field into a
policyInquiryResponse JSON object. Return ONLY the JSON — no markdown, no code fences,
no explanation, no prose before or after.

───────────────────────────────────────────────────────────────────────────────
FIELD EXTRACTION GUIDE
───────────────────────────────────────────────────────────────────────────────

requestingFirm
  firmName  → The BROKER-DEALER or financial advisory FIRM that submitted this application
              (e.g. "Strategic Wealth Advisors", "Premier Financial Services").
              This is NOT the insurance carrier. Look for labels like "Broker-Dealer",
              "Selling Firm", "Advisor Firm", "Receiving Firm", "BD Firm", or the
              firm associated with the servicing agent's employer.
  firmId    → The BD firm's identifier (DTCC ID, CRD, or internal firm ID shown on the
              document). null if not present.
  servicingAgent
    agentName → Full name of the financial adviser / agent of record / servicing agent
    npn       → Agent's National Producer Number (NPN). null if not shown.

producerValidation
  agentName → Same as requestingFirm.servicingAgent.agentName
  npn       → Same as requestingFirm.servicingAgent.npn
  errors    → Always []

client
  clientName  → For INDIVIDUAL accounts: the policy owner's full legal name.
                For TRUST accounts: the full trust name (e.g. "Foster Family Irrevocable Trust"),
                NOT the trustee's personal name.
                For BUSINESS/ENTITY accounts: the entity name.
  ssnLast4    → Last 4 digits of SSN. For trusts, use the trustee/representative's SSN last 4.
                For businesses, use the Tax ID last 4. null if not shown at all.
  policies    → Array — one entry per policy/contract found in the document.

For each policy found:
  policyNumber      → Contract or policy number exactly as printed
  carrierName       → Full name of the INSURANCE CARRIER that issued the annuity
                      (e.g. "Crestview Insurance", "Athene Annuity"). This is NOT the BD firm.
  accountType       → Map registration type to exactly one of:
                        individual | joint | trust | custodial | entity
                      (default "individual" if unclear)
  planType          → Map tax qualification to exactly one of:
                        nonQualified | rothIra | traditionalIra | sep | simple
                      (default "nonQualified" if unclear or not shown)
  ownership         → "single" | "joint" | "trust" | "other" — null if not shown
  productName       → Full annuity product name exactly as printed
  cusip             → 9-character CUSIP identifier. Search the ENTIRE document carefully —
                      it may appear in a product details section, header, or footer.
                      Return the value if found; null only if genuinely absent after
                      thorough review.
  trailingCommission → false unless the document explicitly states trailing commission applies
  contractStatus    → Map to exactly one of:
                        active          — policy is in force / issued / current
                        pending         — application submitted, not yet issued
                        surrendered     — contract has been surrendered
                        death claim pending — death claim in process
                      Use "pending" if the document shows status "Pending", "Application",
                      "Not Yet Issued", or similar pre-issuance language.
  withdrawalStructure
    systematicInPlace → true only if document explicitly shows a systematic withdrawal
                        plan is currently active; false otherwise
  errors            → [] (empty — no validation errors at extraction time)

enums (always include these fixed values):
  accountType: ["individual", "joint", "trust", "custodial", "entity"]
  planType:    ["nonQualified", "rothIra", "traditionalIra", "sep", "simple"]

───────────────────────────────────────────────────────────────────────────────
OUTPUT STRUCTURE — return exactly this shape, nothing else:
───────────────────────────────────────────────────────────────────────────────
{
  "policyInquiryResponse": {
    "requestingFirm": {
      "firmName": "...",
      "firmId": null,
      "servicingAgent": { "agentName": "...", "npn": "..." }
    },
    "producerValidation": {
      "agentName": "...",
      "npn": "...",
      "errors": []
    },
    "client": {
      "clientName": "...",
      "ssnLast4": "...",
      "policies": [
        {
          "policyNumber": "...",
          "carrierName": "...",
          "accountType": "individual",
          "planType": "nonQualified",
          "ownership": "single",
          "productName": "...",
          "cusip": null,
          "trailingCommission": false,
          "contractStatus": "active",
          "withdrawalStructure": { "systematicInPlace": false },
          "errors": []
        }
      ]
    },
    "enums": {
      "accountType": ["individual", "joint", "trust", "custodial", "entity"],
      "planType": ["nonQualified", "rothIra", "traditionalIra", "sep", "simple"]
    }
  }
}
"""


def _strip_pdf_fences(text: str) -> str:
    """Strip markdown code fences the model occasionally wraps around JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _extract_from_pdf(pdf_base64: str, request_id: str) -> dict:
    """
    Decode a Base64-encoded policy statement PDF and extract structured data via Bedrock.

    Passes the PDF as a native document block to Claude — no text extraction library needed.
    Returns the parsed policyInquiryResponse dict.
    Raises ValueError on bad base64, json.JSONDecodeError on non-JSON model output.
    """
    try:
        pdf_bytes = base64.b64decode(pdf_base64, validate=False)
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding: {e}") from e

    logger.info("Sending PDF to Bedrock — request_id=%s size=%d bytes",
                request_id, len(pdf_bytes))

    client = boto3.client("bedrock-runtime", region_name=_PDF_REGION)
    response = client.converse(
        modelId=_PDF_MODEL_ID,
        system=[{"text": _PDF_SYSTEM_PROMPT}],
        messages=[{
            "role": "user",
            "content": [
                {
                    "document": {
                        "format": "pdf",
                        "name": "policy_statement",
                        "source": {"bytes": pdf_bytes},
                    }
                },
                {
                    "text": (
                        f"Extract all policy information from this statement. "
                        f"Request ID: {request_id}. "
                        "Return ONLY the JSON object — no other text."
                    )
                },
            ],
        }],
    )

    raw = response["output"]["message"]["content"][0]["text"]
    logger.info("Bedrock extraction complete — request_id=%s", request_id)
    return json.loads(_strip_pdf_fences(raw))


@BP.route('/extract-policy-from-pdf', methods=['POST'])
def extract_policy_from_pdf():
    """
    Extract structured policy data from a Base64-encoded carrier policy statement PDF.

    Passes the PDF natively to Claude via Bedrock converse() and returns a
    policyInquiryResponse matching the Step 2 BD Change process format.
    Each form may vary in the data it provides — all present fields are extracted,
    absent fields are returned as null.

    Required header:
      requestId: <ULID>

    Required body fields:
      requestId   string   Caller-supplied request identifier
      pdfBase64   string   Base64-encoded bytes of the policy statement PDF

    Response codes:
      EXTRACTED        — extraction succeeded; policyInquiryResponse in payload
      INVALID_PDF      — base64 could not be decoded
      EXTRACTION_ERROR — Bedrock call or JSON parse failure
    """
    # Accept requestId header (per unified spec) with requestId fallback
    request_id_header = request.headers.get("requestId") or request.headers.get("requestId")
    if not request_id_header:
        return create_error_response("MISSING_HEADER", "requestId header is required", 400)
    request_id = request_id_header

    data = request.get_json(silent=True)
    if not data:
        return create_error_response("INVALID_PAYLOAD", "JSON request body is required", 400)

    missing = [f for f in ("requestId", "pdfBase64") if not data.get(f)]
    if missing:
        return create_error_response(
            "VALIDATION_ERROR",
            f"Missing required fields: {', '.join(missing)}",
            400,
        )

    request_id = data["requestId"]
    logger.info("PDF extraction — requestId=%s requestId=%s",
                request_id, request_id)

    try:
        result = _extract_from_pdf(data["pdfBase64"], request_id)
    except ValueError as e:
        logger.error("PDF decode error — requestId=%s: %s", request_id, e)
        return create_error_response("INVALID_PDF", str(e), 400)
    except json.JSONDecodeError as e:
        logger.error("Non-JSON model response — requestId=%s: %s", request_id, e)
        return create_error_response(
            "EXTRACTION_ERROR",
            "Model returned non-JSON output. Verify the PDF is a readable policy statement.",
            500,
        )
    except Exception as e:
        logger.error("Extraction failed — requestId=%s: %s", request_id, e, exc_info=True)
        return create_error_response("EXTRACTION_ERROR", str(e), 500)

    policies = (
        (result.get("policyInquiryResponse") or {})
        .get("client", {})
        .get("policies", [])
    )
    logger.info("Extraction successful — requestId=%s policies=%d",
                request_id, len(policies))

    return create_response(
        "EXTRACTED",
        "Policy data extracted from document",
        request_id,
        result,
        200,
        processing_mode="immediate",
    )


# ── Carrier Letter Agent ────────────────────────────────────────────────────────
# Off-DTCC scenario: DTCC returned "no contracts found" — BD must send a formal
# servicing-agent change letter directly to the carrier.
#
# Letter generation is delegated to the AgentCore carrier letter runtime
# (iri_carrier_letter_agent). That runtime runs a Strands Agent which does carrier
# lookup and letter composition. The letter text is returned here, where we render
# the PDF in-memory via fpdf2 and run a QC pass via Bedrock converse() before
# returning the completed letter to the caller.

_CARRIER_DIR_PATH = os.path.join(os.path.dirname(
    __file__), "..", "data", "carrier_directory.json")
_LETTER_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
_LETTER_REGION = "us-east-1"

# AgentCore carrier letter runtime
_LETTER_AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:762233730742:runtime/iri_carrier_letter_agent-6N5TdgCRbG"
_LETTER_AGENT_REGION = "us-east-1"
_LETTER_AGENT_HOST = f"bedrock-agentcore.{_LETTER_AGENT_REGION}.amazonaws.com"


def _load_carrier_directory() -> list[dict]:
    """Load and return the list of carriers from the bundled directory JSON."""
    try:
        with open(_CARRIER_DIR_PATH) as f:
            return json.load(f)["carriers"]
    except Exception:
        return []


def _strip_fences(text: str) -> str:
    """Strip markdown code fences the LLM sometimes wraps around JSON output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _call_letter_agent(payload: dict) -> dict:
    """
    Invoke the AgentCore carrier letter agent via SigV4-signed HTTP POST.

    The runtime runs a Strands agent that calls lookup_carrier and
    generate_change_letter, then returns {"letterText": "...", ...}.

    Args:
        payload: Dict matching the carrier_letter_request schema.

    Returns:
        Response dict with "letterText" key, or {"error": "..."} on failure.
    """
    session = boto3.Session()
    creds = session.get_credentials().get_frozen_credentials()

    session_id = str(uuid.uuid4())
    encoded_arn = quote(_LETTER_AGENT_ARN, safe="")
    url = f"https://{_LETTER_AGENT_HOST}/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    body_bytes = json.dumps(payload).encode("utf-8")

    aws_request = AWSRequest(
        method="POST",
        url=url,
        data=body_bytes,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        },
    )
    SigV4Auth(creds, "bedrock-agentcore", _LETTER_AGENT_REGION).add_auth(aws_request)

    req = URLRequest(url, data=body_bytes, headers=dict(
        aws_request.headers), method="POST")

    try:
        with urlopen(req, timeout=300) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        logger.error("Letter AgentCore HTTP %s: %s", e.code, error_body)
        return {"error": f"AgentCore HTTP {e.code}", "message": error_body}
    except URLError as e:
        logger.error("Letter AgentCore connection error: %s", e)
        return {"error": "AgentCore connection error", "message": str(e)}
    except Exception as e:
        logger.error("Unexpected error calling letter AgentCore: %s", e, exc_info=True)
        return {"error": "AgentCore invocation failed", "message": str(e)}

    # Handle SSE or plain JSON response
    lines = raw.splitlines()
    data_lines = [ln[6:] for ln in lines if ln.startswith("data: ")]
    raw = "".join(data_lines).strip() if data_lines else raw.strip()
    raw = _strip_fences(raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Letter agent non-JSON response (first 500): %s", raw[:500])
        return {"error": "Agent returned non-JSON response", "raw": raw[:500]}


def _letter_to_pdf_base64(letter_text: str) -> str:
    """Render letter_text to a PDF and return it as a Base64 string."""

    def _is_separator(s: str) -> bool:
        return len(s) >= 8 and len(set(s)) == 1 and s[0] in "-=_*"

    def _ascii_safe(s: str) -> str:
        return (
            s.replace("\u2500", "-").replace("\u2502", "|")
             .replace("\u2014", "--").replace("\u2013", "-")
             .replace("\u2022", "*").replace("\u2019", "'")
             .replace("\u2018", "'").replace("\u201c", '"')
             .replace("\u201d", '"').replace("\u2026", "...")
        )

    class LetterPDF(FPDF):
        def header(self):
            self.set_fill_color(30, 60, 114)
            self.rect(0, 0, 210, 12, "F")
            self.set_font("Helvetica", "B", size=9)
            self.set_text_color(255, 255, 255)
            self.set_xy(25, 3)
            self.cell(0, 6, "SERVICING AGENT CHANGE REQUEST  |  CONFIDENTIAL")
            self.set_text_color(0, 0, 0)
            # fpdf2 does not reset the cursor after header() — do it explicitly
            self.set_y(self.t_margin)

        def footer(self):
            self.set_y(-15)
            self.set_draw_color(30, 60, 114)
            self.set_line_width(0.3)
            self.line(25, self.get_y(), 185, self.get_y())
            self.ln(2)
            self.set_font("Helvetica", "I", size=7)
            self.set_text_color(120, 120, 120)
            self.cell(
                0, 4, "Generated by BD Change Process Agent  |  For authorized use only", align="C")

    pdf = LetterPDF()
    pdf.set_margins(left=25, top=20, right=25)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    for line in letter_text.split("\n"):
        stripped = _ascii_safe(line.rstrip())
        if stripped == "":
            pdf.ln(4)
        elif _is_separator(stripped):
            if stripped[0] == "=":
                pdf.set_draw_color(30, 60, 114)
                pdf.set_line_width(0.5)
            else:
                pdf.set_draw_color(180, 180, 180)
                pdf.set_line_width(0.3)
            y = pdf.get_y()
            pdf.line(25, y, 185, y)
            pdf.ln(2)
        else:
            pdf.set_x(pdf.l_margin)
            if stripped.startswith(("Re:", "Dear")):
                pdf.set_font("Helvetica", "B", size=10)
            elif stripped.isupper() and len(stripped) > 8:
                pdf.set_font("Helvetica", "B", size=9)
                pdf.set_text_color(30, 60, 114)
            elif stripped.startswith("_____"):
                pdf.set_font("Helvetica", size=10)
                pdf.set_text_color(0, 0, 0)
            else:
                pdf.set_font("Helvetica", size=9)
                pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 5, stripped)
            pdf.set_text_color(0, 0, 0)

    pdf_bytes = pdf.output()
    return base64.b64encode(pdf_bytes).decode("utf-8")


def _qc_letter_pdf(pdf_base64: str) -> dict:
    """
    Pass the rendered PDF back to Claude as a native document block for quality
    control. Checks that all required sections are present and well-formed.
    Returns {"passed": bool, "notes": str}.
    """
    try:
        pdf_bytes = base64.b64decode(pdf_base64)
        client = boto3.client("bedrock-runtime", region_name=_LETTER_REGION)
        response = client.converse(
            modelId=_LETTER_MODEL_ID,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "document": {
                            "format": "pdf",
                            "name": "carrier_letter",
                            "source": {"bytes": pdf_bytes},
                        }
                    },
                    {
                        "text": (
                            "Review this servicing agent change letter for completeness and quality. "
                            "Verify all required sections are present: carrier name and mailing address, "
                            "client name and SSN last 4, policy number(s), current servicing agent name "
                            "and NPN, new servicing agent name and NPN, broker-dealer name and DTCC ID, "
                            "trailing commission statement, reason for change, and requesting firm "
                            "signature block with contact information. "
                            "Reply with exactly 'QC_PASS' if the letter is complete and well-formed, "
                            "or 'QC_ISSUES: <brief list of problems>' if anything is missing or incorrect."
                        )
                    },
                ],
            }],
        )
        qc_text = response["output"]["message"]["content"][0]["text"].strip()
        return {"passed": qc_text.startswith("QC_PASS"), "notes": qc_text}
    except Exception as exc:
        logger.warning("PDF QC step failed (non-fatal): %s", exc)
        return {"passed": True, "notes": "QC step skipped due to internal error"}


@BP.route('/generate-carrier-letter', methods=['POST'])
def generate_carrier_letter():
    """
    Generate a formal off-DTCC servicing agent change letter addressed to the carrier.

    Used when a DTCC Policy Inquiry returned 'no contracts found' and the broker-dealer
    must contact the carrier directly. Generates both the letter text and a PDF.

    The carrier directory is consulted to fill in the mailing address and surface any
    carrier-specific requirements (proprietary form required, notarization, etc.).

    Required header:
      requestId: <ULID>

    Required body fields (see schemas/carrier_letter_request.schema.json):
      requestId           string   Caller-supplied identifier
      carrierName         string   Carrier name or alias (directory lookup performed)
      client.name         string   Full name of the policy owner
      client.ssnLast4     string   Last 4 digits of SSN
      policyNumbers       array    List of policy/contract numbers
      currentAgent        object   name + npn of agent being replaced
      newAgent            object   name, npn, bdName, bdDtccId of incoming agent
      reasonForChange     string   Plain-language reason
      trailingCommission  string   "yes" | "no" | "unknown"
      requestingFirm      object   name, contact, phone of the submitting BD

    Optional:
      carrierDepartment          string   Overrides directory default
      carrierAddress             object   Full address — required if carrier not in directory
      effectiveDateRequested     string   YYYY-MM-DD; omit for 'as soon as possible'

    Response codes:
      GENERATED           — letter and PDF produced successfully
      CARRIER_OWN_FORM    — carrier requires its own proprietary form; letter not generated
      VALIDATION_ERROR    — missing required fields or carrier address unresolvable
    """
    # Accept requestId header (per unified spec) with requestId fallback
    request_id_header = request.headers.get("requestId") or request.headers.get("requestId")
    if not request_id_header:
        return create_error_response("MISSING_HEADER", "requestId header is required", 400)
    request_id = request_id_header

    data = request.get_json(silent=True)
    if not data:
        return create_error_response("INVALID_PAYLOAD", "JSON request body is required", 400)

    required = ["requestId", "carrierName", "client", "policyNumbers",
                "currentAgent", "newAgent", "reasonForChange",
                "trailingCommission", "requestingFirm"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return create_error_response(
            "VALIDATION_ERROR", f"Missing required fields: {', '.join(missing)}", 400
        )

    request_id = data["requestId"]
    carrier_name_req = data["carrierName"]
    logger.info("Carrier letter generation — requestId=%s requestId=%s carrier=%s",
                request_id, request_id, carrier_name_req)

    # Pre-flight: check if carrier requires a proprietary form (fast directory lookup, no AI).
    # This avoids burning an LLM call for carriers like Nationwide that can never use a generic letter.
    carriers = _load_carrier_directory()
    carrier_record = next(
        (c for c in carriers
         if carrier_name_req.lower() in
         [c["carrier_name"].lower()] + [a.lower() for a in c.get("aliases", [])]),
        None,
    )
    requirements = carrier_record.get("requirements", {}) if carrier_record else {}
    if requirements.get("use_own_form"):
        form_name = requirements.get("own_form_name", "the carrier's proprietary form")
        logger.info("Carrier requires own form — requestId=%s carrier=%s",
                    request_id, carrier_name_req)
        return create_response(
            "CARRIER_OWN_FORM",
            f"{carrier_name_req} requires the use of {form_name}. "
            "A generic letter cannot be generated for this carrier. "
            "Please obtain the carrier's proprietary form.",
            request_id,
            {
                "carrierName": carrier_record["carrier_name"],
                "ownFormName": form_name,
                "notes": requirements.get("notes", ""),
                "portalUrl": carrier_record.get("correspondence", {}).get("portal_url"),
            },
            200,
        )

    # If carrier is not in directory and no address override was supplied, fail fast.
    if not carrier_record and not data.get("carrierAddress"):
        return create_error_response(
            "VALIDATION_ERROR",
            f"Carrier '{carrier_name_req}' not found in directory and no carrierAddress provided.",
            400,
        )

    new_agent = data["newAgent"]
    current_agent = data["currentAgent"]
    client = data["client"]
    firm = data["requestingFirm"]

    # Build the structured payload for the AgentCore carrier letter runtime.
    agent_payload = {
        "carrierName": carrier_name_req,
        "carrierDepartment": data.get("carrierDepartment", ""),
        "carrierAddress": data.get("carrierAddress"),
        "client": {"name": client["name"], "ssnLast4": client["ssnLast4"]},
        "policyNumbers": data["policyNumbers"],
        "currentAgent": {"name": current_agent["name"], "npn": current_agent["npn"]},
        "newAgent": {
            "name": new_agent["name"],
            "npn": new_agent["npn"],
            "bdName": new_agent["bdName"],
            "bdDtccId": new_agent["bdDtccId"],
        },
        "reasonForChange": data["reasonForChange"],
        "trailingCommission": data["trailingCommission"],
        "effectiveDateRequested": data.get("effectiveDateRequested", ""),
        "requestingFirm": {"name": firm["name"], "contact": firm["contact"], "phone": firm["phone"]},
    }

    # Dispatch to AgentCore carrier letter runtime.
    logger.info("Dispatching to AgentCore letter agent — requestId=%s carrier=%s",
                request_id, carrier_name_req)
    try:
        agent_response = _call_letter_agent(agent_payload)
    except Exception as e:
        logger.error("Letter agent dispatch failed — requestId=%s: %s",
                     request_id, e, exc_info=True)
        return create_error_response("GENERATION_ERROR", f"AgentCore error: {e}", 500)

    if "error" in agent_response:
        logger.error("Letter agent returned error — requestId=%s: %s",
                     request_id, agent_response)
        return create_error_response("GENERATION_ERROR",
                                     agent_response.get("error", "Agent error"), 500)

    letter_text = agent_response.get("letterText")
    if not letter_text:
        logger.error("Letter agent returned no letterText — requestId=%s response=%s",
                     request_id, str(agent_response)[:200])
        return create_error_response("GENERATION_ERROR", "Agent did not produce letter text.", 500)

    # Render PDF in-memory.
    try:
        pdf_base64 = _letter_to_pdf_base64(letter_text)
    except Exception as e:
        logger.error("PDF rendering failed — requestId=%s: %s",
                     request_id, e, exc_info=True)
        return create_error_response("GENERATION_ERROR", f"PDF rendering failed: {e}", 500)

    # QC pass — Claude reviews the rendered PDF as a native document block.
    qc = _qc_letter_pdf(pdf_base64)
    logger.info("Letter QC — requestId=%s passed=%s notes=%s",
                request_id, qc["passed"], qc["notes"][:80])

    logger.info("Carrier letter generated — requestId=%s carrier=%s policies=%d qc_passed=%s",
                request_id, carrier_name_req, len(data["policyNumbers"]), qc["passed"])

    payload = {
        "letterText": letter_text,
        "pdfBase64": pdf_base64,
        "qcReview": qc,
        "metadata": {
            "carrier": carrier_record["carrier_name"] if carrier_record else carrier_name_req,
            "client": client["name"],
            "policyNumbers": data["policyNumbers"],
            "newAgent": new_agent["name"],
            "generatedDate": date.today().isoformat(),
            "carrierRequirements": {
                "wetSignatureRequired": requirements.get("wet_signature_required", True),
                "notarizationRequired": requirements.get("notarization_required", False),
                "medallionRequired": requirements.get("medallion_required", False),
                "notes": requirements.get("notes", ""),
                "processingTimeDays": carrier_record.get("processing_time_days") if carrier_record else None,
            } if requirements else {},
        },
    }

    return create_response(
        "GENERATED",
        f"Carrier letter generated for {carrier_name_req}",
        request_id,
        payload,
        200,
        processing_mode="immediate",
    )


@BP.route('/servicing-agent-changes/reply', methods=['POST'])
def bd_change_callback():
    """
    BD change callback - receive carrier validation response.
    Updates transaction status based on approval/rejection.

    Unified API endpoint.
    """
    request_id, error = validate_request_id(request.headers)
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

        logger.info(f"Received carrier response - Transaction ID: {request_id}")
        logger.info(f"Carrier: {data.get('carrierId')}")
        logger.info(f"Policy Number: {data.get('policyNumber')}")
        logger.info(f"Validation Result: {validation_result}")

        # Find and update existing transaction
        record, table_name = find_transaction_by_id(request_id)

        if record:
            new_status = "CARRIER_APPROVED" if validation_result == "approved" else "CARRIER_REJECTED"
            notes = f"Carrier {validation_result} the BD change request"
            if validation_result == 'rejected':
                rejection_reason = data.get('rejectionReason', 'Not provided')
                notes += f": {rejection_reason}"

            update_transaction_status(
                table_name,
                record["pk"],
                record["sk"],
                new_status,
                notes
            )
            logger.info(f"Updated transaction {request_id} to {new_status}")

        return create_response(
            "RECEIVED",
            f"Carrier validation response received - {validation_result}",
            request_id
        )

    except Exception as e:
        logger.error(f"Error processing carrier response: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/transfer-notifications/reply', methods=['POST'], strict_slashes=False)
def transfer_confirmation():
    """
    Transfer confirmation - accept transfer confirmation.
    Updates transaction status to TRANSFER_CONFIRMED or COMPLETE.

    Unified API endpoint.
    """
    request_id, error = validate_request_id(request.headers)
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

        logger.info(f"Received transfer confirmation - Transaction ID: {request_id}")
        logger.info(f"Policy Number: {data.get('policyNumber')}")
        logger.info(f"Confirmation Status: {confirmation_status}")

        # Find and update existing transaction
        record, table_name = find_transaction_by_id(request_id)

        if record:
            if confirmation_status == "confirmed":
                update_transaction_status(
                    table_name,
                    record["pk"],
                    record["sk"],
                    "TRANSFER_CONFIRMED",
                    "Transfer confirmed"
                )
                update_transaction_status(
                    table_name,
                    record["pk"],
                    record["sk"],
                    "COMPLETE",
                    "BD change process completed successfully"
                )
                logger.info(f"Updated transaction {request_id} to COMPLETE")
            elif confirmation_status == "failed":
                update_transaction_status(
                    table_name,
                    record["pk"],
                    record["sk"],
                    "TRANSFER_PROCESSING",
                    f"Transfer confirmation failed"
                )

        return create_response(
            "RECEIVED",
            f"Transfer confirmation received - {confirmation_status}",
            request_id
        )

    except Exception as e:
        logger.error(f"Error processing transfer confirmation: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/status/<requestId>', methods=['GET'], strict_slashes=False)
def query_status(requestId):
    """
    Query transaction status.
    Retrieve current status and history for a specific transaction from distributor tables.

    Unified API endpoint.
    """
    try:
        # Validate UUID format
        try:
            uuid.UUID(requestId)
        except ValueError:
            return create_error_response(
                "INVALID_REQUEST_ID",
                "Request ID must be a valid UUID",
                400
            )

        logger.info(f"Querying status for request: {requestId}")

        # Search for transaction in distributor tables
        record, table_name = find_transaction_by_id(requestId)

        if not record:
            return create_error_response(
                "NOT_FOUND",
                f"Request {requestId} not found",
                404
            )

        # Format response
        status_data = {
            "requestId": record.get("request-id"),
            "currentStatus": record.get("current-status"),
            "createdAt": record.get("created-at"),
            "updatedAt": record.get("updated-at"),
            "brokerRole": record.get("broker-role"),
            "statusHistory": record.get("status-history", []),
            "policyId": record.get("policy-id"),
            "carrierId": record.get("carrier-id"),
            "clientDetails": record.get("client-details"),
            "firmDetails": record.get("firm-details"),
            "agentDetails": record.get("agent-details"),
            "receivingBroker": record.get("receiving-broker"),
            "deliveringBroker": record.get("delivering-broker"),
        }

        # Include validation result if present
        if "validation-result" in record:
            status_data["validationResult"] = record["validation-result"]

        # Include latest notification if present
        if "latest-notification" in record:
            status_data["latestNotification"] = record["latest-notification"]

        return jsonify(status_data), 200

    except Exception as e:
        logger.error(f"Error querying request status: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )
