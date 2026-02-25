# Unified Brokerage Transfer API Summary

## Overview

This document summarizes the consolidation of three separate API specifications into a single unified specification that any entity can implement.

## Consolidated Specifications

The following specifications have been consolidated into `unified-brokerage-transfer-api.yaml`:

- `clearinghouse-api.yaml` - DTCC clearinghouse endpoints
- `broker-dealer-api.yaml` - Broker-dealer endpoints  
- `insurance-carrier-api.yaml` - Insurance carrier endpoints

## Key Features of the Unified API

### 1. Universal Implementation
- **Single Profile**: All entities (clearinghouse, broker-dealer, carrier) implement the same endpoint set
- **Role Agnostic**: Entity behavior determined by implementation, not separate specifications
- **Flexible Routing**: Receiving entity determines routing rather than caller

### 2. Direct Entity Communication
- Partners can communicate directly with any entity
- Policy-to-entity mapping enables targeted requests
- Fallback to traditional clearinghouse routing when needed

### 3. Enhanced Capability Management
- **NEW**: `NOT_CAPABLE` response code (HTTP 422)
- **NEW**: `CapabilityResponse` schema with detailed capability information
- Graceful degradation when entities cannot fulfill requests

### 4. Maintained Response Patterns
- Immediate/deferred responses preserved for all operations except status queries
- Transaction ID consistency across all routing patterns
- Compatible with existing workflow patterns

## Universal Endpoint Set

All entities now implement these endpoints:

| Endpoint | Purpose |
|----------|---------|
| `POST /submit-policy-inquiry-request` | Submit policy inquiry requests |
| `POST /submit-policy-inquiry-response` | Submit policy inquiry responses |
| `POST /receive-policy-inquiry-response` | Receive forwarded policy responses |
| `POST /receive-bd-change-request` | Receive brokerage dealer change requests |
| `POST /receive-carrier-response` | Receive carrier validation responses |
| `POST /receive-transfer-notification` | Receive transfer notifications |
| `POST /receive-transfer-confirmation` | Receive transfer confirmations |
| `GET /query-status/{transactionId}` | Query transaction status |

## Style Guide Compliance Assessment

### ✅ Compliant Elements

- Uses OpenAPI 3.1.0 as specified
- Implements semantic versioning (v1.0.0)
- Uses `policyNumber` consistently per data definitions
- Includes `correlationId` header support
- Uses `npn` correctly for National Producer Number

### ⚠️ Identified Discrepancies

The specification maintains existing data structures for backward compatibility but contains these Style Guide deviations:

#### 1. Response Body Structure Violation
**Issue**: Response bodies wrap resources in named objects
```yaml
# Current (Non-compliant)
PolicyInquiryRequest:
  type: object
  properties:
    requestingFirm: {...}
    client: {...}

# Should be (Style Guide compliant)
# Response body should BE the resource directly
```

**Impact**: Violates "response body should BE the resource" rule

#### 2. Boolean Field Naming
**Issues**:
- `trailingCommission` → Should be `hasTrailingCommission` or `isTrailingCommissionEnabled`
- `systematicInPlace` → Should be `hasSystematicWithdrawal` or `isSystematicWithdrawalActive`

**Style Guide Rule**: Booleans should be prefixed with `is` or `has`

#### 3. Business Entity Naming
**Issues**:
- `firmName` → Should be `name` per style guide for business entities
- `agentName` → Should use `producer` terminology per style guide preferences

#### 4. Field Naming Consistency
**Mixed Usage**:
- Correctly uses `policyNumber` in most places
- Some legacy references to `policy-id` or `policyId` in comments

## NEW Capability Response Schema

The unified API introduces comprehensive capability management:

```yaml
CapabilityResponse:
  properties:
    code: [NOT_CAPABLE]
    capabilityStatus: [not_supported, temporarily_unavailable, insufficient_data, policy_restriction, system_limitation]
    capabilityLevel: [none, partial, conditional]
    supportedAlternatives: [array of alternative approaches]
    retryAfter: [when capability might be available]
```

## Routing Philosophy Changes

### Before (Role-Specific)
- Separate APIs for each entity type
- Fixed routing patterns
- Caller determines target entity type

### After (Universal)
- Single API implemented by all entities
- Flexible routing determined by receiving entity
- Direct entity communication enabled
- Graceful fallback with capability responses

## Implementation Benefits

1. **Simplified Integration**: Single specification to implement regardless of entity type
2. **Direct Communication**: Bypass clearinghouse when policy-to-carrier mapping is known
3. **Graceful Degradation**: NOT_CAPABLE responses enable fallback routing
4. **Performance Optimization**: Direct entity calls reduce latency
5. **Backward Compatibility**: Maintains existing data structures and workflows

## Migration Considerations

- **Existing Implementations**: Can continue using role-specific patterns
- **New Implementations**: Can leverage universal endpoints and direct communication
- **Data Structures**: No breaking changes to existing schemas
- **Transaction IDs**: Continue to flow consistently across all patterns

## Usage Examples

### Direct Carrier Access
```bash
# Broker can call carrier directly when policy mapping is known
POST https://api.pacificlife.com/v1/submit-policy-inquiry-request
Headers:
  transactionId: 123e4567-e89b-12d3-a456-426614174000
  correlationId: REQ-2024-001
```

### Capability-Aware Routing
```bash
# If carrier responds with NOT_CAPABLE, broker can fallback to clearinghouse
POST https://api.clearinghouse.com/v1/submit-policy-inquiry-request
Headers:
  transactionId: 123e4567-e89b-12d3-a456-426614174000
```

## File Status

- ✅ **Created**: `unified-brokerage-transfer-api.yaml` - Complete unified specification
- ✅ **Preserved**: All original specification files remain in place
- ✅ **Documented**: Style guide discrepancies identified and documented inline
- ✅ **Enhanced**: NEW capability management system added

The unified specification supersedes the individual role-specific APIs while maintaining full backward compatibility and enabling new direct communication patterns.
