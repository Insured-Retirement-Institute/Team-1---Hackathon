"""
Broker-Dealer API Flask Application
Implements the OpenAPI specification for broker-dealer endpoints
"""

from flask import request, jsonify, Blueprint
from datetime import datetime
import sys
import uuid
import logging
from dotenv import load_dotenv
sys.path.insert(0, "../")
load_dotenv(override=False)
from helpers import (create_response,
                     create_error_response,
                     validate_transaction_id)

BP = Blueprint('broker-dealer', __name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@BP.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


@BP.route('/submit-policy-inquiry-request', methods=['POST'])
def submit_policy_inquiry_request():
    """
    Receive policy inquiry request from clearinghouse
    Endpoint for delivering broker-dealer only
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

        logger.info(f"Received policy inquiry request - Transaction ID: {transaction_id}")
        logger.info(f"Requesting Firm: {data.get('requestingFirm', {}).get('firmName')}")
        logger.info(f"Client: {data.get('client', {}).get('clientName')}")

        # Option 1: Return immediate response (for demo purposes)
        # In production, this could be deferred processing

        # For immediate response with policy data:
        # response_payload = {
        #     "requestingFirm": data.get('requestingFirm'),
        #     "producerValidation": {...},
        #     "client": {...},
        #     "enums": {...}
        # }
        # return create_response("SUCCESS", "Policy inquiry processed", response_payload, 200)

        # For deferred processing:
        return create_response(
            "DEFERRED",
            "Policy inquiry request received and queued for processing",
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


@BP.route('/receive-policy-inquiry-response', methods=['POST'])
def receive_policy_inquiry_response():
    """
    Receive policy inquiry response from clearinghouse
    Endpoint for receiving broker-dealer only
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

        # Process the policy inquiry response
        # Store in database, trigger workflows, etc.

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


@BP.route('/receive-bd-change-request', methods=['POST'])
def receive_bd_change_request():
    """
    Receive BD change request from clearinghouse
    Endpoint for receiving broker-dealer only
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

        # Process the BD change request
        # Perform validation, store in database, etc.

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


@BP.route('/receive-transfer-notification', methods=['POST'])
def receive_transfer_notification():
    """
    Receive transfer notification from clearinghouse
    Accepts transfer-related notifications
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
        required_fields = ['transaction-id', 'notification-type', 'policy-id']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        notification_type = data.get('notification-type')
        valid_types = ['transfer-approved', 'transfer-initiated',
                       'transfer-confirmed', 'transfer-complete']
        if notification_type not in valid_types:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Invalid notification-type. Must be one of: {', '.join(valid_types)}",
                400
            )

        logger.info(f"Received transfer notification - Transaction ID: {transaction_id}")
        logger.info(f"Notification Type: {notification_type}")
        logger.info(f"Policy ID: {data.get('policy-id')}")

        # Process the transfer notification
        # Update status, trigger workflows, notify stakeholders, etc.

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

        # In production, retrieve from database
        # For demo purposes, return mock data

        # Simulate not found scenario (can be removed)
        # return create_error_response(
        #     "NOT_FOUND",
        #     f"Transaction {transaction_id} not found",
        #     404
        # )

        # Mock response
        status_data = {
            "transaction-id": transaction_id,
            "current-status": "MANIFEST_RECEIVED",
            "created-at": "2026-02-24T10:00:00Z",
            "updated-at": "2026-02-24T10:15:00Z",
            "broker-role": "receiving",
            "status-history": [
                {
                    "status": "MANIFEST_REQUESTED",
                    "timestamp": "2026-02-24T10:00:00Z",
                    "notes": "Initial request received from clearinghouse"
                },
                {
                    "status": "MANIFEST_RECEIVED",
                    "timestamp": "2026-02-24T10:15:00Z",
                    "notes": "Policy inquiry response processed"
                }
            ]
        }

        # dynamo.get_item(TABLE_DISTRIBUTOR, {'pk': {'S': transaction_id}})

        return jsonify(status_data), 200

    except Exception as e:
        logger.error(f"Error querying transaction status: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )
