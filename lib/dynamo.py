""" Helpers functions to interact with DynamoDB """

import structlog
import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

# Boto3 Clients
DYNAMO_CLIENT = boto3.client('dynamodb')
DYNAMO_RESOURCE = boto3.resource('dynamodb')

# Logger
LOGGER = structlog.get_logger(__name__)


def dynamo_to_json(item):
    deserializer = TypeDeserializer()
    json_data = {k: deserializer.deserialize(v) for k, v in item.items()}
    return json_data


def json_to_dynamo(item):
    serializer = TypeSerializer()
    dynamo_response = {
        k: serializer.serialize(v) for k, v in item.items()}
    return dynamo_response


def get_all(table_name, deserialize=True):
    """ Function to get all items from a DynamoDB table """
    response = DYNAMO_CLIENT.scan(TableName=table_name)
    items = response.get('Items', [])

    if deserialize and items:
        # Deserialize each item
        items = [dynamo_to_json(item) for item in items]

    return items


def get_item(table_name, key):
    """Retrieve an item from DynamoDB by key"""
    try:
        table = DYNAMO_RESOURCE.Table(table_name)
        response = table.get_item(Key=key)
        return response.get('Item')
    except Exception as e:
        LOGGER.error(f"Error getting item from {table_name}", error=str(e))
        raise


def put_item(table_name, item):
    """Store an item in DynamoDB"""
    try:
        table = DYNAMO_RESOURCE.Table(table_name)
        table.put_item(Item=item)
        LOGGER.info(f"Item stored in {table_name}")
        return True
    except Exception as e:
        LOGGER.error(f"Error putting item in {table_name}", error=str(e))
        raise


def delete_item(table_name, key):
    """Delete an item from DynamoDB"""
    try:
        table = DYNAMO_RESOURCE.Table(table_name)
        table.delete_item(Key=key)
        LOGGER.info(f"Item deleted from {table_name}")
        return True
    except Exception as e:
        LOGGER.error(f"Error deleting item from {table_name}", error=str(e))
        raise
