"""
Response helpers for the PDF Inquiry Extractor service.
Standalone copy — no Flask blueprint or route imports.
"""

from flask import jsonify
import re
import logging

# ULID validation: 26 chars using Crockford's Base32 (excludes I, L, O, U)
_ULID_PATTERN = re.compile(r'^[0-9A-HJKMNP-TV-Z]{26}$', re.IGNORECASE)

logger = logging.getLogger(__name__)


def create_response(
    code,
    message,
    request_id,
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
        request_id: UUID from the requestId header
        payload: Optional response payload dict
        status_code: HTTP status code (default 200)
        processing_mode: Optional — "immediate", "deferred", or "queued"
        estimated_response_time: Optional — ISO 8601 duration (e.g., "PT5M")
    """
    response = {
        "code": code,
        "message": message,
        "requestId": request_id,
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


def validate_request_id(headers):
    """
    Validate the requestId header.
    Returns (request_id, None) on success or (None, error_response) on failure.
    """
    request_id = headers.get("requestId")
    if not request_id:
        return None, create_error_response(
            "MISSING_HEADER", "requestId header is required", 400
        )
    if not _ULID_PATTERN.match(request_id):
        return None, create_error_response(
            "INVALID_HEADER", "requestId must be a valid ULID (26 characters, Crockford Base32)", 400
        )
    return request_id, None


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
