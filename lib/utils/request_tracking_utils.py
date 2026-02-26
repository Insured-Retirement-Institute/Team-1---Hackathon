"""
DynamoDB utility functions for request-tracking table.
Provides methods for querying and updating request status.
"""

import boto3
from boto3.dynamodb.conditions import Key
from typing import Dict, List, Optional
from datetime import datetime, timezone
import os

TABLE_NAME = os.environ.get("REQUEST_TRACKING_TABLE", "request-tracking")
REGION = os.environ.get("AWS_REGION", "us-east-1")


def get_table():
    """Get a DynamoDB table resource."""
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    return dynamodb.Table(TABLE_NAME)


def get_request_by_id(request_id: str) -> Optional[Dict]:
    """
    Get a request by its request ID.
    Since pk is the request ID, we can query directly.

    Args:
        request_id: The ULID request identifier

    Returns:
        Request record or None if not found
    """
    table = get_table()

    # Query by pk (request_id)
    response = table.query(
        KeyConditionExpression=Key("pk").eq(request_id)
    )

    items = response.get("Items", [])
    return items[0] if items else None


def scan_all_requests() -> List[Dict]:
    """
    Scan all requests from the request-tracking table.

    Returns:
        List of request records
    """
    table = get_table()
    items = []

    response = table.scan()
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    return items


def query_requests_by_status(status: str) -> List[Dict]:
    """
    Query requests by current status using scan with filter.

    Args:
        status: Status to filter by (e.g., 'CARRIER_VALIDATION_PENDING')

    Returns:
        List of matching request records
    """
    from boto3.dynamodb.conditions import Attr

    table = get_table()
    items = []

    response = table.scan(
        FilterExpression=Attr("currentStatus").eq(status)
    )
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression=Attr("currentStatus").eq(status),
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        items.extend(response.get("Items", []))

    return items


def query_requests_by_carrier(carrier_id: str) -> List[Dict]:
    """
    Query requests by carrier ID using scan with filter.

    Args:
        carrier_id: Carrier identifier (e.g., 'athene', 'pacific-life')

    Returns:
        List of matching request records
    """
    from boto3.dynamodb.conditions import Attr

    table = get_table()
    items = []

    response = table.scan(
        FilterExpression=Attr("carrierId").eq(carrier_id)
    )
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression=Attr("carrierId").eq(carrier_id),
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        items.extend(response.get("Items", []))

    return items


def put_request(request: Dict) -> Dict:
    """
    Put a request record into the table.

    Args:
        request: Request record to insert (must include pk and sk)

    Returns:
        DynamoDB response
    """
    table = get_table()
    return table.put_item(Item=request)


def update_request_status(
    request_id: str,
    sk: str,
    new_status: str,
    notes: Optional[str] = None
) -> Dict:
    """
    Update the status of a request and append to status history.

    Args:
        request_id: The request ID (pk)
        sk: The sort key
        new_status: New status value
        notes: Optional notes for the status change

    Returns:
        DynamoDB response
    """
    table = get_table()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    history_item = {
        "status": new_status,
        "timestamp": timestamp
    }
    if notes:
        history_item["notes"] = notes

    response = table.update_item(
        Key={
            "pk": request_id,
            "sk": sk
        },
        UpdateExpression="SET currentStatus = :status, updatedAt = :updated, statusHistory = list_append(statusHistory, :history)",
        ExpressionAttributeValues={
            ":status": new_status,
            ":updated": timestamp,
            ":history": [history_item]
        },
        ReturnValues="ALL_NEW"
    )

    return response


def format_request_for_api(request: Dict) -> Dict:
    """
    Format a DynamoDB request record for API response.
    Matches the RequestStatus schema from the API spec.

    Args:
        request: Raw DynamoDB request record

    Returns:
        Formatted request for API response
    """
    return {
        "request-id": request.get("requestId"),
        "current-status": request.get("currentStatus"),
        "created-at": request.get("createdAt"),
        "updated-at": request.get("updatedAt"),
        "status-history": request.get("statusHistory", []),
        "policies-affected": request.get("policiesAffected", []),
        "additional-data": {
            "receiving-broker-id": request.get("receivingBrokerId"),
            "delivering-broker-id": request.get("deliveringBrokerId"),
            "carrier-id": request.get("carrierId"),
            "carrier-name": request.get("carrierName"),
            "client-name": request.get("clientName"),
            "ssn-last-4": request.get("ssnLast4"),
        }
    }
