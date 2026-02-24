"""
Test examples for Clearinghouse API endpoints
"""

# Example transaction ID (UUID v4)
TRANSACTION_ID = "123e4567-e89b-12d3-a456-426614174000"

# Example Policy Inquiry Request (from receiving broker)
POLICY_INQUIRY_REQUEST = {
    "requestingFirm": {
        "firmName": "Acme Financial Services",
        "firmId": "DTCC-12345",
        "servicingAgent": {
            "agentName": "John Smith",
            "npn": "12345678"
        }
    },
    "client": {
        "clientName": "Jane Doe",
        "ssn": "123-45-6789",
        "policyNumbers": ["POL-001", "POL-002", "POL-003"]
    }
}

# Example Policy Inquiry Response (from delivering broker)
POLICY_INQUIRY_RESPONSE = {
    "requestingFirm": {
        "firmName": "Acme Financial Services",
        "firmId": "DTCC-12345",
        "servicingAgent": {
            "agentName": "John Smith",
            "npn": "12345678"
        }
    },
    "producerValidation": {
        "agentName": "John Smith",
        "npn": "12345678",
        "errors": []
    },
    "client": {
        "clientName": "Jane Doe",
        "ssnLast4": "6789",
        "policies": [
            {
                "policyNumber": "POL-001",
                "carrierName": "Pacific Life",
                "accountType": "individual",
                "planType": "nonQualified",
                "ownership": "Individual",
                "productName": "Pacific Select Variable Annuity",
                "cusip": "123456789",
                "trailingCommission": True,
                "contractStatus": "Active",
                "withdrawalStructure": {
                    "systematicInPlace": False
                },
                "errors": []
            },
            {
                "policyNumber": "POL-002",
                "carrierName": "Pacific Life",
                "accountType": "joint",
                "planType": "nonQualified",
                "ownership": "Joint",
                "productName": "Pacific Odyssey Variable Annuity",
                "cusip": "987654321",
                "trailingCommission": True,
                "contractStatus": "Active",
                "withdrawalStructure": {
                    "systematicInPlace": True
                },
                "errors": []
            }
        ]
    },
    "enums": {
        "accountType": ["individual", "joint", "trust", "custodial", "entity"],
        "planType": ["nonQualified", "rothIra", "traditionalIra", "sep", "simple"]
    }
}

# Example BD Change Request (from receiving broker)
BD_CHANGE_REQUEST = {
    "transaction-id": TRANSACTION_ID,
    "receiving-broker-id": "BROKER-001",
    "delivering-broker-id": "BROKER-002",
    "carrier-id": "CARRIER-PL",
    "policy-id": "POL-001",
    "policy-details": {
        "policyNumber": "POL-001",
        "accountType": "individual",
        "planType": "nonQualified",
        "productName": "Pacific Select Variable Annuity"
    },
    "broker-details": {
        "firmName": "Acme Financial Services",
        "firmId": "DTCC-12345",
        "agentName": "John Smith",
        "npn": "12345678"
    },
    "validation-requirements": {
        "licensing": True,
        "appointments": True,
        "suitability": True
    },
    "request-timestamp": "2026-02-24T10:00:00Z"
}

# Example Carrier Response (from insurance carrier)
CARRIER_RESPONSE_APPROVED = {
    "transaction-id": TRANSACTION_ID,
    "carrier-id": "CARRIER-PL",
    "policy-id": "POL-001",
    "validation-result": "approved",
    "additional-data": {
        "approval-code": "APR-12345",
        "effective-date": "2026-03-01T00:00:00Z"
    }
}

CARRIER_RESPONSE_REJECTED = {
    "transaction-id": TRANSACTION_ID,
    "carrier-id": "CARRIER-PL",
    "policy-id": "POL-001",
    "validation-result": "rejected",
    "rejection-reason": "Agent not appointed with carrier",
    "additional-data": {
        "rejection-code": "REJ-001"
    }
}

# Example Transfer Confirmation (from delivering broker)
TRANSFER_CONFIRMATION = {
    "transaction-id": TRANSACTION_ID,
    "delivering-broker-id": "BROKER-002",
    "policy-id": "POL-001",
    "confirmation-status": "confirmed",
    "additional-data": {
        "completion-date": "2026-02-25T15:30:00Z",
        "final-value": "$125,000.00"
    }
}

TRANSFER_CONFIRMATION_FAILED = {
    "transaction-id": TRANSACTION_ID,
    "delivering-broker-id": "BROKER-002",
    "policy-id": "POL-001",
    "confirmation-status": "failed",
    "additional-data": {
        "failure-reason": "System error during transfer",
        "retry-required": True
    }
}

# Example headers
HEADERS = {
    "Content-Type": "application/json",
    "transactionId": TRANSACTION_ID
}

# Example Clearinghouse Response (deferred)
CLEARINGHOUSE_RESPONSE = {
    "code": "RECEIVED",
    "message": "Policy inquiry request received and routed to delivering broker",
    "transactionId": TRANSACTION_ID,
    "payload": None  # Always None for clearinghouse responses
}

if __name__ == "__main__":
    import json

    print("Example Policy Inquiry Request:")
    print(json.dumps(POLICY_INQUIRY_REQUEST, indent=2))
    print("\n" + "=" * 50 + "\n")

    print("Example Policy Inquiry Response:")
    print(json.dumps(POLICY_INQUIRY_RESPONSE, indent=2))
    print("\n" + "=" * 50 + "\n")

    print("Example BD Change Request:")
    print(json.dumps(BD_CHANGE_REQUEST, indent=2))
    print("\n" + "=" * 50 + "\n")

    print("Example Carrier Response (Approved):")
    print(json.dumps(CARRIER_RESPONSE_APPROVED, indent=2))
    print("\n" + "=" * 50 + "\n")

    print("Example Transfer Confirmation:")
    print(json.dumps(TRANSFER_CONFIRMATION, indent=2))
    print("\n" + "=" * 50 + "\n")

    print("Example Clearinghouse Response:")
    print(json.dumps(CLEARINGHOUSE_RESPONSE, indent=2))
