"""
Lambda handler for Carrier API operations.
Handles BD change validation requests and policy queries for insurance carriers.
"""

import json
import os
import sys

# Add utils to path for local imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.dynamodb_utils import (
    scan_all_policies,
    get_policy_by_number,
    get_policy_by_transaction,
    query_policies_by_client,
    query_policies_by_ssn_last4,
    query_policies_by_status,
    update_policy_status,
    format_policy_for_api,
    format_policy_detail_for_api,
    to_json,
    DecimalEncoder
)


# Table mapping based on carrier ID
CARRIER_TABLES = {
    "athene": "carrier",
    "carrier": "carrier",
    "pacific-life": "carrier-2",
    "carrier-2": "carrier-2"
}


def create_response(status_code: int, body: dict, headers: dict = None) -> dict:
    """Create a standardized API Gateway response."""
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS"
    }
    if headers:
        default_headers.update(headers)

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body, cls=DecimalEncoder)
    }


def handle_get_all_policies(event: dict) -> dict:
    """
    GET /policies
    Get all policies for a carrier.
    Query params: carrier (required)
    """
    params = event.get("queryStringParameters") or {}
    carrier = params.get("carrier", "carrier")

    table_name = CARRIER_TABLES.get(carrier.lower(), "carrier")

    try:
        policies = scan_all_policies(table_name)
        formatted = [format_policy_detail_for_api(p) for p in policies]

        return create_response(200, {
            "policies": formatted,
            "count": len(formatted)
        })
    except Exception as e:
        return create_response(500, {
            "code": "INTERNAL_ERROR",
            "message": str(e)
        })


def handle_get_policy(event: dict) -> dict:
    """
    GET /policies/{policyNumber}
    Get a specific policy by policy number.
    Query params: carrier (required)
    """
    path_params = event.get("pathParameters") or {}
    policy_number = path_params.get("policyNumber")

    params = event.get("queryStringParameters") or {}
    carrier = params.get("carrier", "carrier")

    if not policy_number:
        return create_response(400, {
            "code": "VALIDATION_ERROR",
            "message": "policyNumber is required"
        })

    table_name = CARRIER_TABLES.get(carrier.lower(), "carrier")

    try:
        policy = get_policy_by_number(table_name, policy_number)

        if not policy:
            return create_response(404, {
                "code": "NOT_FOUND",
                "message": f"Policy {policy_number} not found"
            })

        return create_response(200, format_policy_detail_for_api(policy))
    except Exception as e:
        return create_response(500, {
            "code": "INTERNAL_ERROR",
            "message": str(e)
        })


def handle_query_policies(event: dict) -> dict:
    """
    GET /policies/query
    Query policies by various criteria.
    Query params: carrier (required), clientName, ssnLast4, status
    """
    params = event.get("queryStringParameters") or {}
    carrier = params.get("carrier", "carrier")
    client_name = params.get("clientName")
    ssn_last4 = params.get("ssnLast4")
    status = params.get("status")

    table_name = CARRIER_TABLES.get(carrier.lower(), "carrier")

    try:
        if client_name:
            policies = query_policies_by_client(table_name, client_name)
        elif ssn_last4:
            policies = query_policies_by_ssn_last4(table_name, ssn_last4)
        elif status:
            policies = query_policies_by_status(table_name, status)
        else:
            return create_response(400, {
                "code": "VALIDATION_ERROR",
                "message": "At least one query parameter required: clientName, ssnLast4, or status"
            })

        formatted = [format_policy_detail_for_api(p) for p in policies]

        return create_response(200, {
            "policies": formatted,
            "count": len(formatted)
        })
    except Exception as e:
        return create_response(500, {
            "code": "INTERNAL_ERROR",
            "message": str(e)
        })


def handle_receive_bd_change_request(event: dict) -> dict:
    """
    POST /receive-bd-change-request
    Receive BD change validation request from clearinghouse.
    Per Insurance Carrier API spec.
    """
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return create_response(400, {
            "code": "VALIDATION_ERROR",
            "message": "Invalid JSON body"
        })

    # Get transaction ID from header
    headers = event.get("headers") or {}
    transaction_id = headers.get("transactionId") or headers.get("transactionid")

    if not transaction_id:
        return create_response(400, {
            "code": "VALIDATION_ERROR",
            "message": "transactionId header is required"
        })

    # Validate required fields per spec
    required_fields = ["receivingBrokerId", "deliveringBrokerId", "carrierId", "policyNumber"]
    missing = [f for f in required_fields if not body.get(f)]

    if missing:
        return create_response(400, {
            "code": "VALIDATION_ERROR",
            "message": f"Missing required fields: {', '.join(missing)}"
        })

    # Acknowledge receipt - actual validation would be async
    return create_response(200, {
        "code": "RECEIVED",
        "message": "BD change request received successfully",
        "processingStatus": "received",
        "transactionId": transaction_id
    })


def handle_receive_transfer_notification(event: dict) -> dict:
    """
    POST /receive-transfer-notification
    Receive transfer notification from clearinghouse.
    Per Insurance Carrier API spec.
    """
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return create_response(400, {
            "code": "VALIDATION_ERROR",
            "message": "Invalid JSON body"
        })

    # Get transaction ID from header
    headers = event.get("headers") or {}
    transaction_id = headers.get("transactionId") or headers.get("transactionid")

    if not transaction_id:
        return create_response(400, {
            "code": "VALIDATION_ERROR",
            "message": "transactionId header is required"
        })

    # Validate required fields per spec
    required_fields = ["notificationType", "policyNumber", "carrierId"]
    missing = [f for f in required_fields if not body.get(f)]

    if missing:
        return create_response(400, {
            "code": "VALIDATION_ERROR",
            "message": f"Missing required fields: {', '.join(missing)}"
        })

    # Acknowledge receipt
    return create_response(200, {
        "code": "RECEIVED",
        "message": "Transfer notification received successfully",
        "processingStatus": "received",
        "transactionId": transaction_id
    })


def handle_query_status(event: dict) -> dict:
    """
    GET /query-status/{transactionId}
    Query transaction status.
    Per Insurance Carrier API spec.
    """
    path_params = event.get("pathParameters") or {}
    transaction_id = path_params.get("transactionId")

    if not transaction_id:
        return create_response(400, {
            "code": "VALIDATION_ERROR",
            "message": "transactionId is required"
        })

    # For demo, scan both tables to find the transaction
    for table_name in ["carrier", "carrier-2"]:
        try:
            policies = scan_all_policies(table_name)
            for policy in policies:
                if policy.get("transactionId") == transaction_id:
                    return create_response(200, {
                        "transactionId": transaction_id,
                        "currentStatus": policy.get("currentStatus"),
                        "statusHistory": policy.get("statusHistory", []),
                        "createdAt": policy.get("createdAt"),
                        "updatedAt": policy.get("updatedAt"),
                        "policyNumber": policy.get("policyNumber"),
                        "carrierId": policy.get("carrierId")
                    })
        except Exception:
            continue

    return create_response(404, {
        "code": "NOT_FOUND",
        "message": f"Transaction {transaction_id} not found"
    })


def handle_update_status(event: dict) -> dict:
    """
    PUT /policies/{policyNumber}/status
    Update policy status (for demo/testing).
    """
    path_params = event.get("pathParameters") or {}
    policy_number = path_params.get("policyNumber")

    if not policy_number:
        return create_response(400, {
            "code": "VALIDATION_ERROR",
            "message": "policyNumber is required"
        })

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return create_response(400, {
            "code": "VALIDATION_ERROR",
            "message": "Invalid JSON body"
        })

    new_status = body.get("status")
    transaction_id = body.get("transactionId")
    notes = body.get("notes")
    carrier = body.get("carrier", "carrier")

    if not new_status or not transaction_id:
        return create_response(400, {
            "code": "VALIDATION_ERROR",
            "message": "status and transactionId are required"
        })

    table_name = CARRIER_TABLES.get(carrier.lower(), "carrier")

    try:
        result = update_policy_status(
            table_name,
            policy_number,
            transaction_id,
            new_status,
            notes
        )

        return create_response(200, {
            "code": "UPDATED",
            "message": f"Status updated to {new_status}",
            "policy": format_policy_detail_for_api(result.get("Attributes", {}))
        })
    except Exception as e:
        return create_response(500, {
            "code": "INTERNAL_ERROR",
            "message": str(e)
        })


def handler(event: dict, context) -> dict:
    """
    Main Lambda handler - routes requests to appropriate handlers.
    """
    http_method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    resource = event.get("resource", path)

    # Handle OPTIONS for CORS
    if http_method == "OPTIONS":
        return create_response(200, {})

    # Route based on path and method
    if http_method == "GET":
        if "/query-status/" in path:
            return handle_query_status(event)
        elif "/policies/query" in path:
            return handle_query_policies(event)
        elif "/policies/" in path and path != "/policies/":
            return handle_get_policy(event)
        elif "/policies" in path:
            return handle_get_all_policies(event)

    elif http_method == "POST":
        if "/receive-bd-change-request" in path:
            return handle_receive_bd_change_request(event)
        elif "/receive-transfer-notification" in path:
            return handle_receive_transfer_notification(event)

    elif http_method == "PUT":
        if "/status" in path:
            return handle_update_status(event)

    # Default 404
    return create_response(404, {
        "code": "NOT_FOUND",
        "message": f"Route {http_method} {path} not found"
    })


# For local testing
if __name__ == "__main__":
    # Test get all policies
    test_event = {
        "httpMethod": "GET",
        "path": "/policies",
        "queryStringParameters": {"carrier": "carrier"}
    }
    result = handler(test_event, None)
    print(json.dumps(json.loads(result["body"]), indent=2))
