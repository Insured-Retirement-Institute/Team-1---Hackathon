"""
Broker-Dealer API Flask Application
Implements the OpenAPI specification for broker-dealer endpoints
"""

from flask import Flask, jsonify
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


# ==== Dynamic Blueprint Registration ===============================
broker_dealer_prefix = "/api/broker-dealer"
clearinghouse_prefix = "/api/clearinghouse"
insurance_carriers_prefix = "/api/insurance-carriers"


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


def normalize_lambda_event(event):
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
