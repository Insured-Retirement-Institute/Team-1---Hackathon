"""
Event Listener Lambda
Triggered by EventBridge events and forwards the payload to the /events endpoint.
"""

import json
import logging
import os
import urllib.request
import urllib.error

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configure via environment variables
EVENTS_ENDPOINT_URL = os.environ.get(
    "EVENTS_ENDPOINT_URL", "https://qsrsziidaou4kd6zh6qhtlo5ki0fvsqi.lambda-url.us-east-1.on.aws/v1/events")
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "10"))


def handler(event: dict, context) -> dict:
    """
    Lambda handler triggered by an EventBridge rule.

    Forwards the full EventBridge event payload to the configured /events endpoint
    via an HTTP POST request.

    Environment variables:
        EVENTS_ENDPOINT_URL       - Full URL of the /events endpoint to POST to.
        REQUEST_TIMEOUT_SECONDS   - HTTP request timeout in seconds (default: 10).

    Args:
        event:   The EventBridge event payload delivered by Lambda.
        context: The Lambda runtime context object.

    Returns:
        A dict with statusCode and body reflecting the downstream response.
    """
    logger.info("Received EventBridge event: source=%s, detail-type=%s",
                event.get("source"), event.get("detail-type"))
    logger.debug("Full event payload: %s", json.dumps(event))

    payload_bytes = json.dumps(event).encode("utf-8")

    req = urllib.request.Request(
        url=EVENTS_ENDPOINT_URL,
        data=payload_bytes,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(payload_bytes)),
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status_code = response.status
            response_body = response.read().decode("utf-8")

        logger.info("Successfully forwarded event. Downstream status: %s", status_code)

        return {
            "statusCode": status_code,
            "body": response_body,
        }

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8") if exc.fp else ""
        logger.error("Downstream HTTP error %s: %s", exc.code, error_body)
        return {
            "statusCode": exc.code,
            "body": error_body,
        }

    except urllib.error.URLError as exc:
        logger.error("Failed to reach events endpoint '%s': %s",
                     EVENTS_ENDPOINT_URL, exc.reason)
        raise RuntimeError(f"Could not reach events endpoint: {exc.reason}") from exc
