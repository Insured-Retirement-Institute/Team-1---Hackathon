"""
Response helpers for the PDF Inquiry Extractor service.
Standalone copy — no Flask blueprint or route imports.
"""

from flask import jsonify
import uuid
import logging

logger = logging.getLogger(__name__)


def create_response(
    code,
    message,
    transaction_id,
    payload=None,
    status_code=200,
    processing_mode=None,
    estimated_response_time=None,
):
    """
    Create a standardized response per the StandardResponse schema.

    Args:
        code: Response code (e.g., "EXTRACTED", "IMMEDIATE", "ERROR")
        message: Human-readable message
        transaction_id: UUID from the transactionId header
        payload: Optional response payload dict
        status_code: HTTP status code (default 200)
        processing_mode: Optional — "immediate", "deferred", or "queued"
        estimated_response_time: Optional — ISO 8601 duration (e.g., "PT5M")
    """
    response = {
        "code": code,
        "message": message,
        "transactionId": transaction_id,
    }
    if payload is not None:
        response["payload"] = payload
    if processing_mode is not None:
        response["processingMode"] = processing_mode
    if estimated_response_time is not None:
        response["estimatedResponseTime"] = estimated_response_time
    return jsonify(response), status_code


def create_error_response(code, message, status_code=400):
    """Create a standardized error response."""
    return jsonify({"code": code, "message": message}), status_code


def validate_transaction_id(headers):
    """
    Validate the transactionId header.
    Returns (transaction_id, None) on success or (None, error_response) on failure.
    """
    transaction_id = headers.get("transactionId")
    if not transaction_id:
        return None, create_error_response(
            "MISSING_HEADER", "transactionId header is required", 400
        )
    try:
        uuid.UUID(transaction_id)
        return transaction_id, None
    except ValueError:
        return None, create_error_response(
            "INVALID_HEADER", "transactionId must be a valid UUID", 400
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
