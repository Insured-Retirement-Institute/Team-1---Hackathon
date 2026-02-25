"""
DynamoDB utility functions for request-tracking table.
Provides methods for querying and updating transaction status.
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


def get_transaction_by_id(transaction_id: str) -> Optional[Dict]:
    """
    Get a transaction by its transaction ID.
    Since pk is the transaction ID, we can query directly.

    Args:
        transaction_id: The UUID transaction identifier

    Returns:
        Transaction record or None if not found
    """
    table = get_table()

    # Query by pk (transaction_id)
    response = table.query(
        KeyConditionExpression=Key("pk").eq(transaction_id)
    )

    items = response.get("Items", [])
    return items[0] if items else None


def scan_all_transactions() -> List[Dict]:
    """
    Scan all transactions from the request-tracking table.

    Returns:
        List of transaction records
    """
    table = get_table()
    items = []

    response = table.scan()
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    return items


def query_transactions_by_status(status: str) -> List[Dict]:
    """
    Query transactions by current status using scan with filter.

    Args:
        status: Status to filter by (e.g., 'CARRIER_VALIDATION_PENDING')

    Returns:
        List of matching transaction records
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


def query_transactions_by_carrier(carrier_id: str) -> List[Dict]:
    """
    Query transactions by carrier ID using scan with filter.

    Args:
        carrier_id: Carrier identifier (e.g., 'athene', 'pacific-life')

    Returns:
        List of matching transaction records
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


def put_transaction(transaction: Dict) -> Dict:
    """
    Put a transaction record into the table.

    Args:
        transaction: Transaction record to insert (must include pk and sk)

    Returns:
        DynamoDB response
    """
    table = get_table()
    return table.put_item(Item=transaction)


def update_transaction_status(
    transaction_id: str,
    sk: str,
    new_status: str,
    notes: Optional[str] = None
) -> Dict:
    """
    Update the status of a transaction and append to status history.

    Args:
        transaction_id: The transaction ID (pk)
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
            "pk": transaction_id,
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


def format_transaction_for_api(transaction: Dict) -> Dict:
    """
    Format a DynamoDB transaction record for API response.
    Matches the TransactionStatus schema from the API spec.

    Args:
        transaction: Raw DynamoDB transaction record

    Returns:
        Formatted transaction for API response
    """
    return {
        "transaction-id": transaction.get("transactionId"),
        "current-status": transaction.get("currentStatus"),
        "created-at": transaction.get("createdAt"),
        "updated-at": transaction.get("updatedAt"),
        "status-history": transaction.get("statusHistory", []),
        "policies-affected": transaction.get("policiesAffected", []),
        "additional-data": {
            "receiving-broker-id": transaction.get("receivingBrokerId"),
            "delivering-broker-id": transaction.get("deliveringBrokerId"),
            "carrier-id": transaction.get("carrierId"),
            "carrier-name": transaction.get("carrierName"),
            "client-name": transaction.get("clientName"),
            "ssn-last-4": transaction.get("ssnLast4"),
        }
    }
