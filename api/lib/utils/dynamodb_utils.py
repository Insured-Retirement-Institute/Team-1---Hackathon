"""
DynamoDB utility functions for hackathon Lambda functions.
Provides generic, reusable methods for interacting with DynamoDB tables
across different entities in the pipeline.
"""

import boto3
from boto3.dynamodb.conditions import Key, Attr
from typing import Dict, List, Optional, Any, Union
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


def get_item(
    table_name: str,
    pk: str,
    sk: Optional[str] = None,
    region: str = "us-east-1"
) -> Optional[Dict]:
    """
    Get a single item by primary key.

    Args:
        table_name: Name of the DynamoDB table
        pk: Partition key value
        sk: Sort key value (optional, required if table has sort key)
        region: AWS region

    Returns:
        Item or None if not found
    """
    table = get_table(table_name, region)

    key = {"pk": pk}
    if sk is not None:
        key["sk"] = sk

    response = table.get_item(Key=key)
    return response.get("Item")


def query_items(
    table_name: str,
    pk: str,
    sk_condition: Optional[Any] = None,
    filter_expression: Optional[Any] = None,
    region: str = "us-east-1"
) -> List[Dict]:
    """
    Query items by partition key with optional sort key condition and filter.

    Args:
        table_name: Name of the DynamoDB table
        pk: Partition key value
        sk_condition: Optional sort key condition (e.g., Key("sk").begins_with("PREFIX#"))
        filter_expression: Optional filter expression (e.g., Attr("status").eq("Active"))
        region: AWS region

    Returns:
        List of matching items
    """
    table = get_table(table_name, region)
    items = []

    key_condition = Key("pk").eq(pk)
    if sk_condition is not None:
        key_condition = key_condition & sk_condition

    query_kwargs = {"KeyConditionExpression": key_condition}
    if filter_expression is not None:
        query_kwargs["FilterExpression"] = filter_expression

    response = table.query(**query_kwargs)
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        response = table.query(**query_kwargs)
        items.extend(response.get("Items", []))

    return items


def scan_items(
    table_name: str,
    filter_expression: Optional[Any] = None,
    region: str = "us-east-1"
) -> List[Dict]:
    """
    Scan all items with optional filter expression.

    Args:
        table_name: Name of the DynamoDB table
        filter_expression: Optional filter expression (e.g., Attr("clientName").eq("John"))
        region: AWS region

    Returns:
        List of matching items
    """
    table = get_table(table_name, region)
    items = []

    scan_kwargs = {}
    if filter_expression is not None:
        scan_kwargs["FilterExpression"] = filter_expression

    response = table.scan(**scan_kwargs)
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

    return items


def put_item(
    table_name: str,
    item: Dict,
    region: str = "us-east-1"
) -> Dict:
    """
    Put an item into the table.

    Args:
        table_name: Name of the DynamoDB table
        item: Item to insert (must include pk and sk if table requires it)
        region: AWS region

    Returns:
        DynamoDB response
    """
    table = get_table(table_name, region)
    return table.put_item(Item=item)


def update_item(
    table_name: str,
    pk: str,
    sk: Optional[str] = None,
    updates: Optional[Dict[str, Any]] = None,
    update_expression: Optional[str] = None,
    expression_values: Optional[Dict[str, Any]] = None,
    expression_names: Optional[Dict[str, str]] = None,
    region: str = "us-east-1"
) -> Dict:
    """
    Update an item. Supports either simple updates dict or custom expressions.

    Args:
        table_name: Name of the DynamoDB table
        pk: Partition key value
        sk: Sort key value (optional)
        updates: Simple dict of field names to new values (auto-builds expression)
        update_expression: Custom UpdateExpression string
        expression_values: ExpressionAttributeValues for custom expression
        expression_names: ExpressionAttributeNames for custom expression
        region: AWS region

    Returns:
        DynamoDB response with updated item
    """
    table = get_table(table_name, region)

    key = {"pk": pk}
    if sk is not None:
        key["sk"] = sk

    update_kwargs = {"Key": key, "ReturnValues": "ALL_NEW"}

    if updates:
        # Build expression from simple updates dict
        update_parts = []
        expr_values = {}
        for i, (field, value) in enumerate(updates.items()):
            if field not in ("pk", "sk"):
                update_parts.append(f"{field} = :val{i}")
                expr_values[f":val{i}"] = value
        update_kwargs["UpdateExpression"] = "SET " + ", ".join(update_parts)
        update_kwargs["ExpressionAttributeValues"] = expr_values
    else:
        # Use custom expression
        if update_expression:
            update_kwargs["UpdateExpression"] = update_expression
        if expression_values:
            update_kwargs["ExpressionAttributeValues"] = expression_values
        if expression_names:
            update_kwargs["ExpressionAttributeNames"] = expression_names

    return table.update_item(**update_kwargs)


def delete_item(
    table_name: str,
    pk: str,
    sk: Optional[str] = None,
    region: str = "us-east-1"
) -> Dict:
    """
    Delete an item.

    Args:
        table_name: Name of the DynamoDB table
        pk: Partition key value
        sk: Sort key value (optional)
        region: AWS region

    Returns:
        DynamoDB response
    """
    table = get_table(table_name, region)

    key = {"pk": pk}
    if sk is not None:
        key["sk"] = sk

    return table.delete_item(Key=key)


def batch_write_items(
    table_name: str,
    items: List[Dict],
    region: str = "us-east-1"
) -> None:
    """
    Batch write items to a table (max 25 per batch).

    Args:
        table_name: Name of the DynamoDB table
        items: List of items to write
        region: AWS region
    """
    table = get_table(table_name, region)

    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)


def batch_delete_items(
    table_name: str,
    keys: List[Dict],
    region: str = "us-east-1"
) -> None:
    """
    Batch delete items from a table.

    Args:
        table_name: Name of the DynamoDB table
        keys: List of key dicts (each with pk and optionally sk)
        region: AWS region
    """
    table = get_table(table_name, region)

    with table.batch_writer() as batch:
        for key in keys:
            batch.delete_item(Key=key)


def to_json(data: Any) -> str:
    """Convert data to JSON string, handling Decimal types."""
    return json.dumps(data, cls=DecimalEncoder)


# ---- Carrier / Policy helpers -----------------------------------------------
# These are domain-specific wrappers used by lib/carrier/handler.py.
# The carrier tables store one item per policy; pk = "POLICY#<policyNumber>".

def scan_all_policies(
    table_name: str,
    region: str = "us-east-1"
) -> List[Dict]:
    """
    Return every item in the given carrier table.
    """
    return scan_items(table_name, region=region)


def get_policy_by_number(
    table_name: str,
    policy_number: str,
    region: str = "us-east-1"
) -> Optional[Dict]:
    """
    Return the policy whose policyNumber attribute matches *policy_number*.
    Tries a direct key lookup first (pk = "POLICY#<policyNumber>"), then falls
    back to a scan if the item isn't found under that key.
    """
    # Optimistic direct lookup
    item = get_item(table_name, pk=f"POLICY#{policy_number}", region=region)
    if item:
        return item

    # Fallback: scan with attribute filter
    results = scan_items(
        table_name,
        filter_expression=Attr("policyNumber").eq(policy_number),
        region=region,
    )
    return results[0] if results else None


def get_policy_by_transaction(
    table_name: str,
    request_id: str,
    region: str = "us-east-1"
) -> Optional[Dict]:
    """Return the policy associated with *request_id*."""
    results = scan_items(
        table_name,
        filter_expression=Attr("requestId").eq(request_id),
        region=region,
    )
    return results[0] if results else None


def query_policies_by_client(
    table_name: str,
    client_name: str,
    region: str = "us-east-1"
) -> List[Dict]:
    """Return all policies for the given clientName."""
    return scan_items(
        table_name,
        filter_expression=Attr("clientName").eq(client_name),
        region=region,
    )


def query_policies_by_ssn_last4(
    table_name: str,
    ssn_last4: str,
    region: str = "us-east-1"
) -> List[Dict]:
    """Return all policies whose ssnLast4 matches."""
    return scan_items(
        table_name,
        filter_expression=Attr("ssnLast4").eq(ssn_last4),
        region=region,
    )


def query_policies_by_status(
    table_name: str,
    status: str,
    region: str = "us-east-1"
) -> List[Dict]:
    """Return all policies whose contractStatus matches."""
    return scan_items(
        table_name,
        filter_expression=Attr("contractStatus").eq(status),
        region=region,
    )


def put_policy(
    table_name: str,
    policy: Dict,
    region: str = "us-east-1"
) -> Dict:
    """
    Write a policy item. Ensures the pk is set to ``POLICY#<policyNumber>``
    if not already present.
    """
    if "pk" not in policy and "policyNumber" in policy:
        policy = {"pk": f"POLICY#{policy['policyNumber']}", **policy}
    return put_item(table_name, policy, region=region)


def update_policy_status(
    table_name: str,
    policy_number: str,
    request_id: str,
    new_status: str,
    notes: Optional[str] = None,
    region: str = "us-east-1"
) -> Dict:
    """
    Update the contractStatus / currentStatus of a policy and append to
    statusHistory.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Resolve the pk (direct lookup first, then scan)
    policy = get_policy_by_number(table_name, policy_number, region=region)
    if not policy:
        raise ValueError(f"Policy {policy_number} not found in {table_name}")

    pk = policy["pk"]
    sk = policy.get("sk")

    history_entry = {"status": new_status, "timestamp": now}
    if notes:
        history_entry["notes"] = notes
    if request_id:
        history_entry["requestId"] = request_id

    existing_history = policy.get("statusHistory", [])
    updated_history = existing_history + [history_entry]

    return update_item(
        table_name,
        pk=pk,
        sk=sk,
        updates={
            "contractStatus": new_status,
            "currentStatus": new_status,
            "requestId": request_id,
            "updatedAt": now,
            "statusHistory": updated_history,
        },
        region=region,
    )


def delete_policy(
    table_name: str,
    policy_number: str,
    region: str = "us-east-1"
) -> Dict:
    """Delete a policy by its policyNumber."""
    policy = get_policy_by_number(table_name, policy_number, region=region)
    if not policy:
        raise ValueError(f"Policy {policy_number} not found in {table_name}")
    return delete_item(table_name, pk=policy["pk"], sk=policy.get("sk"), region=region)


def format_policy_for_api(policy: Dict) -> Dict:
    """Return a concise summary of a policy for list views."""
    return {
        "policyNumber": policy.get("policyNumber"),
        "carrierName": policy.get("carrierName"),
        "clientName": policy.get("clientName"),
        "contractStatus": policy.get("contractStatus") or policy.get("currentStatus"),
        "planType": policy.get("planType"),
        "accountType": policy.get("accountType"),
        "updatedAt": policy.get("updatedAt"),
    }


def format_policy_detail_for_api(policy: Dict) -> Dict:
    """Return the full detail view of a policy for single-record endpoints."""
    return {
        "policyNumber": policy.get("policyNumber"),
        "carrierName": policy.get("carrierName"),
        "carrierId": policy.get("carrierId"),
        "clientName": policy.get("clientName"),
        "ssnLast4": policy.get("ssnLast4"),
        "accountType": policy.get("accountType"),
        "planType": policy.get("planType"),
        "ownership": policy.get("ownership"),
        "productName": policy.get("productName"),
        "cusip": policy.get("cusip"),
        "trailingCommission": policy.get("trailingCommission", False),
        "contractStatus": policy.get("contractStatus") or policy.get("currentStatus"),
        "currentStatus": policy.get("currentStatus") or policy.get("contractStatus"),
        "withdrawalStructure": policy.get("withdrawalStructure", {"systematicInPlace": False}),
        "servicingAgent": policy.get("servicingAgent", {}),
        "requestId": policy.get("requestId"),
        "statusHistory": policy.get("statusHistory", []),
        "createdAt": policy.get("createdAt"),
        "updatedAt": policy.get("updatedAt"),
        "errors": policy.get("errors", []),
    }


# Re-export condition builders for convenience
__all__ = [
    "get_dynamodb_resource",
    "get_dynamodb_client",
    "get_table",
    "get_item",
    "query_items",
    "scan_items",
    "put_item",
    "update_item",
    "delete_item",
    "batch_write_items",
    "batch_delete_items",
    "to_json",
    "DecimalEncoder",
    "Key",
    "Attr",
    # Carrier / policy helpers
    "scan_all_policies",
    "get_policy_by_number",
    "get_policy_by_transaction",
    "query_policies_by_client",
    "query_policies_by_ssn_last4",
    "query_policies_by_status",
    "put_policy",
    "update_policy_status",
    "delete_policy",
    "format_policy_for_api",
    "format_policy_detail_for_api",
]
