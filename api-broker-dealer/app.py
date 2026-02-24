"""
Broker-Dealer API Flask Application
Implements the OpenAPI specification for broker-dealer endpoints
"""

from flask import Flask, request, jsonify
from datetime import datetime
import serverless_wsgi
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


# Response helpers
def create_response(code, message, payload=None, status_code=200):
    """Create standardized response"""
    response = {
        "code": code,
        "message": message
    }
    if payload is not None:
        response["payload"] = payload
    return jsonify(response), status_code


def create_error_response(code, message, status_code=400):
    """Create standardized error response"""
    return jsonify({
        "code": code,
        "message": message
    }), status_code


def validate_transaction_id(headers):
    """Validate transaction ID in headers"""
    transaction_id = headers.get('transactionId')
    if not transaction_id:
        return None, create_error_response(
            "MISSING_HEADER",
            "transactionId header is required",
            400
        )
    try:
        uuid.UUID(transaction_id)
        return transaction_id, None
    except ValueError:
        return None, create_error_response(
            "INVALID_HEADER",
            "transactionId must be a valid UUID",
            400
        )


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


@app.route('/submit-policy-inquiry-request', methods=['POST'])
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
            None,
            200
        )

    except Exception as e:
        logger.error(f"Error processing policy inquiry request: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@app.route('/receive-policy-inquiry-response', methods=['POST'])
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
            None,
            200
        )

    except Exception as e:
        logger.error(f"Error processing policy inquiry response: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@app.route('/receive-bd-change-request', methods=['POST'])
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
            None,
            200
        )

    except Exception as e:
        logger.error(f"Error processing BD change request: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@app.route('/receive-transfer-notification', methods=['POST'])
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
            None,
            200
        )

    except Exception as e:
        logger.error(f"Error processing transfer notification: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@app.route('/query-status/<transaction_id>', methods=['GET'])
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

        return jsonify(status_data), 200

    except Exception as e:
        logger.error(f"Error querying transaction status: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return create_error_response(
        "NOT_FOUND",
        "The requested resource was not found",
        404
    )


@app.errorhandler(405)
def method_not_allowed(e):
    """Handle 405 errors"""
    return create_error_response(
        "METHOD_NOT_ALLOWED",
        "The HTTP method is not allowed for this endpoint",
        405
    )


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {str(e)}")
    return create_error_response(
        "INTERNAL_ERROR",
        "An internal server error occurred",
        500
    )


def handler(event, context):
    """
    AWS Lambda handler function

    Args:
        event: AWS Lambda event object (API Gateway request)
        context: AWS Lambda context object

    Returns:
        Response formatted for API Gateway
    """
    return serverless_wsgi.handle_request(app, event, context)


if __name__ == '__main__':
    # For local development only
    app.run(debug=True, host='0.0.0.0', port=5000)
