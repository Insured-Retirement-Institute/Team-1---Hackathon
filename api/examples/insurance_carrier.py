"""
Example payloads for the Insurance Carrier API endpoints.

Two endpoint paths accept BD change validation requests — both dispatch to
the same AgentCore carrier agent:

  POST /api/insurance-carriers/receive-bd-change-request  (insurance-carrier-api.yaml)
  POST /api/insurance-carriers/bd-change                  (unified-brokerage-transfer-api.yaml)

Required header for all POST requests:
  requestId: <UUID>

The AgentCore carrier agent:
  1. Looks up each policy in the carrier DynamoDB table.
  2. Evaluates all 9 business rules.
  3. Returns a carrier_determination JSON payload (IGO or NIGO) synchronously.
"""

import uuid

REQUEST_ID = str(uuid.uuid4())

# ── Carrier BD Change Request — IGO scenario ──────────────────────────────────
# Policy ATH-100053 exists in the carrier DynamoDB table (owner SSN 434558122).
# Receiving agent NPN 99887766 is licensed in TX (the policy state) — RULE-008 passes.
# All other rules also pass → IGO determination expected.
BD_CHANGE_REQUEST_IGO = {
    # BdChangeRequest required fields (per insurance-carrier-api.yaml)
    "receivingBrokerId": "BD-001",
    "deliveringBrokerId": "BD-PREV",
    "carrierId": "ATH",
    "policyNumber": "ATH-100053",

    # Client information (used for SSN ownership check)
    "clientSSN": "434558122",
    "clientName": "Mark Jones",

    # Receiving agent validation fields (inside brokerDetails per spec)
    "brokerDetails": {
        "npn": "99887766",
        "agentName": "Sarah New-Agent",
        "firmName": "Premier Financial Services",
        "agentStatus": "ACTIVE",
        "carrierAppointed": True,
        "eoInPlace": True,
        "licensedStates": ["TX", "CA", "NY"]
    },

    # Signature validation fields
    "clientSigned": True,
    "bdAuthorizedSigned": True,
    "signatureDate": "2026-02-20",
    "submissionDate": "2026-02-25",

    # Broker-dealer status
    "brokerStatus": "ACTIVE",
    "contractedWithCarrier": True,

    # Optional metadata
    "requestTimestamp": "2026-02-25T10:30:00Z"
}

# ── Carrier BD Change Request — NIGO scenario ─────────────────────────────────
# Multiple rule failures deliberately injected:
#   RULE-001: clientSigned = False
#   RULE-002: bdAuthorizedSigned = False
#   RULE-003: signatureDate is > 90 days before submissionDate
#   RULE-005: agentStatus is SUSPENDED (not ACTIVE)
#   RULE-006: carrierAppointed = False
#   RULE-007: eoInPlace = False
#   RULE-008: licensedStates does not include TX (policy state)
BD_CHANGE_REQUEST_NIGO = {
    "receivingBrokerId": "BD-BAD",
    "deliveringBrokerId": "BD-PREV",
    "carrierId": "ATH",
    "policyNumber": "ATH-100053",

    "clientSSN": "434558122",
    "clientName": "Mark Jones",

    "brokerDetails": {
        "npn": "11223344",
        "agentName": "Bad Actor Agent",
        "firmName": "Shady Brokerage LLC",
        "agentStatus": "SUSPENDED",
        "carrierAppointed": False,
        "eoInPlace": False,
        "licensedStates": ["CA"]          # TX is missing — policy state is TX
    },

    "clientSigned": False,
    "bdAuthorizedSigned": False,
    "signatureDate": "2025-10-01",        # > 90 days before submissionDate
    "submissionDate": "2026-02-25",

    "brokerStatus": "ACTIVE",
    "contractedWithCarrier": True,

    "requestTimestamp": "2026-02-25T10:30:00Z"
}

# ── Expected IGO API response (abbreviated) ───────────────────────────────────
API_RESPONSE_IGO = {
    "code": "APPROVED",
    "message": "Servicing agent change approved — all business rules passed",
    "requestId": REQUEST_ID,
    "processingMode": "immediate",
    "payload": {
        "request-id": "...",
        "determination": "IGO",
        "ruleset-version": "1.0.0",
        "evaluated-at": "2026-02-25T...",
        "policies-evaluated": [
            {
                "policy-number": "ATH-100053",
                "client-name": "Mark Jones",
                "account-type": "Indexed Annuity",
                "product-name": "Athene MYG 5 MVA",
                "policy-status": "Active",
                "state": "TX",
                "current-agents": [{"npn": "20672400", "name": "Nicole Nelson"}]
            }
        ],
        "rule-results": [
            {"rule-id": "RULE-001", "name": "Client Signature", "passed": True, "severity": "hard_stop"},
            {"rule-id": "RULE-002", "name": "BD Authorization Signature", "passed": True, "severity": "hard_stop"},
            {"rule-id": "RULE-003", "name": "Signature Recency (≤90 days)", "passed": True, "severity": "hard_stop"},
            {"rule-id": "RULE-004", "name": "Producer Identity Change", "passed": True, "severity": "hard_stop"},
            {"rule-id": "RULE-005", "name": "Producer Active Status", "passed": True, "severity": "hard_stop"},
            {"rule-id": "RULE-006", "name": "Carrier Appointment", "passed": True, "severity": "hard_stop"},
            {"rule-id": "RULE-007", "name": "E&O Coverage", "passed": True, "severity": "hard_stop"},
            {"rule-id": "RULE-008", "name": "State Licensing", "passed": True, "severity": "hard_stop"},
            {"rule-id": "RULE-009", "name": "Broker-Dealer Contract Status", "passed": True, "severity": "hard_stop"},
        ],
        "deficiencies": [],
        "corrective-actions": [],
        "summary": "All 9 rules passed. Request is In Good Order and approved for processing."
    }
}

# ── Expected NIGO API response (abbreviated) ──────────────────────────────────
API_RESPONSE_NIGO = {
    "code": "REJECTED",
    "message": "Servicing agent change rejected — 7 of 9 rules failed",
    "requestId": REQUEST_ID,
    "processingMode": "immediate",
    "payload": {
        "request-id": "...",
        "determination": "NIGO",
        "deficiencies": [
            {"nigo-code": "NIGO-001", "rule-id": "RULE-001", "message": "Client signature missing"},
            {"nigo-code": "NIGO-002", "rule-id": "RULE-002", "message": "BD authorization signature missing"},
            {"nigo-code": "NIGO-003", "rule-id": "RULE-003", "message": "Signatures are older than 90 days"},
            {"nigo-code": "NIGO-005", "rule-id": "RULE-005", "message": "Receiving agent status is SUSPENDED"},
            {"nigo-code": "NIGO-006", "rule-id": "RULE-006", "message": "Receiving agent not appointed with carrier"},
            {"nigo-code": "NIGO-007", "rule-id": "RULE-007", "message": "Receiving agent has no E&O coverage on file"},
            {"nigo-code": "NIGO-008", "rule-id": "RULE-008", "message": "Receiving agent not licensed in TX"},
        ],
        "corrective-actions": [
            "Obtain client signature on the change request form",
            "Obtain BD home-office authorized signature",
            "Re-execute all signatures within the last 90 days",
            "Activate or replace the receiving agent (currently SUSPENDED)",
            "Complete carrier appointment process for the receiving agent",
            "Provide a current E&O certificate to the carrier",
            "Obtain a TX insurance license for the receiving agent",
        ],
        "summary": "7 of 9 hard-stop rules failed. Request is Not In Good Order."
    }
}

# ── Transfer notification (sent AFTER an approved change has been processed) ──
TRANSFER_NOTIFICATION = {
    "notificationType": "service-agent-change-complete",
    "policyNumber": "ATH-100053",
    "carrierId": "ATH",
    "receivingBrokerId": "BD-001",
    "deliveringBrokerId": "BD-PREV",
    "effectiveDate": "2026-03-01",
    "notificationTimestamp": "2026-02-25T15:30:00Z",
    "additionalData": {
        "newAgentName": "Sarah New-Agent",
        "newAgentNpn": "99887766",
        "previousAgentName": "Nicole Nelson",
        "previousAgentNpn": "20672400",
    }
}

# ── Request headers ───────────────────────────────────────────────────────────
HEADERS = {
    "Content-Type": "application/json",
    "requestId": REQUEST_ID
}

if __name__ == "__main__":
    import json

    print("=== IGO BD Change Request ===")
    print(json.dumps(BD_CHANGE_REQUEST_IGO, indent=2))

    print("\n=== NIGO BD Change Request ===")
    print(json.dumps(BD_CHANGE_REQUEST_NIGO, indent=2))

    print("\n=== Transfer Notification ===")
    print(json.dumps(TRANSFER_NOTIFICATION, indent=2))
