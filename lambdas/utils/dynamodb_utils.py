"""
DynamoDB utility functions for carrier Lambda functions.
Provides reusable methods for interacting with carrier DynamoDB tables.
"""

import boto3
from boto3.dynamodb.conditions import Key, Attr
from typing import Dict, List, Optional, Any
from decimal import Decimal
import json


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)


def get_dynamodb_resource(region: str = "us-east-1"):
    """Get a DynamoDB resource."""
    return boto3.resource("dynamodb", region_name=region)


def get_dynamodb_client(region: str = "us-east-1"):
    """Get a DynamoDB client."""
    return boto3.client("dynamodb", region_name=region)


def get_table(table_name: str, region: str = "us-east-1"):
    """Get a DynamoDB table resource."""
    dynamodb = get_dynamodb_resource(region)
    return dynamodb.Table(table_name)


def scan_all_policies(table_name: str, region: str = "us-east-1") -> List[Dict]:
    """
    Scan all policies from a carrier table.

    Args:
        table_name: Name of the DynamoDB table ('carrier' or 'carrier-2')
        region: AWS region

    Returns:
        List of policy records
    """
    table = get_table(table_name, region)
    items = []

    response = table.scan()
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    return items


def get_policy_by_number(
    table_name: str,
    policy_number: str,
    region: str = "us-east-1"
) -> Optional[Dict]:
    """
    Get a policy by its policy number.

    Args:
        table_name: Name of the DynamoDB table
        policy_number: The policy number (e.g., 'ATH-100001')
        region: AWS region

    Returns:
        Policy record or None if not found
    """
    table = get_table(table_name, region)

    response = table.query(
        KeyConditionExpression=Key("pk").eq(f"POLICY#{policy_number}")
    )

    items = response.get("Items", [])
    return items[0] if items else None


def get_policy_by_transaction(
    table_name: str,
    policy_number: str,
    transaction_id: str,
    region: str = "us-east-1"
) -> Optional[Dict]:
    """
    Get a specific policy transaction.

    Args:
        table_name: Name of the DynamoDB table
        policy_number: The policy number
        transaction_id: The transaction ID
        region: AWS region

    Returns:
        Policy record or None if not found
    """
    table = get_table(table_name, region)

    response = table.get_item(
        Key={
            "pk": f"POLICY#{policy_number}",
            "sk": f"TRANSACTION#{transaction_id}"
        }
    )

    return response.get("Item")


def query_policies_by_client(
    table_name: str,
    client_name: str,
    region: str = "us-east-1"
) -> List[Dict]:
    """
    Query policies by client name using a scan with filter.

    Args:
        table_name: Name of the DynamoDB table
        client_name: Client name to search for
        region: AWS region

    Returns:
        List of matching policy records
    """
    table = get_table(table_name, region)
    items = []

    response = table.scan(
        FilterExpression=Attr("clientName").eq(client_name)
    )
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression=Attr("clientName").eq(client_name),
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        items.extend(response.get("Items", []))

    return items


def query_policies_by_ssn_last4(
    table_name: str,
    ssn_last4: str,
    region: str = "us-east-1"
) -> List[Dict]:
    """
    Query policies by SSN last 4 digits using a scan with filter.

    Args:
        table_name: Name of the DynamoDB table
        ssn_last4: Last 4 digits of SSN
        region: AWS region

    Returns:
        List of matching policy records
    """
    table = get_table(table_name, region)
    items = []

    response = table.scan(
        FilterExpression=Attr("ssnLast4").eq(ssn_last4)
    )
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression=Attr("ssnLast4").eq(ssn_last4),
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        items.extend(response.get("Items", []))

    return items


def query_policies_by_status(
    table_name: str,
    status: str,
    region: str = "us-east-1"
) -> List[Dict]:
    """
    Query policies by current status.

    Args:
        table_name: Name of the DynamoDB table
        status: Status to filter by (e.g., 'CARRIER_APPROVED')
        region: AWS region

    Returns:
        List of matching policy records
    """
    table = get_table(table_name, region)
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


def put_policy(
    table_name: str,
    policy: Dict,
    region: str = "us-east-1"
) -> Dict:
    """
    Put a policy record into the table.

    Args:
        table_name: Name of the DynamoDB table
        policy: Policy record to insert
        region: AWS region

    Returns:
        DynamoDB response
    """
    table = get_table(table_name, region)
    return table.put_item(Item=policy)


def update_policy_status(
    table_name: str,
    policy_number: str,
    transaction_id: str,
    new_status: str,
    notes: Optional[str] = None,
    region: str = "us-east-1"
) -> Dict:
    """
    Update the status of a policy and append to status history.

    Args:
        table_name: Name of the DynamoDB table
        policy_number: The policy number
        transaction_id: The transaction ID
        new_status: New status value
        notes: Optional notes for the status change
        region: AWS region

    Returns:
        DynamoDB response
    """
    from datetime import datetime, timezone

    table = get_table(table_name, region)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    history_item = {
        "status": new_status,
        "timestamp": timestamp
    }
    if notes:
        history_item["notes"] = notes

    response = table.update_item(
        Key={
            "pk": f"POLICY#{policy_number}",
            "sk": f"TRANSACTION#{transaction_id}"
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


def delete_policy(
    table_name: str,
    policy_number: str,
    transaction_id: str,
    region: str = "us-east-1"
) -> Dict:
    """
    Delete a policy record.

    Args:
        table_name: Name of the DynamoDB table
        policy_number: The policy number
        transaction_id: The transaction ID
        region: AWS region

    Returns:
        DynamoDB response
    """
    table = get_table(table_name, region)

    return table.delete_item(
        Key={
            "pk": f"POLICY#{policy_number}",
            "sk": f"TRANSACTION#{transaction_id}"
        }
    )


def format_policy_for_api(policy: Dict) -> Dict:
    """
    Format a DynamoDB policy record for API response.
    Matches the Policy Inquiry API spec format.

    Args:
        policy: Raw DynamoDB policy record

    Returns:
        Formatted policy for API response
    """
    return {
        "policyNumber": policy.get("policyNumber"),
        "carrierName": policy.get("carrierName"),
        "accountType": policy.get("accountType"),
        "planType": policy.get("planType"),
        "ownership": policy.get("ownership"),
        "productName": policy.get("productName"),
        "cusip": policy.get("cusip"),
        "trailingCommission": policy.get("trailingCommission", False),
        "contractStatus": policy.get("contractStatus"),
        "withdrawalStructure": policy.get("withdrawalStructure", {"systematicInPlace": False}),
        "errors": policy.get("errors", [])
    }


def format_policy_detail_for_api(policy: Dict) -> Dict:
    """
    Format a DynamoDB policy record for detailed API response.
    Includes all fields for carrier admin view.

    Args:
        policy: Raw DynamoDB policy record

    Returns:
        Formatted policy with all details
    """
    return {
        "transactionId": policy.get("transactionId"),
        "policyNumber": policy.get("policyNumber"),
        "carrierId": policy.get("carrierId"),
        "carrierName": policy.get("carrierName"),
        "currentStatus": policy.get("currentStatus"),
        "createdAt": policy.get("createdAt"),
        "updatedAt": policy.get("updatedAt"),
        "client": {
            "clientName": policy.get("clientName"),
            "ssnLast4": policy.get("ssnLast4")
        },
        "servicingAgent": policy.get("servicingAgent"),
        "policyDetails": {
            "accountType": policy.get("accountType"),
            "planType": policy.get("planType"),
            "ownership": policy.get("ownership"),
            "productName": policy.get("productName"),
            "cusip": policy.get("cusip"),
            "trailingCommission": policy.get("trailingCommission", False),
            "contractStatus": policy.get("contractStatus"),
            "withdrawalStructure": policy.get("withdrawalStructure", {"systematicInPlace": False})
        },
        "errors": policy.get("errors", [])
    }


def to_json(data: Any) -> str:
    """Convert data to JSON string, handling Decimal types."""
    return json.dumps(data, cls=DecimalEncoder)
