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

# Carrier table mapping by policy prefix
CARRIER_TABLES = {
    "ATH": {"table": "carrier", "carrierName": "Athene"},
    "PAC": {"table": "carrier-2", "carrierName": "Pacific Life"},
    "PRU": {"table": "carrier-3", "carrierName": "Prudential"},
}

# Carrier-specific configurations for direct carrier endpoints
CARRIER_CONFIGS = {
    "athene": {"table": "carrier", "carrierName": "Athene", "prefix": "ATH"},
    "paclife": {"table": "carrier-2", "carrierName": "Pacific Life", "prefix": "PAC"},
    "prudential": {"table": "carrier-3", "carrierName": "Prudential", "prefix": "PRU"},
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


def lookup_policy_from_table(policy_number: str, table_name: str, carrier_name: str) -> dict:
    """
    Look up a policy from a specific carrier table.
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
    expected_prefix = carrier_config["prefix"]

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
            # Validate policy belongs to this carrier
            if not policy_number.startswith(expected_prefix):
                policies.append({
                    "policyNumber": policy_number,
                    "carrierName": carrier_name,
                    "errors": [{
                        "errorCode": "wrongCarrier",
                        "message": f"Policy {policy_number} does not belong to {carrier_name}"
                    }]
                })
                continue

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

        logger.info(f"[{carrier_name}] Returning {len(policies)} policies for transaction {transaction_id}")

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


@BP.route('/bd-change', methods=['POST'])
def bd_change():
    """
    Brokerage dealer change request.
    Validates and approves/rejects broker-dealer changes.

    The carrier performs validation checks including:
    - Agent licensing verification
    - Carrier appointment verification
    - Suitability requirements
    - Policy-specific rules

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
        valid_types = ['transfer-approved', 'transfer-initiated', 'transfer-confirmed',
                       'transfer-complete', 'service-agent-change-complete']
        if notification_type not in valid_types:
            return create_error_response(
                "VALIDATION_ERROR",
                f"notificationType must be one of: {', '.join(valid_types)}",
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
            f"Transfer notification '{notification_type}' received and processed",
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
