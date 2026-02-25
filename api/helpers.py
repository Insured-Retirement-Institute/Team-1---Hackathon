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
def create_response(
    code,
    message,
    transaction_id,
    payload=None,
    status_code=200,
    processing_mode=None,
    estimated_response_time=None
):
    """
    Create standardized response per StandardResponse schema.

    Args:
        code: Response code (e.g., "IMMEDIATE", "DEFERRED", "RECEIVED")
        message: Human-readable response message
        transaction_id: Unique transaction identifier (required)
        payload: Optional response payload (e.g., PolicyInquiryResponse)
        status_code: HTTP status code (default 200)
        processing_mode: Optional - "immediate", "deferred", or "queued"
        estimated_response_time: Optional - ISO 8601 duration (e.g., "PT5M")
    """
    response = {
        "code": code,
        "message": message,
        "transactionId": transaction_id
    }
    if payload is not None:
        response["payload"] = payload
    if processing_mode is not None:
        response["processingMode"] = processing_mode
    if estimated_response_time is not None:
        response["estimatedResponseTime"] = estimated_response_time
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
