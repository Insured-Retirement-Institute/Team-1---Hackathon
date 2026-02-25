# BD Change Process API Flow Summary

This document summarizes the three OpenAPI specifications created for the Broker-Dealer change process and validates that they match the sequence diagram requirements.

## Overview

Three separate OpenAPI specifications have been created to handle the BD change process:

1. **Clearinghouse API** (`clearinghouse-api.yaml`) - Central hub for receiving requests
2. **Broker-Dealer API** (`broker-dealer-api.yaml`) - For both receiving and delivering brokers  
3. **Insurance Carrier API** (`insurance-carrier-api.yaml`) - For insurance carriers

## New Response Format Structure

All APIs now use a standardized nested response format:

```json
{
  "code": "RESPONSE_CODE",
  "message": "Human-readable message",
  "requestId": "uuid-format-request-id",
  "payload": {} // or null
}
```

### Response Behavior Rules

#### Clearinghouse API Behavior
- **Always deferred responses**: Never returns payload data immediately
- **Transaction ID provision**: Always provides requestId for tracking
- **No immediate data**: payload field is always null
- **Internal routing**: Handles forwarding between brokers and carriers

#### Broker-Dealer API Behavior
- **Flexible response mode**: Can return immediate (with payload) or deferred (without payload)
- **Transaction ID reflection**: Must reflect requestId received from clearinghouse
- **Payload inclusion**: May include payload for immediate processing, omit for deferred
- **Processing indication**: Uses code field to indicate processing status

#### Response Code Examples
- `RECEIVED`: Request acknowledged and queued
- `PROCESSING`: Request being actively processed
- `DEFERRED`: Processing deferred, use requestId for tracking
- `SUCCESS`: Operation completed successfully
- `ERROR`: Operation failed

## Policy Inquiry API Updates

### New Policy Inquiry Request/Response Schema

The APIs have been updated to support the detailed policy inquiry process with comprehensive policy information:

#### Policy Inquiry Request Structure
```json
{
  "policy-inquiry-request": {
    "requesting-firm": {
      "firm-name": "string",
      "firm-id": "string", 
      "servicing-agent": {
        "agent-name": "string",
        "npn": "string"
      }
    },
    "client": {
      "client-name": "string",
      "ssn": "string",
      "contract-numbers": ["string"]
    }
  }
}
```

#### Policy Inquiry Response Structure
```json
{
  "policy-inquiry-response": {
    "client": {
      "client-name": "string",
      "ssn-last-4": "string",
      "policies": {
        "<contract-number>": {
          "carrier-name": "string",
          "account-type": "individual|joint|trust|custodial|entity",
          "plan-type": "non-qualified|roth-ira|traditional-ira|sep|simple", 
          "ownership": "string",
          "product-name": "string",
          "cusip": "string",
          "trailing-commission": true|false,
          "contract-status": "string",
          "withdrawal-structure": {
            "systematic-in-place": true|false
          },
          "errors": ["string"]
        }
      }
    },
    "enums": {
      "account-type": ["individual", "joint", "trust", "custodial", "entity"],
      "plan-type": ["non-qualified", "roth-ira", "traditional-ira", "sep", "simple"]
    }
  }
}
```

### Security and Privacy Enhancements
- **SSN Protection**: Response includes only last 4 digits of SSN for security
- **Contract-Keyed Policies**: Policies organized by contract number for efficient lookup
- **Error Handling**: Each policy can include specific error information

### New API Endpoints

#### Broker-Dealer API Additions
- `POST /receive-policy-inquiry-response` - Receiving broker receives policy details from clearinghouse

This endpoint supports the new nested response format with optional payload inclusion based on processing mode (immediate vs deferred).

## Response Pattern Examples

### Clearinghouse Response Examples

#### Policy Inquiry Request Received (Always Deferred)
```json
{
  "code": "RECEIVED",
  "message": "Policy inquiry request received and routed to delivering broker",
  "requestId": "123e4567-e89b-12d3-a456-426614174000",
  "payload": null
}
```

#### Policy Inquiry Response Received (Always Deferred)
```json
{
  "code": "RECEIVED", 
  "message": "Policy inquiry response received and forwarded to requesting broker",
  "requestId": "123e4567-e89b-12d3-a456-426614174000",
  "payload": null
}
```

### Broker-Dealer Response Examples

#### Immediate Response with Policy Data
```json
{
  "code": "SUCCESS",
  "message": "Policy inquiry processed successfully",
  "requestId": "123e4567-e89b-12d3-a456-426614174000",
  "payload": {
    "policy-inquiry-response": {
      "client": {
        "client-name": "John Doe",
        "ssn-last-4": "1234",
        "policies": {
          "ANN-12345": {
            "carrier-name": "ABC Insurance Company",
            "account-type": "individual",
            "plan-type": "non-qualified",
            "ownership": "Individual",
            "product-name": "ABC Fixed Annuity",
            "cusip": "123456789",
            "trailing-commission": true,
            "contract-status": "Active",
            "withdrawal-structure": {
              "systematic-in-place": false
            },
            "errors": []
          }
        }
      },
      "enums": {
        "account-type": ["individual", "joint", "trust", "custodial", "entity"],
        "plan-type": ["non-qualified", "roth-ira", "traditional-ira", "sep", "simple"]
      }
    }
  }
}
```

#### Deferred Response (Processing Required)
```json
{
  "code": "DEFERRED",
  "message": "Policy inquiry request received and queued for processing",
  "requestId": "123e4567-e89b-12d3-a456-426614174000",
  "payload": null
}
```

#### Error Response Example
```json
{
  "code": "ERROR",
  "message": "Invalid contract number provided",
  "requestId": "123e4567-e89b-12d3-a456-426614174000",
  "payload": {
    "error-details": {
      "field": "contract-numbers",
      "invalid-values": ["INVALID-123"]
    }
  }
}
```

### Transaction ID Flow Example

1. **Receiving Broker** submits policy inquiry → Gets `requestId: "abc-123"`
2. **Clearinghouse** receives request → Returns same `requestId: "abc-123"`
3. **Delivering Broker** receives forwarded request → Must use same `requestId: "abc-123"` in response
4. **Clearinghouse** receives response → Forwards with same `requestId: "abc-123"`
5. **Receiving Broker** receives final response → Same `requestId: "abc-123"` maintained throughout

## API Flow Validation Against Sequence Diagram

### Step 1: Manifest Request
**Sequence**: RBD → Clearinghouse → DBD

**API Flow**:
1. Receiving Broker-Dealer calls: `POST https://api.example.com/v1/submit-policy-inquiry-request`
2. Clearinghouse internally forwards to Delivering Broker-Dealer: `POST https://api.example.com/v1/submit-policy-inquiry-request`
3. Status updated to: `MANIFEST_REQUESTED`

✅ **Validated**: API supports this flow with proper routing and status tracking.

### Step 2: Policy List Response  
**Sequence**: DBD → Clearinghouse → RBD

**API Flow**:
1. Delivering Broker-Dealer calls: `POST https://api.example.com/v1/submit-policy-inquiry-response`
2. Clearinghouse internally forwards response to Receiving Broker-Dealer
3. Status updated to: `MANIFEST_RECEIVED`

✅ **Validated**: API supports immediate and deferred responses via `response-type` field.

### Step 3: Due Diligence
**Sequence**: RBD internal process

**API Flow**:
- Internal broker process (no API calls)
- Status can be updated to: `DUE_DILIGENCE_COMPLETE`

✅ **Validated**: Status enum includes this state.

### Step 4: BD Change Request to Carrier
**Sequence**: RBD → Clearinghouse → CAR (loop for each policy)

**API Flow**:
1. Receiving Broker-Dealer calls: `POST https://api.example.com/v1/receive-bd-change-request`
2. Clearinghouse internally forwards to Carrier: `POST https://api.example.com/v1/receive-bd-change-request`
3. Status updated to: `CARRIER_VALIDATION_PENDING`

✅ **Validated**: API supports per-policy requests with loop capability.

### Step 5: Carrier Validates & Responds
**Sequence**: CAR validation → CAR → Clearinghouse → RBD

**API Flow**:
1. Carrier performs internal validation
2. Carrier calls: `POST https://api.example.com/v1/receive-carrier-response`
3. Clearinghouse internally forwards to Receiving Broker-Dealer
4. Status updated to: `CARRIER_APPROVED` or `CARRIER_REJECTED`

✅ **Validated**: API supports both approval and rejection paths with reasons.

### Steps 6-8: Transfer Processing
**Sequence**: Various transfer confirmations and notifications

**API Flow**:
1. Transfer initiation: Status → `TRANSFER_INITIATED`
2. Delivering Broker confirmation: `POST https://api.example.com/v1/receive-transfer-confirmation`
3. Status updates: `TRANSFER_PROCESSING` → `TRANSFER_CONFIRMED` → `COMPLETE`
4. Final notifications sent to all parties

✅ **Validated**: API supports complete transfer workflow with notifications.

### Status API (Available to All)
**Sequence**: All parties can query status

**API Flow**:
- All parties can call: `GET /query-status/{request-id}`
- Returns current status and full history

✅ **Validated**: Status API available in all three specifications.

## Key Features Implemented

### Transaction Management
- **Persistent Transaction ID**: UUID format used across all APIs
- **Required Transaction Headers**: All POST endpoints require `requestId` header parameter
- **Status Tracking**: Complete status enum covering all diagram states
- **History Tracking**: Full audit trail of status changes

### Transaction ID Header Requirements

All API POST endpoints require a `requestId` header parameter for request tracking and correlation:

```http
POST /submit-policy-inquiry-request
Content-Type: application/json
requestId: 123e4567-e89b-12d3-a456-426614174000

{
  "requestingFirm": { ... },
  "client": { ... }
}
```

#### Header Specification
- **Parameter Name**: `requestId`
- **Location**: HTTP Header
- **Required**: Yes (for all POST endpoints)
- **Format**: UUID (string format)
- **Description**: Unique transaction identifier that flows through all related requests

#### Endpoints Requiring RequestId Header
**Clearinghouse API:**
- `POST /submit-policy-inquiry-request` ✅
- `POST /submit-policy-inquiry-response` ✅  
- `POST /receive-bd-change-request` ✅
- `POST /receive-carrier-response` ✅
- `POST /receive-transfer-confirmation` ✅

**Broker-Dealer API:**
- `POST /submit-policy-inquiry-request` ✅
- `POST /receive-policy-inquiry-response` ✅
- `POST /receive-bd-change-request` ✅  
- `POST /receive-transfer-notification` ✅

**Insurance Carrier API:**
- `POST /receive-bd-change-request` ✅
- `POST /receive-transfer-notification` ✅

#### Endpoints NOT Requiring RequestId Header
**All APIs:**
- `GET /query-status/{requestId}` - Transaction ID provided in URL path parameter instead

#### Transaction ID Flow with Headers
1. **Receiving Broker** submits request with `requestId: "abc-123"` header
2. **Clearinghouse** receives request, validates header, forwards with same `requestId: "abc-123"`
3. **Delivering Broker** processes request using `requestId: "abc-123"` from header
4. All subsequent requests in the flow must include the same `requestId` header value
5. Response payloads also include `requestId` field for correlation

### Deferred Processing Support
- **Immediate vs Deferred**: Responses can be processed immediately or deferred
- **Processing Status**: APIs indicate how requests will be handled
- **Asynchronous Flow**: Support for async processing with callbacks

### Open-Ended Data Structure
- **Additional Data Fields**: All schemas include `additional-data` objects
- **JSON Only**: All payloads use JSON format as specified
- **Kebab Case URLs**: All route URLs use kebab-case formatting

### Error Handling
- **Standard Responses**: Consistent response format across all APIs
- **Error Codes**: Structured error responses with codes and messages
- **HTTP Status Codes**: Proper use of 200, 400, 404, 500

## Route Summary by API

### Clearinghouse API (Inbound Only)
- `POST /submit-policy-inquiry-request` - From receiving brokers
- `POST /submit-policy-inquiry-response` - From delivering brokers
- `POST /receive-bd-change-request` - From receiving brokers
- `POST /receive-carrier-response` - From carriers
- `POST /receive-transfer-confirmation` - From delivering brokers
- `GET /query-status/{request-id}` - Status queries

### Broker-Dealer API  
- `POST /submit-policy-inquiry-request` - From clearinghouse (delivering broker)
- `POST /receive-policy-inquiry-response` - From clearinghouse (receiving broker)
- `POST /receive-bd-change-request` - From clearinghouse (receiving broker)
- `POST /receive-transfer-notification` - From clearinghouse
- `GET /query-status/{request-id}` - Status queries

### Insurance Carrier API
- `POST /receive-bd-change-request` - From clearinghouse
- `POST /receive-transfer-notification` - From clearinghouse  
- `GET /query-status/{request-id}` - Status queries

## Data Flow Architecture

```
Receiving Broker → Clearinghouse → Delivering Broker (Manifest)
Delivering Broker → Clearinghouse → Receiving Broker (Response)
Receiving Broker → Clearinghouse → Carrier (BD Change Request)  
Carrier → Clearinghouse → Receiving Broker (Validation Response)
All Parties ↔ Clearinghouse (Status Queries)
```

The clearinghouse acts as a central message hub, receiving requests from all parties and internally routing them to appropriate destinations. No public routes expose the internal forwarding logic.

## Security Considerations

The specifications intentionally exclude security constraints as requested, but production implementations should consider:
- Authentication and authorization
- API rate limiting  
- Request/response encryption
- Audit logging
- Message signing/verification

## Compliance with Requirements

✅ **Mermaid Diagram Mapping**: All sequence flows represented  
✅ **Three Separate Specs**: Clearinghouse, Broker-Dealer, Carrier APIs
✅ **Constructive Verb Routes**: Clear action indication in URLs  
✅ **Persistent Transaction IDs**: UUID tracking across all requests  
✅ **JSON Only**: All data structures use JSON format  
✅ **Kebab Case URLs**: All routes follow kebab-case convention  
✅ **Open-Ended Data**: Flexible additional-data fields  
✅ **Deferred Response Support**: Async processing capabilities  
✅ **Status Tracking**: Complete status lifecycle support
