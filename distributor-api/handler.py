"""
Distributor API Lambda Handler
Single-table DynamoDB design for agent/client/contract/transaction management.

Routes:
  GET  /agent/{npn}                    - Get agent profile
  GET  /agent/{npn}/clients            - Get all clients for agent
  POST /agent/{npn}/clients            - Create new client for agent
  GET  /agent/{npn}/transactions       - Get all transactions for agent
  POST /agent/{npn}/transactions       - Create new transaction
  GET  /client/{clientId}              - Get client profile
  GET  /client/{clientId}/contracts    - Get all contracts for client
"""

import json
import boto3
import uuid
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
TABLE_NAME = 'distributor'


def get_table():
    return dynamodb.Table(TABLE_NAME)


def response(status_code, body):
    """Standard API response."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Max-Age': '86400'
        },
        'body': json.dumps(body, default=str)
    }


def get_agent(npn):
    """Get agent profile."""
    table = get_table()
    result = table.get_item(Key={'pk': f'AGENT#{npn}', 'sk': 'PROFILE'})
    item = result.get('Item')
    if not item:
        return response(404, {'error': 'Agent not found'})
    return response(200, item)


def get_agent_clients(npn):
    """Get all clients for an agent."""
    table = get_table()
    result = table.query(
        KeyConditionExpression=Key('pk').eq(f'AGENT#{npn}') & Key('sk').begins_with('CLIENT#')
    )
    clients = result.get('Items', [])
    return response(200, {'clients': clients, 'count': len(clients)})


def create_client(npn, body):
    """Create a new client for an agent."""
    table = get_table()

    # Validate required fields
    required = ['clientName', 'ssnLast4']
    missing = [f for f in required if f not in body]
    if missing:
        return response(400, {'error': f'Missing required fields: {", ".join(missing)}'})

    # Verify agent exists
    agent_result = table.get_item(Key={'pk': f'AGENT#{npn}', 'sk': 'PROFILE'})
    if not agent_result.get('Item'):
        return response(404, {'error': 'Agent not found'})

    # Generate client ID
    client_id = str(uuid.uuid4())[:8].upper()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Create client profile
    client_profile = {
        'pk': f'CLIENT#{client_id}',
        'sk': 'PROFILE',
        'type': 'Client',
        'clientId': client_id,
        'clientName': body['clientName'],
        'ssnLast4': body['ssnLast4'],
        'createdAt': now
    }

    # Create agent-client link
    agent_client = {
        'pk': f'AGENT#{npn}',
        'sk': f'CLIENT#{client_id}',
        'type': 'AgentClient',
        'clientId': client_id,
        'clientName': body['clientName'],
        'ssnLast4': body['ssnLast4'],
        'assignedAt': now
    }

    # Write both items
    table.put_item(Item=client_profile)
    table.put_item(Item=agent_client)

    return response(201, {'message': 'Client created', 'client': client_profile})


def get_agent_transactions(npn):
    """Get all transactions for an agent."""
    table = get_table()
    result = table.query(
        KeyConditionExpression=Key('pk').eq(f'AGENT#{npn}') & Key('sk').begins_with('TRANSACTION#')
    )
    transactions = result.get('Items', [])
    return response(200, {'transactions': transactions, 'count': len(transactions)})


def get_client(client_id):
    """Get client profile."""
    table = get_table()
    result = table.get_item(Key={'pk': f'CLIENT#{client_id}', 'sk': 'PROFILE'})
    item = result.get('Item')
    if not item:
        return response(404, {'error': 'Client not found'})
    return response(200, item)


def get_client_contracts(client_id):
    """Get all contracts for a client."""
    table = get_table()
    result = table.query(
        KeyConditionExpression=Key('pk').eq(f'CLIENT#{client_id}') & Key('sk').begins_with('CONTRACT#')
    )
    contracts = result.get('Items', [])
    return response(200, {'contracts': contracts, 'count': len(contracts)})


def create_transaction(npn, body):
    """Create a new transaction for an agent."""
    table = get_table()

    # Validate required fields
    required = ['clientId', 'contracts', 'receivingBrokerId']
    missing = [f for f in required if f not in body]
    if missing:
        return response(400, {'error': f'Missing required fields: {", ".join(missing)}'})

    # Verify agent exists
    agent_result = table.get_item(Key={'pk': f'AGENT#{npn}', 'sk': 'PROFILE'})
    if not agent_result.get('Item'):
        return response(404, {'error': 'Agent not found'})

    agent = agent_result['Item']

    # Verify client exists and belongs to agent
    client_id = body['clientId']
    client_link = table.get_item(Key={'pk': f'AGENT#{npn}', 'sk': f'CLIENT#{client_id}'})
    if not client_link.get('Item'):
        return response(400, {'error': 'Client not found or not assigned to this agent'})

    client = client_link['Item']

    # Create transaction
    tx_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    transaction = {
        'pk': f'AGENT#{npn}',
        'sk': f'TRANSACTION#{tx_id}',
        'type': 'Transaction',
        'transactionId': tx_id,
        'clientId': client_id,
        'clientName': client.get('clientName'),
        'contracts': body['contracts'],
        'transactionType': body.get('transactionType', 'BD_CHANGE'),
        'status': 'MANIFEST_REQUESTED',
        'receivingBrokerId': body['receivingBrokerId'],
        'deliveringBrokerId': agent.get('firmId'),
        'createdAt': now,
        'updatedAt': now
    }

    table.put_item(Item=transaction)

    return response(201, {'message': 'Transaction created', 'transaction': transaction})


def handler(event, context):
    """Main Lambda handler - routes based on path and method."""

    http_method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    path = event.get('path') or event.get('rawPath', '/')

    # Handle CORS preflight
    if http_method == 'OPTIONS':
        return response(200, {})

    # Parse path segments
    segments = [s for s in path.split('/') if s]

    # Parse body for POST requests
    body = None
    if http_method == 'POST' and event.get('body'):
        try:
            body = json.loads(event['body'])
        except json.JSONDecodeError:
            return response(400, {'error': 'Invalid JSON body'})

    try:
        # Route: GET /agent/{npn}
        if len(segments) == 2 and segments[0] == 'agent' and http_method == 'GET':
            return get_agent(segments[1])

        # Route: GET /agent/{npn}/clients
        if len(segments) == 3 and segments[0] == 'agent' and segments[2] == 'clients' and http_method == 'GET':
            return get_agent_clients(segments[1])

        # Route: POST /agent/{npn}/clients
        if len(segments) == 3 and segments[0] == 'agent' and segments[2] == 'clients' and http_method == 'POST':
            return create_client(segments[1], body)

        # Route: GET /agent/{npn}/transactions
        if len(segments) == 3 and segments[0] == 'agent' and segments[2] == 'transactions' and http_method == 'GET':
            return get_agent_transactions(segments[1])

        # Route: POST /agent/{npn}/transactions
        if len(segments) == 3 and segments[0] == 'agent' and segments[2] == 'transactions' and http_method == 'POST':
            return create_transaction(segments[1], body)

        # Route: GET /client/{clientId}
        if len(segments) == 2 and segments[0] == 'client' and http_method == 'GET':
            return get_client(segments[1])

        # Route: GET /client/{clientId}/contracts
        if len(segments) == 3 and segments[0] == 'client' and segments[2] == 'contracts' and http_method == 'GET':
            return get_client_contracts(segments[1])

        # Health check
        if path in ['/', '/health']:
            return response(200, {'status': 'healthy', 'service': 'distributor-api'})

        return response(404, {'error': 'Not found', 'path': path, 'method': http_method})

    except Exception as e:
        return response(500, {'error': str(e)})
