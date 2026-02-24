# Clearinghouse API

A Flask-based REST API implementing the Clearinghouse API specification for orchestrating broker-dealer change processes. This API is designed to run on AWS Lambda and acts as the central hub routing requests between broker-dealers and insurance carriers.

## Overview

This API provides endpoints for the clearinghouse to:

- Receive policy inquiry requests from receiving brokers and route to delivering brokers
- Receive policy inquiry responses from delivering brokers and forward to receiving brokers
- Process BD change requests and coordinate with carriers for validation
- Handle carrier validation responses
- Process transfer confirmations
- Track transaction status throughout the workflow

## Key Characteristics

**Deferred Processing**: The clearinghouse ALWAYS returns deferred responses (no payload). All responses include a `transactionId` for tracking, with actual data delivery handled through separate callback mechanisms.

**Orchestration Role**: The clearinghouse acts as the central coordinator, routing messages between:

- Receiving broker-dealers
- Delivering broker-dealers
- Insurance carriers

## Architecture

- **Framework**: Flask 3.0
- **Deployment**: AWS Lambda with API Gateway
- **Handler**: serverless-wsgi for WSGI-to-Lambda integration
- **Runtime**: Python 3.11

## API Endpoints

### Health Check

- `GET /health` - Service health check

### Policy Inquiry Flow

- `POST /submit-policy-inquiry-request` - Receive from receiving broker, route to delivering broker
- `POST /submit-policy-inquiry-response` - Receive from delivering broker, forward to receiving broker

### BD Change Process

- `POST /receive-bd-change-request` - Receive from receiving broker, route to carrier
- `POST /receive-carrier-response` - Receive carrier validation, route to receiving broker
- `POST /receive-transfer-confirmation` - Receive from delivering broker, broadcast to parties

### Status Query

- `GET /query-status/{transactionId}` - Query transaction status and history

## Setup

### Prerequisites

- Python 3.11+
- Node.js and npm (for Serverless Framework)
- AWS CLI configured with appropriate credentials

### Local Development

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Run locally:

```bash
python app.py
```

The API will be available at `http://localhost:5001`

### AWS Lambda Deployment

1. Install Serverless Framework:

```bash
npm install -g serverless
```

2. Install Serverless plugins:

```bash
npm install
```

3. Deploy to AWS:

```bash
serverless deploy --stage dev --region us-east-1
```

4. Deploy to production:

```bash
serverless deploy --stage prod --region us-east-1
```

### Testing

Test endpoints locally:

```bash
# Health check
curl http://localhost:5001/health

# Policy inquiry request from receiving broker
curl -X POST http://localhost:5001/submit-policy-inquiry-request \
  -H "Content-Type: application/json" \
  -H "transactionId: 123e4567-e89b-12d3-a456-426614174000" \
  -d '{
    "requestingFirm": {
      "firmName": "Acme Financial",
      "firmId": "FIRM123",
      "servicingAgent": {
        "agentName": "John Smith",
        "npn": "12345678"
      }
    },
    "client": {
      "clientName": "Jane Doe",
      "ssn": "123-45-6789",
      "policyNumbers": ["POL001", "POL002"]
    }
  }'

# BD change request from receiving broker
curl -X POST http://localhost:5001/receive-bd-change-request \
  -H "Content-Type: application/json" \
  -H "transactionId: 123e4567-e89b-12d3-a456-426614174000" \
  -d '{
    "transaction-id": "123e4567-e89b-12d3-a456-426614174000",
    "receiving-broker-id": "BROKER-001",
    "delivering-broker-id": "BROKER-002",
    "carrier-id": "CARRIER-PL",
    "policy-id": "POL-001"
  }'

# Carrier validation response
curl -X POST http://localhost:5001/receive-carrier-response \
  -H "Content-Type: application/json" \
  -H "transactionId: 123e4567-e89b-12d3-a456-426614174000" \
  -d '{
    "transaction-id": "123e4567-e89b-12d3-a456-426614174000",
    "carrier-id": "CARRIER-PL",
    "policy-id": "POL-001",
    "validation-result": "approved"
  }'

# Query status
curl http://localhost:5001/query-status/123e4567-e89b-12d3-a456-426614174000
```

## Response Format

All clearinghouse responses follow this format:

### Success Response

```json
{
  "code": "RECEIVED",
  "message": "Request received and routed",
  "transactionId": "123e4567-e89b-12d3-a456-426614174000",
  "payload": null
}
```

**Note**: `payload` is ALWAYS `null` for clearinghouse responses. All processing is deferred.

### Error Response

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Detailed error message"
}
```

## Transaction Statuses

The clearinghouse tracks transactions through these statuses:

- `MANIFEST_REQUESTED` - Initial policy inquiry sent to delivering broker
- `MANIFEST_RECEIVED` - Policy details received from delivering broker
- `DUE_DILIGENCE_COMPLETE` - Due diligence checks completed
- `CARRIER_VALIDATION_PENDING` - Waiting for carrier validation
- `CARRIER_APPROVED` - Carrier approved the BD change
- `CARRIER_REJECTED` - Carrier rejected the BD change
- `TRANSFER_INITIATED` - Transfer process started
- `TRANSFER_PROCESSING` - Transfer in progress
- `TRANSFER_CONFIRMED` - Transfer completed successfully
- `COMPLETE` - Entire process complete

## Environment Variables

Set these in `serverless.yml` or AWS Lambda console:

- `STAGE` - Deployment stage (dev, staging, prod)

## Routing Logic

The clearinghouse implements routing logic to:

1. **Policy Inquiry Requests**: Route to appropriate delivering broker based on policy ownership
2. **Policy Inquiry Responses**: Forward to original requesting broker
3. **BD Change Requests**: Route to carrier for validation
4. **Carrier Responses**: Forward to receiving broker
5. **Transfer Confirmations**: Broadcast to receiving broker and carrier

## Authentication

In production, add authentication/authorization:

- API Gateway authorizers
- API keys
- JWT tokens
- AWS IAM authentication
- Mutual TLS for partner integrations

## Database Integration

TODO: Add database layer for:

- Transaction persistence
- Status tracking
- Routing configuration
- Audit logging

Recommended: DynamoDB for serverless scalability

## Logging

The application uses Python's logging module. Logs are sent to CloudWatch Logs when deployed to AWS Lambda.

## API Documentation

Full API documentation is available in the OpenAPI specification: `clearinghouse-api.yaml`

## License

See LICENSE file for details.
