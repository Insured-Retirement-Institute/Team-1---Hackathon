# Broker-Dealer API

A Flask-based REST API implementing the Broker-Dealer API specification for handling broker-dealer change processes. This API is designed to run on AWS Lambda.

## Overview

This API provides endpoints for broker-dealers (both receiving and delivering) to:

- Receive and respond to policy inquiry requests
- Handle BD change requests
- Process transfer notifications
- Query transaction status

## Architecture

- **Framework**: Flask 3.0
- **Deployment**: AWS Lambda with API Gateway
- **Handler**: serverless-wsgi for WSGI-to-Lambda integration
- **Runtime**: Python 3.11

## API Endpoints

### Health Check

- `GET /health` - Service health check

### Policy Inquiry

- `POST /submit-policy-inquiry-request` - Receive policy inquiry request (delivering broker)
- `POST /receive-policy-inquiry-response` - Receive policy inquiry response (receiving broker)

### BD Change Process

- `POST /receive-bd-change-request` - Receive BD change request (receiving broker)
- `POST /receive-transfer-notification` - Receive transfer notifications

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

The API will be available at `http://localhost:5000`

### AWS Lambda Deployment

1. Install Serverless Framework:

```bash
npm install -g serverless
```

2. Install Serverless plugins:

```bash
npm install --save-dev serverless-python-requirements serverless-wsgi
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
curl http://localhost:5000/health

# Policy inquiry request (requires transactionId header)
curl -X POST http://localhost:5000/submit-policy-inquiry-request \
  -H "Content-Type: application/json" \
  -H "transactionId: 123e4567-e89b-12d3-a456-426614174000" \
  -d '{
    "requestingFirm": {
      "firmName": "Example Firm",
      "firmId": "FIRM123",
      "servicingAgent": {
        "agentName": "John Doe",
        "npn": "12345678"
      }
    },
    "client": {
      "clientName": "Jane Smith",
      "ssn": "123-45-6789",
      "policyNumbers": ["POL001", "POL002"]
    }
  }'

# Query status
curl http://localhost:5000/query-status/123e4567-e89b-12d3-a456-426614174000
```

## Environment Variables

Set these in `serverless.yml` or AWS Lambda console:

- `STAGE` - Deployment stage (dev, staging, prod)

## Authentication

In production, add authentication/authorization:

- API Gateway authorizers
- API keys
- JWT tokens
- AWS IAM authentication

## Logging

The application uses Python's logging module. Logs are sent to CloudWatch Logs when deployed to AWS Lambda.

## Error Handling

All endpoints return standardized responses:

Success response:

```json
{
  "code": "RECEIVED",
  "message": "Request processed successfully",
  "payload": {}
}
```

Error response:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Detailed error message"
}
```

## API Documentation

Full API documentation is available in the OpenAPI specification: `broker-dealer-api.yaml`

## License

See LICENSE file for details.
