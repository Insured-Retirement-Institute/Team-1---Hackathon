"""
Clearinghouse API Flask Application
Implements the OpenAPI specification for clearinghouse endpoints
Integrated with DynamoDB request-tracking table.
"""
import os
from flask import request, jsonify, Blueprint
from datetime import datetime, timezone
import sys
import uuid
import logging
from helpers import (create_response,
                     create_error_response,
                     validate_transaction_id)
sys.path.insert(0, "../")
sys.path.insert(0, "../../")
from lib.utils.dynamodb_utils import get_item, put_item, update_item, scan_items, query_items, Attr, Key

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BP = Blueprint('clearinghouse', __name__)

# Table names
REQUEST_TRACKING_TABLE = os.environ.get("REQUEST_TRACKING_TABLE", "request-tracking")
IIEX_TABLE = os.environ.get("IIEX_TABLE", "iiex")

# Carrier name mapping by policy prefix (for IIEX lookups)
CARRIER_NAME_BY_PREFIX = {
    "ATH": "Athene",
    "PAC": "Pacific Life",
    "PRU": "Prudential",
}

# Value mappings for IIEX responses
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

# Status constants
STATUSES = [
    "MANIFEST_REQUESTED",
    "MANIFEST_RECEIVED",
    "DUE_DILIGENCE_COMPLETE",
    "CARRIER_VALIDATION_PENDING",
    "CARRIER_APPROVED",
    "CARRIER_REJECTED",
    "TRANSFER_INITIATED",
    "TRANSFER_PROCESSING",
    "TRANSFER_CONFIRMED",
    "COMPLETE",
]


def get_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_tracking_record(
    transaction_id: str,
    initial_status: str,
    receiving_broker_id: str = None,
    delivering_broker_id: str = None,
    carrier_id: str = None,
    carrier_name: str = None,
    client_name: str = None,
    ssn_last4: str = None,
    policies_affected: list = None,
    notes: str = None,
) -> dict:
    """Create a new request tracking record."""
    timestamp = get_timestamp()
    sk = str(uuid.uuid4())

    record = {
        "pk": transaction_id,
        "sk": sk,
        "transactionId": transaction_id,
        "currentStatus": initial_status,
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "statusHistory": [{
            "status": initial_status,
            "timestamp": timestamp,
            "notes": notes or f"Transaction created with status {initial_status}"
        }],
        "receivingBrokerId": receiving_broker_id,
        "deliveringBrokerId": delivering_broker_id,
        "carrierId": carrier_id,
        "carrierName": carrier_name,
        "clientName": client_name,
        "ssnLast4": ssn_last4,
        "policiesAffected": policies_affected or [],
        "additionalData": {
            "requestType": "BD_CHANGE",
            "createdVia": "clearinghouse-api",
        },
    }

    return record


def get_tracking_record(transaction_id: str) -> dict:
    """Get a tracking record by transaction ID."""
    try:
        items = query_items(
            REQUEST_TRACKING_TABLE,
            transaction_id
        )
        return items[0] if items else None
    except Exception as e:
        logger.error(f"Error getting tracking record: {e}")
        return None


def update_tracking_status(
    transaction_id: str,
    sk: str,
    new_status: str,
    notes: str = None
) -> dict:
    """Update the status of a tracking record."""
    timestamp = get_timestamp()

    history_item = {"status": new_status, "timestamp": timestamp}
    if notes:
        history_item["notes"] = notes

    return update_item(
        REQUEST_TRACKING_TABLE,
        transaction_id,
        sk,
        update_expression="SET currentStatus = :status, updatedAt = :updated, statusHistory = list_append(statusHistory, :history_item)",
        expression_values={
            ":status": new_status,
            ":updated": timestamp,
            ":history_item": [history_item]
        }
    )


def get_carrier_info(policy_numbers: list) -> tuple:
    """Determine carrier ID and name from policy numbers."""
    if not policy_numbers:
        return None, None

    first_policy = policy_numbers[0]
    if first_policy.startswith("ATH"):
        return "athene", "Athene"
    elif first_policy.startswith("PAC"):
        return "pacific-life", "Pacific Life"
    elif first_policy.startswith("PRU"):
        return "prudential", "Prudential"
    return None, None


def create_capability_response(
    transaction_id: str,
    message: str,
    capability_status: str,
    capability_level: str = "none",
    supported_alternatives: list = None,
    retry_after: str = None
) -> tuple:
    """Create a CapabilityResponse for 422 NOT_CAPABLE responses."""
    response = {
        "code": "NOT_CAPABLE",
        "message": message,
        "transactionId": transaction_id,
        "capabilityStatus": capability_status,
        "capabilityLevel": capability_level,
    }
    if supported_alternatives:
        response["supportedAlternatives"] = supported_alternatives
    if retry_after:
        response["retryAfter"] = retry_after
    return jsonify(response), 422


def lookup_policy_from_iiex(policy_number: str) -> dict:
    """
    Look up a policy from the IIEX table.
    Returns the policy record or None if not found.
    """
    policy = get_item(
        IIEX_TABLE,
        f"POLICY#{policy_number}",
        f"POLICY#{policy_number}"
    )

    if policy:
        # Determine carrier name from prefix
        prefix = policy_number.split("-")[0] if "-" in policy_number else None
        policy["_carrierName"] = CARRIER_NAME_BY_PREFIX.get(prefix, "Unknown")
    return policy


def format_iiex_policy_for_response(policy: dict, client_ssn: str = None) -> dict:
    """
    Format an IIEX DB policy record to PolicyInquiryResponse DetailedPolicyInfo format.
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


@BP.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "clearinghouse-api",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


@BP.route('/dtcc/policy-inquiry', methods=['POST'])
def dtcc_policy_inquiry():
    """
    DTCC/IIEX policy inquiry endpoint.
    Looks up policies from the IIEX table which contains aggregated data
    from multiple carriers (Athene, Pacific Life).

    This is the clearinghouse's cached/aggregated view of policy data.
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

        if 'requestingFirm' not in data or 'client' not in data:
            return create_error_response(
                "VALIDATION_ERROR",
                "requestingFirm and client are required fields",
                400
            )

        requesting_firm = data.get('requestingFirm', {})
        client = data.get('client', {})
        servicing_agent = requesting_firm.get('servicingAgent', {})

        logger.info(f"[DTCC/IIEX] Policy inquiry - Transaction ID: {transaction_id}")
        logger.info(f"[DTCC/IIEX] Client: {client.get('clientName')}")
        logger.info(f"[DTCC/IIEX] Policy Numbers: {client.get('policyNumbers', [])}")

        client_ssn = client.get('ssn')
        policy_numbers = client.get('policyNumbers', [])

        policies = []
        client_name_from_db = None
        ssn_last4 = client_ssn[-4:] if client_ssn and len(client_ssn) >= 4 else None

        for policy_number in policy_numbers:
            policy = lookup_policy_from_iiex(policy_number)
            if policy:
                if not client_name_from_db:
                    client_name_from_db = policy.get('clientName')
                    if not ssn_last4 and policy.get('ownerSSN'):
                        ssn_last4 = policy.get('ownerSSN')[-4:]

                formatted_policy = format_iiex_policy_for_response(policy, client_ssn)
                policies.append(formatted_policy)
            else:
                # Policy not found in IIEX
                policies.append({
                    "policyNumber": policy_number,
                    "carrierName": None,
                    "errors": [{
                        "errorCode": "policyNotFound",
                        "message": f"Policy {policy_number} not found in IIEX records"
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
                "errors": []
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
            f"[DTCC/IIEX] Returning {len(policies)} policies for transaction {transaction_id}")

        return create_response(
            "IMMEDIATE",
            "Policy inquiry processed successfully from IIEX cache",
            transaction_id,
            response_payload,
            200,
            processing_mode="cached"
        )

    except Exception as e:
        logger.error(f"[DTCC/IIEX] Error processing policy inquiry: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/policy-inquiry', methods=['POST'])
def policy_inquiry():
    """
    Process policy inquiry request.
    Routes request to appropriate delivering broker or responds immediately if cached.
    Creates a new tracking record with MANIFEST_REQUESTED status.

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
        policy_numbers = client.get('policyNumbers', [])

        logger.info(f"Received policy inquiry request - Transaction ID: {transaction_id}")
        logger.info(f"Requesting Firm: {requesting_firm.get('firmName')}")
        logger.info(f"Client: {client.get('clientName')}")
        logger.info(f"Policy Numbers: {policy_numbers}")

        # Determine carrier from policy numbers
        carrier_id, carrier_name = get_carrier_info(policy_numbers)

        # Get SSN last 4 if full SSN provided
        ssn = client.get('ssn', '')
        ssn_last4 = ssn[-4:] if len(ssn) >= 4 else None

        # Create tracking record
        record = create_tracking_record(
            transaction_id=transaction_id,
            initial_status="MANIFEST_REQUESTED",
            receiving_broker_id=requesting_firm.get('firmId'),
            delivering_broker_id=None,  # To be determined
            carrier_id=carrier_id,
            carrier_name=carrier_name,
            client_name=client.get('clientName'),
            ssn_last4=ssn_last4,
            policies_affected=policy_numbers,
            notes="Policy inquiry request received from receiving broker"
        )

        # Store request details
        record["additionalData"]["requestingFirm"] = requesting_firm
        record["additionalData"]["clientRequest"] = client

        put_item(REQUEST_TRACKING_TABLE, record)
        logger.info(f"Created tracking record for transaction {transaction_id}")

        return create_response(
            "RECEIVED",
            "Policy inquiry request received and routed to delivering broker",
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
    Routes response to requesting broker.
    Updates tracking record to MANIFEST_RECEIVED status.

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

        # Validate required fields
        required_fields = ['requestingFirm', 'producerValidation', 'client', 'enums']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        client = data.get('client', {})
        policies = client.get('policies', [])

        logger.info(
            f"Received policy inquiry response - Transaction ID: {transaction_id}")
        logger.info(f"Client: {client.get('clientName')}")
        logger.info(f"Number of policies: {len(policies)}")

        # Get existing tracking record
        record = get_tracking_record(transaction_id)

        if record:
            # Update status to MANIFEST_RECEIVED
            update_tracking_status(
                transaction_id,
                record["sk"],
                "MANIFEST_RECEIVED",
                "Policy inquiry response received from delivering broker"
            )

            # Store response details
            update_item(
                REQUEST_TRACKING_TABLE,
                transaction_id,
                record["sk"],
                updates={
                    "policyInquiryResponse": data,
                    "ssnLast4": client.get("ssnLast4"),
                }
            )
            logger.info(f"Updated tracking record {transaction_id} to MANIFEST_RECEIVED")
        else:
            logger.warning(f"Tracking record {transaction_id} not found, creating new")
            # Create new record if not found
            new_record = create_tracking_record(
                transaction_id=transaction_id,
                initial_status="MANIFEST_RECEIVED",
                client_name=client.get('clientName'),
                ssn_last4=client.get('ssnLast4'),
                policies_affected=[p.get('policyNumber')
                                   for p in policies if p.get('policyNumber')],
                notes="Policy inquiry response received (new record)"
            )
            put_item(REQUEST_TRACKING_TABLE, new_record)

        return create_response(
            "RECEIVED",
            "Policy inquiry response received and forwarded to requesting broker",
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
    Routes to carrier for validation.
    Updates tracking record to CARRIER_VALIDATION_PENDING status.

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
        logger.info(f"Carrier: {data.get('carrier-id')}")

        # Get existing tracking record
        record = get_tracking_record(transaction_id)

        if record:
            # First update to DUE_DILIGENCE_COMPLETE
            update_tracking_status(
                transaction_id,
                record["sk"],
                "DUE_DILIGENCE_COMPLETE",
                "Due diligence checks completed"
            )

            # Then update to CARRIER_VALIDATION_PENDING
            update_tracking_status(
                transaction_id,
                record["sk"],
                "CARRIER_VALIDATION_PENDING",
                "BD change request sent to carrier for validation"
            )

            # Update broker and carrier info
            update_item(
                REQUEST_TRACKING_TABLE,
                transaction_id,
                record["sk"],
                updates={
                    "receivingBrokerId": data.get('receiving-broker-id'),
                    "deliveringBrokerId": data.get('delivering-broker-id'),
                    "carrierId": data.get('carrier-id'),
                }
            )
            logger.info(
                f"Updated tracking record {transaction_id} to CARRIER_VALIDATION_PENDING")
        else:
            logger.warning(f"Tracking record {transaction_id} not found")

        return create_response(
            "RECEIVED",
            "BD change request received and routed to carrier for validation",
            transaction_id
        )

    except Exception as e:
        logger.error(f"Error processing BD change request: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/bd-change-callback', methods=['POST'])
def bd_change_callback():
    """
    BD change callback - receive carrier validation response.
    Routes response to receiving broker.
    Updates tracking record to CARRIER_APPROVED or CARRIER_REJECTED.

    Unified API endpoint - replaces /receive-carrier-response
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
        required_fields = ['transaction-id', 'carrier-id',
                           'policy-id', 'validation-result']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        validation_result = data.get('validation-result')
        if validation_result not in ['approved', 'rejected']:
            return create_error_response(
                "VALIDATION_ERROR",
                "validation-result must be either 'approved' or 'rejected'",
                400
            )

        logger.info(f"Received carrier response - Transaction ID: {transaction_id}")
        logger.info(f"Carrier: {data.get('carrier-id')}")
        logger.info(f"Policy ID: {data.get('policy-id')}")
        logger.info(f"Validation Result: {validation_result}")

        rejection_reason = None
        if validation_result == 'rejected':
            rejection_reason = data.get('rejection-reason', 'Not provided')
            logger.info(f"Rejection Reason: {rejection_reason}")

        # Get existing tracking record
        record = get_tracking_record(transaction_id)

        if record:
            new_status = "CARRIER_APPROVED" if validation_result == "approved" else "CARRIER_REJECTED"
            notes = f"Carrier {validation_result} the BD change request"
            if rejection_reason:
                notes += f": {rejection_reason}"

            update_tracking_status(
                transaction_id,
                record["sk"],
                new_status,
                notes
            )

            # Store rejection reason if rejected
            if rejection_reason:
                update_item(
                    REQUEST_TRACKING_TABLE,
                    transaction_id,
                    record["sk"],
                    updates={"rejectionReason": rejection_reason}
                )

            logger.info(f"Updated tracking record {transaction_id} to {new_status}")

        status_message = "approved" if validation_result == "approved" else "rejected"
        return create_response(
            "RECEIVED",
            f"Carrier validation response received - {status_message}",
            transaction_id
        )

    except Exception as e:
        logger.error(f"Error processing carrier response: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@BP.route('/transfer-notification', methods=['POST'])
def transfer_notification():
    """
    Transfer notification - accept transfer-related notifications.
    Supports various notification types (approval, initiation, completion).
    Updates tracking record based on notification type.

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
            "service-agent-change-complete": "COMPLETE",
        }
        new_status = notification_to_status.get(notification_type, "TRANSFER_PROCESSING")

        # Get existing tracking record
        record = get_tracking_record(transaction_id)

        if record:
            update_tracking_status(
                transaction_id,
                record["sk"],
                new_status,
                f"Transfer notification received: {notification_type}"
            )
            logger.info(f"Updated tracking record {transaction_id} to {new_status}")

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


@BP.route('/transfer-confirmation', methods=['POST'])
def transfer_confirmation():
    """
    Transfer confirmation - accept transfer confirmation from delivering entity.
    Broadcasts to relevant parties.
    Updates tracking record to TRANSFER_CONFIRMED or COMPLETE.

    Unified API endpoint - replaces /receive-transfer-confirmation
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
        logger.info(f"Delivering Broker: {data.get('deliveringBrokerId')}")
        logger.info(f"Policy Number: {data.get('policyNumber')}")
        logger.info(f"Confirmation Status: {confirmation_status}")

        # Get existing tracking record
        record = get_tracking_record(transaction_id)

        if record:
            if confirmation_status == "confirmed":
                # Update to TRANSFER_CONFIRMED then COMPLETE
                update_tracking_status(
                    transaction_id,
                    record["sk"],
                    "TRANSFER_CONFIRMED",
                    "Transfer confirmed by delivering broker"
                )
                update_tracking_status(
                    transaction_id,
                    record["sk"],
                    "COMPLETE",
                    "BD change process completed successfully"
                )
                logger.info(f"Updated tracking record {transaction_id} to COMPLETE")
            else:
                update_tracking_status(
                    transaction_id,
                    record["sk"],
                    "TRANSFER_PROCESSING",
                    f"Transfer confirmation failed: {data.get('failure-reason', 'Unknown')}"
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
    Query transaction status
    Retrieve current status and history for a specific transaction from request-tracking table.
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

        # Get tracking record
        record = get_tracking_record(transaction_id)

        if not record:
            return create_error_response(
                "NOT_FOUND",
                f"Transaction {transaction_id} not found",
                404
            )

        # Format response
        status_data = {
            "transaction-id": record.get("transactionId"),
            "current-status": record.get("currentStatus"),
            "created-at": record.get("createdAt"),
            "updated-at": record.get("updatedAt"),
            "status-history": record.get("statusHistory", []),
            "policies-affected": record.get("policiesAffected", []),
            "additional-data": {
                "receiving-broker-id": record.get("receivingBrokerId"),
                "delivering-broker-id": record.get("deliveringBrokerId"),
                "carrier-id": record.get("carrierId"),
                "carrier-name": record.get("carrierName"),
                "client-name": record.get("clientName"),
                "ssn-last-4": record.get("ssnLast4"),
            }
        }

        # Include rejection reason if present
        if "rejectionReason" in record:
            status_data["rejection-reason"] = record["rejectionReason"]

        return jsonify(status_data), 200

    except Exception as e:
        logger.error(f"Error querying transaction status: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )
