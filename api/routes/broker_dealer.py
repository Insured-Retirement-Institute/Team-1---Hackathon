"""
Broker-Dealer API Flask Application
Implements the OpenAPI specification for broker-dealer endpoints
Integrated with DynamoDB distributor tables.
"""

from flask import request, jsonify, Blueprint
from datetime import datetime, timezone
import sys
import uuid
import logging
from dotenv import load_dotenv
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
