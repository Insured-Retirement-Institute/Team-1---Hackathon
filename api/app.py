"""
Broker-Dealer API Flask Application
Implements the OpenAPI specification for broker-dealer endpoints
"""

from flask import Flask, jsonify
from datetime import datetime
from flask_cors import CORS
import os
import sys
import logging
import importlib
import serverless_wsgi
from dotenv import load_dotenv

# Add api folder to path for dynamodb_utils and helpers imports
sys.path.insert(0, os.path.dirname(__file__))

load_dotenv(override=False)
from helpers import create_error_response, normalize_lambda_event

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ==== Dynamic Blueprint Registration ====================================================
routes_dir = os.path.join(os.path.dirname(__file__), 'routes')
for filename in os.listdir(routes_dir):
    if filename.endswith('.py') and filename != '__init__.py':
        module_name = f"routes.{filename[:-3]}"
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, 'BP'):
                # URL prefix with /v1/ base (e.g., insurance_carrier.py -> /v1/insurance-carrier)
                url_prefix = f"/v1/{filename[:-3].replace('_', '-')}"
                app.register_blueprint(module.BP, url_prefix=url_prefix)
        except Exception as e:
            print(f"Failed to import {module_name}: {e}")


@app.route('/v1/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200


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


def lambda_handler(event, context):
    event = normalize_lambda_event(event)
    return serverless_wsgi.handle_request(app, event, context)


if __name__ == '__main__':
    # For local development only
    app.run(debug=True, port=5000)
