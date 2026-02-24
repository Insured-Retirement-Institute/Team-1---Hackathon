"""
Clearinghouse API Flask Application
Implements the OpenAPI specification for clearinghouse endpoints
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
def create_response(code, message, transaction_id, status_code=200):
    """
    Create standardized clearinghouse response
    Note: Clearinghouse ALWAYS returns deferred responses (no payload)
    """
    response = {
        "code": code,
        "message": message,
        "transactionId": transaction_id,
        "payload": None
    }
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
        "service": "clearinghouse-api",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


@app.route('/submit-policy-inquiry-request', methods=['POST'])
def submit_policy_inquiry_request():
    """
    Receive policy inquiry request from receiving broker
    Routes request to appropriate delivering broker

    Clearinghouse Response Behavior:
    - Always returns deferred response (no payload)
    - Provides transactionId for tracking
    - Status updated to MANIFEST_REQUESTED
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
        logger.info(f"Policy Numbers: {data.get('client', {}).get('policyNumbers')}")

        # TODO: Route request to delivering broker
        # TODO: Update transaction status to MANIFEST_REQUESTED
        # TODO: Store transaction in database

        return create_response(
            "RECEIVED",
            "Policy inquiry request received and routed to delivering broker",
            transaction_id,
            200
        )

    except Exception as e:
        logger.error(f"Error processing policy inquiry request: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@app.route('/submit-policy-inquiry-response', methods=['POST'])
def submit_policy_inquiry_response():
    """
    Receive policy inquiry response from delivering broker
    Routes response to requesting broker

    Clearinghouse Response Behavior:
    - Always returns deferred response (no payload)
    - Reflects transactionId from original request
    - Status updated to MANIFEST_RECEIVED
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
        logger.info(
            f"Number of policies: {len(data.get('client', {}).get('policies', []))}")

        # TODO: Route response to requesting broker
        # TODO: Update transaction status to MANIFEST_RECEIVED
        # TODO: Store response in database

        return create_response(
            "RECEIVED",
            "Policy inquiry response received and forwarded to requesting broker",
            transaction_id,
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
    Receive BD change request from receiving broker
    Routes to carrier for validation
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

        # TODO: Route request to insurance carrier for validation
        # TODO: Update transaction status to CARRIER_VALIDATION_PENDING
        # TODO: Store request in database

        return create_response(
            "RECEIVED",
            "BD change request received and routed to carrier for validation",
            transaction_id,
            200
        )

    except Exception as e:
        logger.error(f"Error processing BD change request: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@app.route('/receive-carrier-response', methods=['POST'])
def receive_carrier_response():
    """
    Receive carrier validation response
    Routes response to receiving broker
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

        if validation_result == 'rejected':
            logger.info(
                f"Rejection Reason: {data.get('rejection-reason', 'Not provided')}")

        # TODO: Route response to receiving broker
        # TODO: Update transaction status to CARRIER_APPROVED or CARRIER_REJECTED
        # TODO: Store response in database

        status_message = "approved" if validation_result == "approved" else "rejected"
        return create_response(
            "RECEIVED",
            f"Carrier validation response received - {status_message}",
            transaction_id,
            200
        )

    except Exception as e:
        logger.error(f"Error processing carrier response: {str(e)}")
        return create_error_response(
            "INTERNAL_ERROR",
            "Internal server error occurred",
            500
        )


@app.route('/receive-transfer-confirmation', methods=['POST'])
def receive_transfer_confirmation():
    """
    Receive transfer confirmation from delivering broker
    Broadcasts to relevant parties
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
        required_fields = ['transaction-id', 'delivering-broker-id',
                           'policy-id', 'confirmation-status']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return create_error_response(
                "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing_fields)}",
                400
            )

        confirmation_status = data.get('confirmation-status')
        if confirmation_status not in ['confirmed', 'failed']:
            return create_error_response(
                "VALIDATION_ERROR",
                "confirmation-status must be either 'confirmed' or 'failed'",
                400
            )

        logger.info(f"Received transfer confirmation - Transaction ID: {transaction_id}")
        logger.info(f"Delivering Broker: {data.get('delivering-broker-id')}")
        logger.info(f"Policy ID: {data.get('policy-id')}")
        logger.info(f"Confirmation Status: {confirmation_status}")

        # TODO: Broadcast notification to receiving broker and carrier
        # TODO: Update transaction status to TRANSFER_CONFIRMED or appropriate status
        # TODO: Store confirmation in database

        return create_response(
            "RECEIVED",
            f"Transfer confirmation received - {confirmation_status}",
            transaction_id,
            200
        )

    except Exception as e:
        logger.error(f"Error processing transfer confirmation: {str(e)}")
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
            "transaction-id": transaction_id,
            "current-status": "CARRIER_VALIDATION_PENDING",
            "created-at": "2026-02-24T10:00:00Z",
            "updated-at": "2026-02-24T10:30:00Z",
            "status-history": [
                {
                    "status": "MANIFEST_REQUESTED",
                    "timestamp": "2026-02-24T10:00:00Z",
                    "notes": "Policy inquiry request received from receiving broker"
                },
                {
                    "status": "MANIFEST_RECEIVED",
                    "timestamp": "2026-02-24T10:15:00Z",
                    "notes": "Policy inquiry response received from delivering broker"
                },
                {
                    "status": "DUE_DILIGENCE_COMPLETE",
                    "timestamp": "2026-02-24T10:20:00Z",
                    "notes": "Due diligence checks completed"
                },
                {
                    "status": "CARRIER_VALIDATION_PENDING",
                    "timestamp": "2026-02-24T10:30:00Z",
                    "notes": "BD change request sent to carrier for validation"
                }
            ],
            "policies-affected": ["POL-001", "POL-002"],
            "additional-data": {
                "receiving-broker-id": "BROKER-001",
                "delivering-broker-id": "BROKER-002",
                "carrier-id": "CARRIER-PL"
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
    app.run(debug=True, host='0.0.0.0', port=5001)
