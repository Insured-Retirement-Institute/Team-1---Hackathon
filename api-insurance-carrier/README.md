# Insurance Carrier API

A Flask-based REST API implementing the Insurance Carrier API specification for handling broker-dealer change validation requests. This API is designed to run on AWS Lambda and processes validation requests from the clearinghouse.

## Overview

This API provides endpoints for insurance carriers to:

- Receive BD change validation requests from the clearinghouse
- Perform validation checks (licensing, appointments, suitability, policy rules)
- Send validation responses (approval/rejection) back to clearinghouse
- Receive transfer completion notifications
- Track transaction status

## Validation Process

When a BD change request is received, the carrier validates:

1. **Agent Licensing** - Verify the new agent is properly licensed
2. **Carrier Appointments** - Confirm the agent is appointed with the carrier
3. **Suitability Requirements** - Check suitability compliance
4. **Policy-Specific Rules** - Validate against policy-level restrictions

Based on validation results, the carrier sends an approval or rejection response to the clearinghouse.

## Architecture

- **Framework**: Flask 3.0
- **Deployment**: AWS Lambda with API Gateway
- **Handler**: serverless-wsgi for WSGI-to-Lambda integration
- **Runtime**: Python 3.11

## API Endpoints

### Health Check

- `GET /health` - Service health check

### BD Change Validation

- `POST /receive-bd-change-request` - Receive validation request from clearinghouse

### Transfer Notifications

- `POST /receive-transfer-notification` - Receive transfer completion notification

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

The API will be available at `http://localhost:5002`

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
curl http://localhost:5002/health

# BD change validation request
curl -X POST http://localhost:5002/receive-bd-change-request \
  -H "Content-Type: application/json" \
  -H "transactionId: 123e4567-e89b-12d3-a456-426614174000" \
  -d '{
    "receivingBrokerId": "BROKER-001",
    "deliveringBrokerId": "BROKER-002",
    "carrierId": "CARRIER-PL",
    "policyNumber": "POL-001",
    "policyDetails": {
      "accountType": "individual",
      "planType": "nonQualified",
      "productName": "Pacific Select Variable Annuity"
    },
    "brokerDetails": {
      "agentName": "John Smith",
      "npn": "12345678",
      "licenseState": "CA"
    },
    "validationRequirements": {
      "licensing": true,
      "appointments": true,
      "suitability": true
    },
    "requestTimestamp": "2026-02-24T10:30:00Z"
  }'

# Transfer notification
curl -X POST http://localhost:5002/receive-transfer-notification \
  -H "Content-Type: application/json" \
  -H "transactionId: 123e4567-e89b-12d3-a456-426614174000" \
  -d '{
    "notificationType": "service-agent-change-complete",
    "policyNumber": "POL-001",
    "carrierId": "CARRIER-PL",
    "receivingBrokerId": "BROKER-001",
    "deliveringBrokerId": "BROKER-002",
    "effectiveDate": "2026-03-01",
    "notificationTimestamp": "2026-02-25T15:30:00Z"
  }'

# Query status
curl http://localhost:5002/query-status/123e4567-e89b-12d3-a456-426614174000
```

## Response Format

### Success Response

```json
{
  "code": "RECEIVED",
  "message": "BD change validation request received and queued for processing",
  "processingStatus": "deferred",
  "estimatedResponseTime": "Within 24 hours"
}
```

### Error Response

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Detailed error message"
}
```

## Processing Status Values

- `received` - Request received and acknowledged
- `processing` - Currently processing the request
- `deferred` - Processing deferred, will respond asynchronously

## Outbound Communications

The carrier API sends validation responses back to the clearinghouse:

**POST to Clearinghouse** `/receive-carrier-response`:

```json
{
  "transaction-id": "uuid",
  "carrier-id": "CARRIER-PL",
  "policy-id": "POL-001",
  "validation-result": "approved",
  "validation-details": {
    "licensingCheck": "passed",
    "appointmentCheck": "passed",
    "suitabilityCheck": "passed",
    "policyRulesCheck": "passed"
  },
  "response-timestamp": "2026-02-24T11:00:00Z"
}
```

For rejections, include `rejection-reason`:

```json
{
  "transaction-id": "uuid",
  "carrier-id": "CARRIER-PL",
  "policy-id": "POL-001",
  "validation-result": "rejected",
  "rejection-reason": "Agent not appointed with carrier",
  "validation-details": {
    "licensingCheck": "passed",
    "appointmentCheck": "failed",
    "suitabilityCheck": "not-checked",
    "policyRulesCheck": "not-checked"
  }
}
```

## Transaction Statuses

The carrier tracks transactions through these statuses:

- `CARRIER_VALIDATION_PENDING` - Validation request received
- `CARRIER_APPROVED` - Validation passed, BD change approved
- `CARRIER_REJECTED` - Validation failed, BD change rejected
- `TRANSFER_CONFIRMED` - Transfer completion confirmed
- `COMPLETE` - Process complete

## Environment Variables

Set these in `serverless.yml` or AWS Lambda console:

- `STAGE` - Deployment stage (dev, staging, prod)

## Database Integration

TODO: Add database layer for:

- Transaction persistence
- Validation history
- Policy lookup
- Agent appointment data
- Audit logging

Recommended: DynamoDB for serverless scalability

## Integration with Internal Systems

The carrier API should integrate with:

- **Agent Management System** - Verify appointments and licensing
- **Policy Administration System** - Validate policy details
- **Suitability Engine** - Check suitability requirements
- **Commission System** - Update servicing agent for commissions

## Authentication

In production, add authentication/authorization:

- API Gateway authorizers
- API keys
- JWT tokens
- AWS IAM authentication
- Mutual TLS for clearinghouse integration

## Logging

The application uses Python's logging module. Logs are sent to CloudWatch Logs when deployed to AWS Lambda.

## API Documentation

Full API documentation is available in the OpenAPI specification: `insurance-carrier-api.yaml`

## License

See LICENSE file for details.
