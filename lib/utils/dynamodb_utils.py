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
]
