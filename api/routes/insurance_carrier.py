"""
Insurance Carrier API Flask Application
Implements the OpenAPI specification for insurance carrier endpoints
"""

from flask import request, jsonify, Blueprint
from datetime import datetime
import uuid
import logging
from helpers import (create_response,
                     create_error_response,
                     validate_transaction_id)
from dynamodb_utils import get_item, scan_items, Attr

BP = Blueprint('insurance-carrier', __name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrier table mapping
CARRIER_TABLES = {
    "ATH": {"table": "carrier", "carrierName": "Athene"},
    "PAC": {"table": "carrier-2", "carrierName": "Pacific Life"},
    "PRU": {"table": "carrier-3", "carrierName": "Prudential"},
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


def format_policy_for_response(policy: dict, client_ssn: str = None) -> dict:
    """
    Format a carrier DB policy record to PolicyInquiryResponse DetailedPolicyInfo format.
    """
    errors = []

    # Check SSN match if provided
    if client_ssn and policy.get("ownerSSN") != client_ssn:
        errors.append({
            "errorCode": "ssnContractMismatch",
            "message": "Client's SSN does not match the contract on file"
        })

    # Check policy status
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
    # In production, this would check:
    # - Producer is licensed in the relevant state
    # - Producer is appointed with the carrier
    # - Producer affiliation matches the requesting firm
    return []


@BP.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "insurance-carrier-api",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


@BP.route('/submit-policy-inquiry-request', methods=['POST'])
def submit_policy_inquiry_request():
    """
    Receive policy inquiry request (direct or via clearinghouse)

    Accept policy inquiry request to provide policy information for specified accounts.
    Carrier responds immediately with policy data from carrier tables.
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

        # Validate required fields per PolicyInquiryRequest schema
        if 'requestingFirm' not in data:
            return create_error_response(
                "VALIDATION_ERROR",
                "Missing required field: requestingFirm",
                400
            )
        if 'client' not in data:
            return create_error_response(
                "VALIDATION_ERROR",
                "Missing required field: client",
                400
            )

        requesting_firm = data.get('requestingFirm', {})
        client = data.get('client', {})
        servicing_agent = requesting_firm.get('servicingAgent', {})

        logger.info(f"Received policy inquiry request - Transaction ID: {transaction_id}")
        logger.info(f"Requesting Firm: {requesting_firm.get('firmName')}")
        logger.info(f"Agent: {servicing_agent.get('agentName')}")
        logger.info(f"Client: {client.get('clientName')}")
        logger.info(f"Policy Numbers: {client.get('policyNumbers', [])}")

        # Extract request data
        client_ssn = client.get('ssn')
        policy_numbers = client.get('policyNumbers', [])

        # Validate producer (licensing, appointments)
        producer_errors = validate_producer(
            servicing_agent.get('agentName'),
            servicing_agent.get('npn')
        )

        # Look up policies from carrier tables
        policies = []
        client_name_from_db = None
        ssn_last4 = client_ssn[-4:] if client_ssn and len(client_ssn) >= 4 else None

        for policy_number in policy_numbers:
            policy = lookup_policy(policy_number)
            if policy:
                # Capture client name from first found policy
                if not client_name_from_db:
                    client_name_from_db = policy.get('clientName')
                    # Get SSN last 4 from DB if not provided in request
                    if not ssn_last4 and policy.get('ownerSSN'):
                        ssn_last4 = policy.get('ownerSSN')[-4:]

                formatted_policy = format_policy_for_response(policy, client_ssn)
                policies.append(formatted_policy)
            else:
                # Policy not found - add error entry
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
                    "errors": [{
                        "errorCode": "policyNotFound",
                        "message": f"Policy {policy_number} not found in carrier records"
                    }]
                })

        # Build PolicyInquiryResponse payload
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
            f"Returning {len(policies)} policies for transaction {transaction_id}")

        # Return immediate response with policy data
        return create_response(
            "IMMEDIATE",
            "Policy inquiry processed successfully",
            transaction_id,
            response_payload,
            200,
            processing_mode="immediate"
        )

    except Exception as e:
        logger.error(f"Error processing policy inquiry request: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/submit-policy-inquiry-response', methods=['POST'])
def submit_policy_inquiry_response():
    """
    Submit policy inquiry response to clearinghouse

    Submit detailed policy information response to clearinghouse after
    processing a deferred request.
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

        # Validate required fields per PolicyInquiryResponse schema
        required_fields = ['requestingFirm', 'producerValidation', 'client', 'enums']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        logger.info(
            f"Submitting policy inquiry response - Transaction ID: {transaction_id}")
        logger.info(f"Client: {data.get('client', {}).get('clientName')}")
        logger.info(f"Policies count: {len(data.get('client', {}).get('policies', []))}")

        # TODO: Forward response to clearinghouse
        # - Validate response structure
        # - Send to clearinghouse endpoint
        # - Update transaction status

        return create_response(
            "RECEIVED",
            "Policy inquiry response submitted successfully",
            transaction_id,
            None,
            200
        )

    except Exception as e:
        logger.error(f"Error submitting policy inquiry response: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/receive-bd-change-request', methods=['POST'])
def receive_bd_change_request():
    """
    Receive BD change validation request from clearinghouse
    Validates and approves/rejects broker-dealer changes

    The carrier performs validation checks including:
    - Agent licensing verification
    - Carrier appointment verification
    - Suitability requirements
    - Policy-specific rules
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
        required_fields = ['receivingBrokerId',
                           'deliveringBrokerId', 'carrierId', 'policyNumber']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        logger.info(
            f"Received BD change validation request - Transaction ID: {transaction_id}")
        logger.info(f"Policy Number: {data.get('policyNumber')}")
        logger.info(f"Receiving Broker: {data.get('receivingBrokerId')}")
        logger.info(f"Delivering Broker: {data.get('deliveringBrokerId')}")
        logger.info(f"Carrier: {data.get('carrierId')}")

        # TODO: Perform validation checks:
        # - Verify agent licensing
        # - Check carrier appointments
        # - Validate suitability requirements
        # - Check policy-specific rules
        # - Store validation request in database

        # Options for response:
        # 1. Immediate processing and response
        # 2. Deferred processing with estimated time

        # For immediate processing (uncomment if applicable):
        # validation_result = perform_validation(data)
        # send_validation_response_to_clearinghouse(transaction_id, validation_result)
        # return create_response(
        #     "APPROVED",
        #     "BD change request validated and approved",
        #     "processing",
        #     None,
        #     200
        # )

        # For deferred processing:
        return create_response(
            "RECEIVED",
            "BD change validation request received and queued for processing",
            transaction_id,
            None,
            200,
            processing_mode="deferred",
            estimated_response_time="PT24H"
        )

    except Exception as e:
        logger.error(f"Error processing BD change request: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/receive-transfer-notification', methods=['POST'])
def receive_transfer_notification():
    """
    Receive transfer notification from clearinghouse
    Accept final service agent change notification
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
        required_fields = ['notificationType', 'policyNumber', 'carrierId']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        notification_type = data.get('notificationType')
        if notification_type != 'service-agent-change-complete':
            return create_error_response(
                "VALIDATION_ERROR",
                "notificationType must be 'service-agent-change-complete'",
                400
            )

        logger.info(f"Received transfer notification - Transaction ID: {transaction_id}")
        logger.info(f"Notification Type: {notification_type}")
        logger.info(f"Policy Number: {data.get('policyNumber')}")
        logger.info(f"Carrier: {data.get('carrierId')}")
        logger.info(f"New Broker: {data.get('receivingBrokerId')}")
        logger.info(f"Previous Broker: {data.get('deliveringBrokerId')}")
        logger.info(f"Effective Date: {data.get('effectiveDate')}")

        # TODO: Process transfer notification:
        # - Update policy servicing agent records
        # - Update commission structures
        # - Trigger internal workflows
        # - Send confirmations to stakeholders
        # - Store notification in database

        return create_response(
            "RECEIVED",
            "Transfer notification received and processed",
            transaction_id,
            None,
            200,
            processing_mode="immediate"
        )

    except Exception as e:
        logger.error(f"Error processing transfer notification: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/query-status/<transaction_id>', methods=['GET'])
def query_status(transaction_id):
    """
    Query transaction status
    Retrieve current status and history for a specific transaction
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

        # TODO: Retrieve from database
        # For demo purposes, return mock data

        # Simulate not found scenario (can be removed in production)
        # return create_error_response(
        #     "NOT_FOUND",
        #     f"Transaction {transaction_id} not found",
        #     404
        # )

        # Mock response
        status_data = {
            "currentStatus": "CARRIER_APPROVED",
            "createdAt": "2026-02-24T10:30:00Z",
            "updatedAt": "2026-02-24T11:00:00Z",
            "statusHistory": [
                {
                    "status": "CARRIER_VALIDATION_PENDING",
                    "timestamp": "2026-02-24T10:30:00Z",
                    "notes": "BD change validation request received from clearinghouse"
                },
                {
                    "status": "CARRIER_APPROVED",
                    "timestamp": "2026-02-24T11:00:00Z",
                    "notes": "All validation checks passed - approved"
                }
            ],
            "carrierValidationDetails": {
                "licensingCheck": "passed",
                "appointmentCheck": "passed",
                "suitabilityCheck": "passed",
                "policyRulesCheck": "passed",
                "validatedBy": "System Automated Validation",
                "validationTimestamp": "2026-02-24T11:00:00Z"
            },
            "policiesAffected": ["POL-001"],
            "additionalData": {
                "carrier": "CARRIER-PL",
                "policyNumber": "POL-001",
                "newBroker": "BROKER-001",
                "previousBroker": "BROKER-002"
            }
        }

        return jsonify(status_data), 200

    except Exception as e:
        logger.error(f"Error querying transaction status: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )
