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
from dotenv import load_dotenv
import boto3
from fpdf import FPDF
load_dotenv(override=False)
sys.path.insert(0, "../")
sys.path.insert(0, "../../")
from helpers import (create_response,
                     create_error_response,
                     validate_transaction_id)
from lib.utils.dynamodb_utils import get_item, put_item, update_item, scan_items, Attr

BP = Blueprint('broker-dealer', __name__)

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


def find_transaction_by_id(transaction_id: str, table_name: str = None):
    """
    Find a transaction by ID across distributor tables.
    Returns (record, table_name) or (None, None).
    """
    tables_to_search = [table_name] if table_name else ["distributor", "distributor-2"]

    for table in tables_to_search:
        try:
            items = scan_items(
                table,
                Attr("transaction-id").eq(transaction_id)
            )
            if items:
                return items[0], table
        except Exception as e:
            logger.error(f"Error scanning {table}: {e}")

    return None, None


def create_transaction_record(
    transaction_id: str,
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
        "sk": f"TRANSACTION#{transaction_id}",
        "transaction-id": transaction_id,
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


@BP.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "broker-dealer-api",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


@BP.route('/policy-inquiry', methods=['POST'])
def policy_inquiry():
    """
    Process policy inquiry request.
    Endpoint for delivering broker-dealer - receives from clearinghouse or direct.
    Stores the request in the distributor table.

    Unified API endpoint - replaces /submit-policy-inquiry-request
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

        logger.info(f"Received policy inquiry request - Transaction ID: {transaction_id}")
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
            transaction_id=transaction_id,
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
        logger.info(f"Stored transaction {transaction_id} in {table_name}")

        return create_response(
            "RECEIVED",
            "Policy inquiry request received and stored",
            transaction_id,
            processing_mode="deferred"
        )

    except Exception as e:
        logger.error(f"Error processing policy inquiry request: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/policy-inquiry-callback', methods=['POST'])
def policy_inquiry_callback():
    """
    Policy inquiry callback - receive policy inquiry response.
    Endpoint for receiving broker-dealer - receives from clearinghouse or direct.
    Updates the transaction status to MANIFEST_RECEIVED.

    Unified API endpoint - replaces /receive-policy-inquiry-response
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
            f"Received policy inquiry response - Transaction ID: {transaction_id}")
        logger.info(f"Client: {data.get('client', {}).get('clientName')}")

        # Find and update existing transaction
        record, table_name = find_transaction_by_id(transaction_id)

        if record:
            update_transaction_status(
                table_name,
                record["pk"],
                record["sk"],
                "MANIFEST_RECEIVED",
                "Policy inquiry response received from clearinghouse"
            )
            logger.info(f"Updated transaction {transaction_id} to MANIFEST_RECEIVED")
        else:
            logger.warning(
                f"Transaction {transaction_id} not found in distributor tables")

        return create_response(
            "RECEIVED",
            "Policy inquiry response received successfully",
            transaction_id
        )

    except Exception as e:
        logger.error(f"Error processing policy inquiry response: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/bd-change', methods=['POST'])
def bd_change():
    """
    Brokerage dealer change request.
    Endpoint for receiving broker-dealer - receives from clearinghouse or direct.
    Updates transaction status.

    Unified API endpoint - replaces /receive-bd-change-request
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

        # Validate required fields
        required_fields = ['transaction-id', 'receiving-broker-id', 'delivering-broker-id',
                           'carrier-id', 'policy-id']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        logger.info(f"Received BD change request - Transaction ID: {transaction_id}")
        logger.info(f"Policy ID: {data.get('policy-id')}")
        logger.info(f"Receiving Broker: {data.get('receiving-broker-id')}")
        logger.info(f"Delivering Broker: {data.get('delivering-broker-id')}")

        # Find and update existing transaction
        record, table_name = find_transaction_by_id(transaction_id)

        if record:
            update_transaction_status(
                table_name,
                record["pk"],
                record["sk"],
                "DUE_DILIGENCE_COMPLETE",
                "BD change request received, due diligence complete"
            )
            logger.info(f"Updated transaction {transaction_id} to DUE_DILIGENCE_COMPLETE")

        return create_response(
            "RECEIVED",
            "BD change request received successfully",
            transaction_id
        )

    except Exception as e:
        logger.error(f"Error processing BD change request: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/transfer-notification', methods=['POST'])
def transfer_notification():
    """
    Transfer notification - accept transfer-related notifications.
    Receives from clearinghouse or direct.
    Accepts transfer-related notifications and updates status.

    Unified API endpoint - replaces /receive-transfer-notification
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

        logger.info(f"Received transfer notification - Transaction ID: {transaction_id}")
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
        record, table_name = find_transaction_by_id(transaction_id)

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
            logger.info(f"Updated transaction {transaction_id} to {new_status}")

        return create_response(
            "RECEIVED",
            f"Transfer notification '{notification_type}' received successfully",
            transaction_id
        )

    except Exception as e:
        logger.error(f"Error processing transfer notification: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


# ── PDF Policy Statement Extractor ─────────────────────────────────────────────
# Uses Claude via Bedrock converse() with a native document block.
# No text-extraction library needed — Claude reads the PDF layout directly.

_PDF_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
_PDF_REGION   = "us-east-1"

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

    logger.info("Sending PDF to Bedrock — request_id=%s size=%d bytes", request_id, len(pdf_bytes))

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
      transactionId: <UUID>

    Required body fields:
      requestId   string   Caller-supplied request identifier
      pdfBase64   string   Base64-encoded bytes of the policy statement PDF

    Response codes:
      EXTRACTED        — extraction succeeded; policyInquiryResponse in payload
      INVALID_PDF      — base64 could not be decoded
      EXTRACTION_ERROR — Bedrock call or JSON parse failure
    """
    transaction_id, error = validate_transaction_id(request.headers)
    if error:
        return error

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
    logger.info("PDF extraction — transactionId=%s requestId=%s", transaction_id, request_id)

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
    logger.info("Extraction successful — requestId=%s policies=%d", request_id, len(policies))

    return create_response(
        "EXTRACTED",
        "Policy data extracted from document",
        transaction_id,
        result,
        200,
        processing_mode="immediate",
    )


# ── Carrier Letter Generator ────────────────────────────────────────────────────
# Off-DTCC scenario: DTCC returned "no contracts found", so the BD must send a
# formal servicing-agent change letter directly to the carrier.
# Uses the carrier directory bundled in api/data/carrier_directory.json.

_CARRIER_DIR_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "carrier_directory.json")

def _load_carrier_directory() -> list[dict]:
    """Load and return the list of carriers from the bundled directory JSON."""
    try:
        with open(_CARRIER_DIR_PATH) as f:
            return json.load(f)["carriers"]
    except Exception:
        return []


def _lookup_carrier(carrier_name: str, carriers: list[dict]) -> dict | None:
    """Return the carrier record for an exact or alias match, or None."""
    name_lower = carrier_name.lower().strip()
    for c in carriers:
        if c["carrier_name"].lower() == name_lower:
            return c
        if any(alias.lower() == name_lower for alias in c.get("aliases", [])):
            return c
    # Partial match fallback
    for c in carriers:
        candidates = [c["carrier_name"]] + c.get("aliases", [])
        if any(name_lower in x.lower() or x.lower() in name_lower for x in candidates):
            return c
    return None


def _build_letter(
    carrier_name: str,
    carrier_department: str,
    carrier_address_block: str,
    client_name: str,
    client_ssn_last4: str,
    policy_numbers: list[str],
    current_agent_name: str,
    current_agent_npn: str,
    new_agent_name: str,
    new_agent_npn: str,
    new_bd_name: str,
    new_bd_dtcc_id: str,
    reason_for_change: str,
    requesting_firm_name: str,
    requesting_firm_contact: str,
    requesting_firm_phone: str,
    trailing_commission: str,
    effective_date_requested: str,
) -> str:
    """Assemble the formal servicing-agent change letter text."""
    today = date.today().strftime("%B %d, %Y")

    policy_ref = ", ".join(policy_numbers) if len(policy_numbers) <= 3 else (
        ", ".join(policy_numbers[:3]) + f", and {len(policy_numbers) - 3} additional"
    )

    eff_line = (
        f"Requested Effective Date:  {effective_date_requested}"
        if effective_date_requested
        else "Requested Effective Date:  As soon as administratively possible"
    )

    tc_map = {
        "yes":     "The new servicing agent WILL receive trailing commissions on this contract.",
        "no":      "The new servicing agent will NOT receive trailing commissions on this contract.",
        "unknown": "Please apply your standard trailing commission arrangement for the new servicing agent.",
    }
    tc_line = tc_map.get(trailing_commission.lower(), tc_map["unknown"])

    SEP = "-" * 72

    return f"""{requesting_firm_name}
{"=" * len(requesting_firm_name)}
Contact: {requesting_firm_contact}
Phone:   {requesting_firm_phone}
Date:    {today}


{carrier_name}
{carrier_department}
{carrier_address_block}


Re:   Request for Servicing Agent / Broker of Record Change
      Policy Number(s): {policy_ref}
      Policyholder:     {client_name} (SSN last 4: {client_ssn_last4})


Dear {carrier_department},

We are writing on behalf of {new_bd_name} (DTCC Firm ID: {new_bd_dtcc_id}) to formally
request a change of servicing agent for the above-referenced annuity contract(s).
This request is made with the full knowledge and authorization of the policy owner.

Please note: A policy inquiry was submitted through DTCC and returned no contracts
found, indicating these contracts are not currently accessible via the DTCC platform.
We are therefore submitting this request directly to your company.

{SEP}
  CONTRACT INFORMATION
{SEP}
  Policyholder:           {client_name}
  SSN (last 4 digits):    {client_ssn_last4}
  Policy Number(s):       {", ".join(policy_numbers)}

{SEP}
  CURRENT SERVICING AGENT (TO BE REMOVED)
{SEP}
  Agent Name:             {current_agent_name}
  National Producer No.:  {current_agent_npn}

{SEP}
  NEW SERVICING AGENT (TO BE ASSIGNED)
{SEP}
  Agent Name:             {new_agent_name}
  National Producer No.:  {new_agent_npn}
  Broker/Dealer:          {new_bd_name}
  DTCC Firm ID:           {new_bd_dtcc_id}
  {eff_line}

{SEP}
  TRAILING COMMISSION
{SEP}
  {tc_line}

{SEP}
  REASON FOR CHANGE
{SEP}
  {reason_for_change}

We represent that the incoming servicing agent, {new_agent_name} (NPN: {new_agent_npn}),
holds all required licenses in the applicable jurisdiction(s) and has an active
appointment with {carrier_name}. Supporting documentation is enclosed if required.

Please process this servicing agent change at your earliest convenience and
confirm completion in writing to the contact listed above.

If you have any questions or require additional documentation, please do not
hesitate to contact us.

Sincerely,


_________________________________________
{requesting_firm_contact}
Authorized Representative, {requesting_firm_name}


Enclosures (as applicable):
  * Copy of policy owner authorization / client signature
  * Incoming producer's state insurance license(s)
  * Carrier appointment confirmation for {new_agent_name}
  * DTCC "no contracts found" response (if available)
"""


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

    pdf = FPDF()
    pdf.set_margins(left=25, top=25, right=25)
    pdf.add_page()

    # Header band
    pdf.set_fill_color(30, 60, 114)
    pdf.rect(0, 0, 210, 12, "F")
    pdf.set_font("Helvetica", "B", size=9)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(25, 3)
    pdf.cell(0, 6, "SERVICING AGENT CHANGE REQUEST  |  CONFIDENTIAL", ln=True)

    pdf.set_text_color(0, 0, 0)
    pdf.set_y(20)

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

    # Footer
    pdf.set_y(-18)
    pdf.set_draw_color(30, 60, 114)
    pdf.set_line_width(0.3)
    pdf.line(25, pdf.get_y(), 185, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", size=7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 4, "Generated by BD Change Process Agent  |  For authorized use only", align="C")

    pdf_bytes = pdf.output()
    return base64.b64encode(pdf_bytes).decode("utf-8")


@BP.route('/generate-carrier-letter', methods=['POST'])
def generate_carrier_letter():
    """
    Generate a formal off-DTCC servicing agent change letter addressed to the carrier.

    Used when a DTCC Policy Inquiry returned 'no contracts found' and the broker-dealer
    must contact the carrier directly. Generates both the letter text and a PDF.

    The carrier directory is consulted to fill in the mailing address and surface any
    carrier-specific requirements (proprietary form required, notarization, etc.).

    Required header:
      transactionId: <UUID>

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
    transaction_id, error = validate_transaction_id(request.headers)
    if error:
        return error

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
    logger.info("Carrier letter generation — transactionId=%s requestId=%s", transaction_id, request_id)

    # Carrier lookup
    carriers = _load_carrier_directory()
    carrier_record = _lookup_carrier(data["carrierName"], carriers)

    # Surface carrier-specific requirements
    requirements = carrier_record.get("requirements", {}) if carrier_record else {}
    if requirements.get("use_own_form"):
        form_name = requirements.get("own_form_name", "the carrier's proprietary form")
        logger.info("Carrier requires own form — requestId=%s carrier=%s", request_id, data["carrierName"])
        return create_response(
            "CARRIER_OWN_FORM",
            f"{data['carrierName']} requires the use of {form_name}. "
            "A generic letter cannot be generated for this carrier. "
            "Please obtain the carrier's proprietary form.",
            transaction_id,
            {
                "carrierName": carrier_record["carrier_name"],
                "ownFormName": form_name,
                "notes": requirements.get("notes", ""),
                "portalUrl": carrier_record.get("correspondence", {}).get("portal_url"),
            },
            200,
        )

    # Resolve carrier address
    addr_override = data.get("carrierAddress")
    if addr_override:
        addr_lines = [addr_override["line1"]]
        if addr_override.get("line2"):
            addr_lines.append(addr_override["line2"])
        addr_lines.append(f"{addr_override['city']}, {addr_override['state']} {addr_override['zip']}")
        carrier_address_block = "\n".join(addr_lines)
        carrier_full_name = data["carrierName"]
        carrier_department = data.get("carrierDepartment", "Annuity Service Center")
    elif carrier_record:
        corr = carrier_record.get("correspondence", {})
        addr = corr.get("address", {})
        addr_lines = [addr.get("line1", "")]
        if addr.get("line2"):
            addr_lines.append(addr["line2"])
        addr_lines.append(f"{addr.get('city', '')}, {addr.get('state', '')} {addr.get('zip', '')}")
        carrier_address_block = "\n".join(addr_lines)
        carrier_full_name = carrier_record["carrier_name"]
        carrier_department = data.get("carrierDepartment") or carrier_record.get("servicing_department", "Annuity Service Center")
    else:
        return create_error_response(
            "VALIDATION_ERROR",
            f"Carrier '{data['carrierName']}' not found in directory and no carrierAddress provided.",
            400,
        )

    client = data["client"]
    new_agent = data["newAgent"]
    current_agent = data["currentAgent"]
    firm = data["requestingFirm"]

    try:
        letter_text = _build_letter(
            carrier_name=carrier_full_name,
            carrier_department=carrier_department,
            carrier_address_block=carrier_address_block,
            client_name=client["name"],
            client_ssn_last4=client["ssnLast4"],
            policy_numbers=data["policyNumbers"],
            current_agent_name=current_agent["name"],
            current_agent_npn=current_agent["npn"],
            new_agent_name=new_agent["name"],
            new_agent_npn=new_agent["npn"],
            new_bd_name=new_agent["bdName"],
            new_bd_dtcc_id=new_agent["bdDtccId"],
            reason_for_change=data["reasonForChange"],
            requesting_firm_name=firm["name"],
            requesting_firm_contact=firm["contact"],
            requesting_firm_phone=firm["phone"],
            trailing_commission=data["trailingCommission"],
            effective_date_requested=data.get("effectiveDateRequested", ""),
        )
        pdf_base64 = _letter_to_pdf_base64(letter_text)
    except Exception as e:
        logger.error("Letter generation failed — requestId=%s: %s", request_id, e, exc_info=True)
        return create_error_response("GENERATION_ERROR", str(e), 500)

    logger.info("Carrier letter generated — requestId=%s carrier=%s policies=%d",
                request_id, carrier_full_name, len(data["policyNumbers"]))

    payload = {
        "letterText": letter_text,
        "pdfBase64": pdf_base64,
        "metadata": {
            "carrier": carrier_full_name,
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
        f"Carrier letter generated for {carrier_full_name}",
        transaction_id,
        payload,
        200,
        processing_mode="immediate",
    )


@BP.route('/bd-change-callback', methods=['POST'])
def bd_change_callback():
    """
    BD change callback - receive carrier validation response.
    Updates transaction status based on approval/rejection.

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

        logger.info(f"Received carrier response - Transaction ID: {transaction_id}")
        logger.info(f"Carrier: {data.get('carrierId')}")
        logger.info(f"Policy Number: {data.get('policyNumber')}")
        logger.info(f"Validation Result: {validation_result}")

        # Find and update existing transaction
        record, table_name = find_transaction_by_id(transaction_id)

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
            logger.info(f"Updated transaction {transaction_id} to {new_status}")

        return create_response(
            "RECEIVED",
            f"Carrier validation response received - {validation_result}",
            transaction_id
        )

    except Exception as e:
        logger.error(f"Error processing carrier response: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/transfer-confirmation', methods=['POST'])
def transfer_confirmation():
    """
    Transfer confirmation - accept transfer confirmation.
    Updates transaction status to TRANSFER_CONFIRMED or COMPLETE.

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

        # Find and update existing transaction
        record, table_name = find_transaction_by_id(transaction_id)

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
                logger.info(f"Updated transaction {transaction_id} to COMPLETE")
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
            transaction_id
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
    Query transaction status.
    Retrieve current status and history for a specific transaction from distributor tables.

    Unified API endpoint.
    """
    try:
        # Validate UUID format
        try:
            uuid.UUID(transaction_id)
        except ValueError:
            return create_error_response(
                "INVALID_TRANSACTION_ID",
                "Transaction ID must be a valid UUID",
                400
            )

        logger.info(f"Querying status for transaction: {transaction_id}")

        # Search for transaction in distributor tables
        record, table_name = find_transaction_by_id(transaction_id)

        if not record:
            return create_error_response(
                "NOT_FOUND",
                f"Transaction {transaction_id} not found",
                404
            )

        # Format response
        status_data = {
            "transaction-id": record.get("transaction-id"),
            "current-status": record.get("current-status"),
            "created-at": record.get("created-at"),
            "updated-at": record.get("updated-at"),
            "broker-role": record.get("broker-role"),
            "status-history": record.get("status-history", []),
            "policy-id": record.get("policy-id"),
            "carrier-id": record.get("carrier-id"),
            "client-details": record.get("client-details"),
            "firm-details": record.get("firm-details"),
            "agent-details": record.get("agent-details"),
            "receiving-broker": record.get("receiving-broker"),
            "delivering-broker": record.get("delivering-broker"),
        }

        # Include validation result if present
        if "validation-result" in record:
            status_data["validation-result"] = record["validation-result"]

        # Include latest notification if present
        if "latest-notification" in record:
            status_data["latest-notification"] = record["latest-notification"]

        return jsonify(status_data), 200

    except Exception as e:
        logger.error(f"Error querying transaction status: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )
