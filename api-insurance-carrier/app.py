"""
Insurance Carrier API Flask Application
Implements the OpenAPI specification for insurance carrier endpoints
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import serverless_wsgi
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


# Response helpers
def create_response(code, message, processing_status="received", estimated_time=None, status_code=200):
    """Create standardized response"""
    response = {
        "code": code,
        "message": message,
        "processingStatus": processing_status
    }
    if estimated_time:
        response["estimatedResponseTime"] = estimated_time
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
        "service": "insurance-carrier-api",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


@app.route('/receive-bd-change-request', methods=['POST'])
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
            "deferred",
            "Within 24 hours",
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
            "processing",
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


def _normalize_lambda_event(event):
    """Ensure required WSGI fields are present for serverless_wsgi."""
    if not event:
        return event

    headers = event.get("headers")
    if not isinstance(headers, dict):
        headers = {}

    if "X-Forwarded-Proto" not in headers and "x-forwarded-proto" not in headers:
        protocol = (event.get("requestContext") or {}).get("http", {}).get("protocol")
        scheme = None
        if isinstance(protocol, str) and protocol:
            scheme = protocol.split("/")[0].lower()
        if not scheme:
            scheme = "https"
        headers["X-Forwarded-Proto"] = scheme

    event["headers"] = headers
    return event


def lambda_handler(event, context):
    event = _normalize_lambda_event(event)
    return serverless_wsgi.handle_request(app, event, context)


if __name__ == '__main__':
    # For local development only
    app.run(debug=True, host='0.0.0.0', port=5002)
