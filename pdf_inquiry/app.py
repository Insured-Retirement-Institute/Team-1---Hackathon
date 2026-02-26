"""
PDF Policy Statement → PolicyInquiryResponse Extractor
Flask application + Lambda handler

Exposes a single endpoint:
  POST /extract   — accepts { requestId, pdfBase64 }, returns policyInquiryResponse

Local development:
  python app.py              # runs on http://localhost:5001

Lambda deployment:
  The lambda_handler function is the Lambda entry point.
  Package this directory + installed requirements and deploy with a Function URL.
"""

import json
import logging
import os

import serverless_wsgi
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

import extractor
from helpers import (
    create_error_response,
    create_response,
    normalize_lambda_event,
    validate_request_id,
)

load_dotenv(override=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


@app.route("/extract", methods=["POST"])
def extract_policy():
    """
    Extract structured policy data from a Base64-encoded PDF policy statement.

    Required header:
      requestId: <UUID>

    Required body (JSON):
      requestId   string   Caller-supplied request identifier
      pdfBase64   string   Base64-encoded bytes of the policy statement PDF

    Response:
      200  code=EXTRACTED  payload.policyInquiryResponse — structured policy data
      400  VALIDATION_ERROR / MISSING_HEADER / INVALID_PAYLOAD
      500  EXTRACTION_ERROR — Bedrock call or JSON parse failure
    """
    request_id, err = validate_request_id(request.headers)
    if err:
        return err

    data = request.get_json(silent=True)
    if not data:
        return create_error_response("INVALID_PAYLOAD", "JSON request body is required", 400)

    missing = [f for f in ("requestId", "pdfBase64") if not data.get(f)]
    if missing:
        return create_error_response(
            "VALIDATION_ERROR",
            f"Missing required fields: {', '.join(missing)}",
            400,
        )

    request_id = data["requestId"]
    logger.info("PDF extraction request — requestId=%s requestId=%s", request_id, request_id)

    try:
        result = extractor.extract_from_pdf(data["pdfBase64"], request_id)
    except ValueError as e:
        logger.error("PDF decode error — requestId=%s: %s", request_id, e)
        return create_error_response("INVALID_PDF", str(e), 400)
    except json.JSONDecodeError as e:
        logger.error("Model returned non-JSON — requestId=%s: %s", request_id, e)
        return create_error_response(
            "EXTRACTION_ERROR",
            "Model returned non-JSON output. Check the PDF is a readable policy statement.",
            500,
        )
    except Exception as e:
        logger.error("Extraction failed — requestId=%s: %s", request_id, e, exc_info=True)
        return create_error_response("EXTRACTION_ERROR", str(e), 500)

    logger.info("Extraction successful — requestId=%s policies=%d",
                request_id,
                len((result.get("policyInquiryResponse") or {}).get("client", {}).get("policies", [])))

    return create_response(
        "EXTRACTED",
        "Policy data extracted from document",
        request_id,
        result,
        200,
        processing_mode="immediate",
    )


@app.route("/health", methods=["GET"])
def health():
    """Health check — used by load balancers and monitoring."""
    return jsonify({"status": "healthy", "service": "pdf-inquiry-extractor"}), 200


@app.errorhandler(404)
def not_found(e):
    return create_error_response("NOT_FOUND", "The requested resource was not found", 404)


@app.errorhandler(405)
def method_not_allowed(e):
    return create_error_response("METHOD_NOT_ALLOWED", "HTTP method not allowed for this endpoint", 405)


def lambda_handler(event, context):
    """AWS Lambda entry point — bridges Lambda Function URL events to Flask."""
    event = normalize_lambda_event(event)
    return serverless_wsgi.handle_request(app, event, context)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, port=port)
