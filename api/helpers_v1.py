"""
v0 Unified Brokerage Transfer API — Response helpers.

These return data directly (no StandardResponse wrapper) per the v0.1.1 spec.
"""

from flask import jsonify
import logging

logger = logging.getLogger(__name__)


def validate_request_id(headers):
    """
    Validate requestId header (required, any non-empty string).
    Returns (request_id, error_response) tuple.
    """
    request_id = headers.get("requestId")
    if not request_id:
        return None, error_response("MISSING_HEADER", "requestId header is required", status=400)
    return request_id, None


def ok_response(data, status=200, correlation_id=None):
    """Return JSON data directly for 200 responses."""
    resp = jsonify(data)
    if correlation_id:
        resp.headers["correlationId"] = correlation_id
    return resp, status


def deferred_response(request_id, message, estimated_time=None, correlation_id=None):
    """Return DeferredResponse for 202 Accepted."""
    body = {
        "code": "DEFERRED",
        "message": message,
        "requestId": request_id,
    }
    if estimated_time:
        body["estimatedResponseTime"] = estimated_time
    resp = jsonify(body)
    if correlation_id:
        resp.headers["correlationId"] = correlation_id
    return resp, 202


def acknowledgment_response(request_id, message, correlation_id=None):
    """Return AcknowledgmentResponse for callback/reply endpoints."""
    body = {
        "code": "RECEIVED",
        "message": message,
        "requestId": request_id,
    }
    resp = jsonify(body)
    if correlation_id:
        resp.headers["correlationId"] = correlation_id
    return resp, 200


def capability_response(request_id, message, level="none", alternatives=None):
    """Return CapabilityResponse for 422 Not Capable."""
    body = {
        "code": "NOT_CAPABLE",
        "message": message,
        "requestId": request_id,
        "capabilityLevel": level,
    }
    if alternatives:
        body["supportedAlternatives"] = alternatives
    return jsonify(body), 422


def error_response(code, message, request_id=None, status=400):
    """Return ErrorResponse."""
    from datetime import datetime
    body = {
        "code": code,
        "message": message,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if request_id:
        body["requestId"] = request_id
    return jsonify(body), status
