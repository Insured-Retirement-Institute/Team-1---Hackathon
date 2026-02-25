# Carrier Servicing Agent Change Validator — Technical Documentation

**Status:** Deployed and live
**Last verified:** 2026-02-25
**PR:** [#3 — feature/carrier-agent-agentcore-dispatch](https://github.com/Insured-Retirement-Institute/Team-1---Hackathon/pull/3)

---

## What It Does

This agent is the carrier's automated back-end validator for annuity servicing agent (producer) change requests. When a broker-dealer or clearinghouse submits a request to change the servicing agent on an existing annuity policy, this agent:

1. **Looks up the policy** from the carrier's DynamoDB table using the contract number
2. **Evaluates 9 business rules** — covering signatures, producer eligibility, licensing, and broker-dealer contracts
3. **Returns a structured IGO/NIGO determination** — In Good Order (approved) or Not In Good Order (rejected with deficiency codes and corrective actions)

The agent runs synchronously. The calling Lambda API receives the full determination in one HTTP response — no polling required.

---

## Architecture

```
Broker-Dealer / Clearinghouse
        │
        │ POST /api/insurance-carriers/receive-bd-change-request
        │      or
        │ POST /api/insurance-carriers/bd-change
        │
        ▼
  AWS Lambda (Flask)
  api/routes/insurance_carrier.py
        │
        │  Maps BdChangeRequest → carrier agent payload
        │  SigV4-signed POST to AgentCore data plane
        │
        ▼
  Amazon Bedrock AgentCore Runtime
  iri_producer_change_agent
  ARN: arn:aws:bedrock-agentcore:us-east-1:762233730742:runtime/iri_producer_change_agent-nLtgj9FbJl
        │
        │  7 tools (Strands @tool decorated functions)
        │  Model: claude-sonnet-4-5 via Bedrock
        │
        ├─► DynamoDB: carrier table  (lookup_policy, lookup_policies_for_client)
        ├─► validate_signatures()
        ├─► check_producer_identity()
        ├─► check_producer_eligibility()
        ├─► check_producer_licensing()
        ├─► check_bd_contract()
        └─► get_active_ruleset()
        │
        ▼
  JSON determination  →  Lambda wraps in StandardResponse  →  caller
```

---

## API Endpoints

Both endpoints accept the same `BdChangeRequest` payload and return the same response. They differ only in URL — one per each API spec.

| Endpoint | Spec |
|---|---|
| `POST /api/insurance-carriers/receive-bd-change-request` | `insurance-carrier-api.yaml` |
| `POST /api/insurance-carriers/bd-change` | `unified-brokerage-transfer-api.yaml` |

### Required Header

```
transactionId: <UUID>
```

### Request Body (`BdChangeRequest`)

**Spec-required fields** (validated, 400 if missing):

| Field | Type | Description |
|---|---|---|
| `receivingBrokerId` | string | Receiving broker-dealer identifier |
| `deliveringBrokerId` | string | Delivering (outgoing) broker-dealer identifier |
| `carrierId` | string | Carrier code (`ATH`, `PAC`, …) |
| `policyNumber` | string | Contract number (e.g. `ATH-100053`) |

**Carrier validation fields** (passed in `brokerDetails` and top-level):

| Field | Location | Type | Description |
|---|---|---|---|
| `brokerDetails.npn` | body | string | Receiving agent's National Producer Number |
| `brokerDetails.agentName` | body | string | Receiving agent's full name |
| `brokerDetails.agentStatus` | body | string | `ACTIVE` \| `SUSPENDED` \| `TERMINATED` \| `INACTIVE` |
| `brokerDetails.carrierAppointed` | body | boolean | Agent holds active carrier appointment |
| `brokerDetails.eoInPlace` | body | boolean | Agent has current E&O certificate on file |
| `brokerDetails.licensedStates` | body | string[] | State codes where agent is licensed |
| `clientSSN` | body | string | Policy owner's SSN (for ownership verification) |
| `clientSigned` | body | boolean | Owner signed the change request form |
| `bdAuthorizedSigned` | body | boolean | BD home-office signed the form |
| `signatureDate` | body | string | Date signatures obtained (`YYYY-MM-DD`) |
| `submissionDate` | body | string | Date request submitted (`YYYY-MM-DD`) |
| `brokerStatus` | body | string | Receiving BD status (`ACTIVE` \| …) |
| `contractedWithCarrier` | body | boolean | BD has active selling agreement |

### Example Request (IGO scenario)

```json
POST /api/insurance-carriers/receive-bd-change-request
transactionId: 550e8400-e29b-41d4-a716-446655440000

{
  "receivingBrokerId":   "BD-001",
  "deliveringBrokerId":  "BD-PREV",
  "carrierId":           "ATH",
  "policyNumber":        "ATH-100053",
  "clientSSN":           "434558122",
  "clientName":          "Mark Jones",
  "brokerDetails": {
    "npn":               "99887766",
    "agentName":         "Sarah New-Agent",
    "firmName":          "Premier Financial Services",
    "agentStatus":       "ACTIVE",
    "carrierAppointed":  true,
    "eoInPlace":         true,
    "licensedStates":    ["TX", "CA", "NY"]
  },
  "clientSigned":        true,
  "bdAuthorizedSigned":  true,
  "signatureDate":       "2026-02-20",
  "submissionDate":      "2026-02-25",
  "brokerStatus":        "ACTIVE",
  "contractedWithCarrier": true
}
```

### Example Response (IGO — APPROVED)

```json
{
  "code": "APPROVED",
  "message": "Servicing agent change approved — all business rules passed",
  "transactionId": "550e8400-e29b-41d4-a716-446655440000",
  "processingMode": "immediate",
  "payload": {
    "request-id": "550e8400-e29b-41d4-a716-446655440000",
    "determination": "IGO",
    "ruleset-version": "1.0.0",
    "evaluated-at": "2026-02-25T00:00:00Z",
    "policies-evaluated": [
      {
        "policy-number": "ATH-100053",
        "client-name": "Joshua Lee",
        "account-type": "Indexed Annuity",
        "product-name": "Athene MYG 5 MVA",
        "policy-status": "Active",
        "plan-type": "Roth IRA",
        "state": "TX",
        "current-agents": [{"npn": "27530463", "name": "Amanda Foster"}]
      }
    ],
    "rule-results": [
      {"rule-id": "RULE-001", "name": "Client Signature Required",              "passed": true, "severity": "hard_stop"},
      {"rule-id": "RULE-002", "name": "BD Authorized Signature Required",        "passed": true, "severity": "hard_stop"},
      {"rule-id": "RULE-003", "name": "Signature Timeliness (90-Day Window)",    "passed": true, "severity": "hard_stop"},
      {"rule-id": "RULE-004", "name": "Producer Change Must Be a Different Individual", "passed": true, "severity": "hard_stop"},
      {"rule-id": "RULE-005", "name": "Incoming Producer Active Status",         "passed": true, "severity": "hard_stop"},
      {"rule-id": "RULE-006", "name": "Carrier Appointment Required",            "passed": true, "severity": "hard_stop"},
      {"rule-id": "RULE-007", "name": "E&O Coverage Required",                   "passed": true, "severity": "hard_stop"},
      {"rule-id": "RULE-008", "name": "Producer State Licensing",                "passed": true, "severity": "hard_stop"},
      {"rule-id": "RULE-009", "name": "BD Active Carrier Contract",              "passed": true, "severity": "hard_stop"}
    ],
    "deficiencies": [],
    "corrective-actions": [],
    "summary": "All 9 rules passed. Request is In Good Order and approved for processing."
  }
}
```

### Example Response (NIGO — REJECTED)

```json
{
  "code": "REJECTED",
  "message": "Servicing agent change rejected — 7 of 9 hard-stop rules failed",
  "transactionId": "550e8400-e29b-41d4-a716-446655440000",
  "processingMode": "immediate",
  "payload": {
    "determination": "NIGO",
    "deficiencies": [
      {"nigo-code": "NIGO-001", "rule-id": "RULE-001", "message": "Client signature missing"},
      {"nigo-code": "NIGO-002", "rule-id": "RULE-002", "message": "BD authorization signature missing"},
      {"nigo-code": "NIGO-003", "rule-id": "RULE-003", "message": "Signatures are 147 days old"},
      {"nigo-code": "NIGO-005", "rule-id": "RULE-005", "message": "Receiving agent status is SUSPENDED"},
      {"nigo-code": "NIGO-006", "rule-id": "RULE-006", "message": "Receiving agent not appointed with carrier"},
      {"nigo-code": "NIGO-007", "rule-id": "RULE-007", "message": "Receiving agent has no E&O coverage on file"},
      {"nigo-code": "NIGO-008", "rule-id": "RULE-008", "message": "Not licensed in: TX"}
    ],
    "corrective-actions": [
      "Obtain client signature on the change request form",
      "Obtain BD home-office authorized signature",
      "Re-execute all signatures within the last 90 days",
      "Activate or replace the receiving agent (currently SUSPENDED)",
      "Complete carrier appointment process for the receiving agent",
      "Provide a current E&O certificate to the carrier",
      "Obtain a TX insurance license for the receiving agent"
    ],
    "summary": "7 of 9 hard-stop rules failed. Request is Not In Good Order."
  }
}
```

---

## Business Rules

All 9 rules are **hard stops** — any single failure produces a NIGO.

| Rule ID | Name | What Is Checked | NIGO Code |
|---|---|---|---|
| RULE-001 | Client Signature Required | `clientSigned == true` | NIGO-001 |
| RULE-002 | BD Authorized Signature Required | `bdAuthorizedSigned == true` | NIGO-002 |
| RULE-003 | Signature Timeliness (90-Day Window) | `submissionDate - signatureDate ≤ 90 days` | NIGO-003 |
| RULE-004 | Producer Change Must Be a Different Individual | Incoming NPN ≠ current servicing agent NPN (from DynamoDB) | NIGO-004 |
| RULE-005 | Incoming Producer Active Status | `agentStatus == "ACTIVE"` | NIGO-005 |
| RULE-006 | Carrier Appointment Required | `carrierAppointed == true` | NIGO-006 |
| RULE-007 | E&O Coverage Required | `eoInPlace == true` | NIGO-007 |
| RULE-008 | Producer State Licensing | Agent licensed in every state where affected policies are issued | NIGO-008 |
| RULE-009 | BD Active Carrier Contract | `brokerStatus == "ACTIVE"` AND `contractedWithCarrier == true` | NIGO-009 |

---

## AgentCore Agent

### Identity

| Property | Value |
|---|---|
| Name | `iri_producer_change_agent` |
| ARN | `arn:aws:bedrock-agentcore:us-east-1:762233730742:runtime/iri_producer_change_agent-nLtgj9FbJl` |
| Region | `us-east-1` |
| Model | `claude-sonnet-4-5` via Amazon Bedrock |
| Framework | [Strands Agents](https://strandsagents.com) |
| Entry point | `src/runtime_agent.py` |

### Payload Format Sent to AgentCore

The Lambda maps the flat `BdChangeRequest` into a structured carrier agent payload before invocation:

```json
{
  "request-id":      "<UUID>",
  "submission-date": "YYYY-MM-DD",
  "client": {
    "ssn":             "434558122",
    "client-name":     "Mark Jones",
    "contract-numbers": ["ATH-100053"]
  },
  "receiving-agent": {
    "npn":              "99887766",
    "agent-name":       "Sarah New-Agent",
    "status":           "ACTIVE",
    "carrier-appointed": true,
    "e-o-coverage":     true,
    "licensed-states":  ["TX", "CA", "NY"]
  },
  "receiving-broker": {
    "broker-id":               "BD-001",
    "broker-name":             "Premier Financial Services",
    "status":                  "ACTIVE",
    "contracted-with-carrier": true
  },
  "signatures": {
    "client-signed":       true,
    "bd-authorized-signed": true,
    "signature-date":      "2026-02-20"
  }
}
```

### Field Mapping (BdChangeRequest → Agent Payload)

| BdChangeRequest field | Agent payload field |
|---|---|
| `policyNumber` | `client.contract-numbers[0]` |
| `clientSSN` | `client.ssn` |
| `clientName` | `client.client-name` |
| `receivingBrokerId` | `receiving-broker.broker-id` |
| `brokerStatus` | `receiving-broker.status` |
| `contractedWithCarrier` | `receiving-broker.contracted-with-carrier` |
| `brokerDetails.npn` | `receiving-agent.npn` |
| `brokerDetails.agentName` | `receiving-agent.agent-name` |
| `brokerDetails.agentStatus` | `receiving-agent.status` |
| `brokerDetails.carrierAppointed` | `receiving-agent.carrier-appointed` |
| `brokerDetails.eoInPlace` | `receiving-agent.e-o-coverage` |
| `brokerDetails.licensedStates` | `receiving-agent.licensed-states` |
| `clientSigned` | `signatures.client-signed` |
| `bdAuthorizedSigned` | `signatures.bd-authorized-signed` |
| `signatureDate` | `signatures.signature-date` |
| `submissionDate` | `submission-date` |

### How the Lambda Calls AgentCore

The Lambda uses `botocore.auth.SigV4Auth` with raw `urllib.request` rather than `boto3.client("bedrock-agentcore")`. This is intentional: the bedrock-agentcore service model may not be bundled in the Lambda runtime's botocore version, but botocore itself is always present.

```
POST https://bedrock-agentcore.us-east-1.amazonaws.com
     /runtimes/{url-encoded-ARN}/invocations?qualifier=DEFAULT
Content-Type: application/json
X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: <fresh UUID per request>
Authorization: AWS4-HMAC-SHA256 ... (SigV4)
```

The response may arrive as SSE (`data: {...}` lines) or plain JSON — both are handled.

### Agent Tools

| Tool | Purpose | Rules Evaluated |
|---|---|---|
| `lookup_policy(policy_number)` | Fetch policy by contract number from DynamoDB `carrier` table | — |
| `lookup_policies_for_client(ssn)` | Scan for all policies owned by an SSN | — |
| `validate_signatures(...)` | Check signature presence and recency | RULE-001, RULE-002, RULE-003 |
| `check_producer_identity(current_npn, incoming_npn)` | Verify agent change is a real change | RULE-004 |
| `check_producer_eligibility(status, appointed, eo)` | Check agent active status, appointment, E&O | RULE-005, RULE-006, RULE-007 |
| `check_producer_licensing(licensed_states, policy_states)` | Check state licensing against policy states from DynamoDB | RULE-008 |
| `check_bd_contract(bd_status, contracted)` | Check BD active status and selling agreement | RULE-009 |
| `get_active_ruleset()` | Return ruleset version and metadata | — |

### DynamoDB Table

| Property | Value |
|---|---|
| Table name | `carrier` |
| Region | `us-east-1` |
| Primary key | `pk` = `POLICY#{policy_number}`, `sk` = `POLICY#{policy_number}` |
| Key policy fields | `policyNumber`, `ownerSSN`, `clientName`, `accountType`, `productName`, `policyStatus`, `planType`, `state`, `servicingAgents[]` |

Carrier `ATH` (Athene) → `carrier` table
Carrier `PAC` (Pacific Life) → `carrier-2` table *(not yet populated)*

---

## Source Files

| File | Role |
|---|---|
| `src/carrier_agent.py` | Agent definition — tools, system prompt, `build_carrier_agent()` |
| `src/runtime_agent.py` | AgentCore entrypoint — routes `agent_type` to the right agent |
| `src/agent.py` | Original IGO/NIGO prototype agent (static data) — still available via `agent_type: "igo_nigo"` |
| `api/routes/insurance_carrier.py` | Flask blueprint — HTTP routes, BdChangeRequest validation, AgentCore dispatch |
| `api/app.py` | Flask app factory — dynamic blueprint registration with `URL_PREFIX` support |
| `api/examples/insurance_carrier.py` | Reference payloads for both IGO and NIGO scenarios |
| `data/business_rules.json` | Rule definitions — IDs, names, descriptions, NIGO codes, corrective actions |
| `schemas/rules.schema.json` | JSONSchema for `business_rules.json` |
| `specs/insurance-carrier-api.yaml` | OpenAPI spec for carrier-facing endpoints |
| `specs/unified-brokerage-transfer-api.yaml` | OpenAPI spec for the unified `/bd-change` endpoint |

---

## IAM Requirements

The Lambda execution role needs:

```json
{
  "Effect": "Allow",
  "Action": "bedrock-agentcore:InvokeAgentRuntime",
  "Resource": "arn:aws:bedrock-agentcore:us-east-1:762233730742:runtime/iri_producer_change_agent-nLtgj9FbJl"
}
```

The AgentCore agent's execution role needs:

```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:GetItem", "dynamodb:Scan"],
  "Resource": "arn:aws:dynamodb:us-east-1:762233730742:table/carrier"
}
```

---

## Known Limitations / TODO

- `receive-transfer-notification` handler acknowledges the notification but does **not** update DynamoDB — marked TODO
- `query-status` endpoint returns mock data — a real request-tracking table is needed
- `carrier-2` table for Pacific Life is not yet populated
- `validate_producer()` in the policy inquiry handler always returns valid — stub for demo
- Flask local startup fails if `lib/utils` is not on `PYTHONPATH` (works correctly in Lambda)
