"""
Test examples for Broker-Dealer API endpoints
"""

# Example transaction ID (UUID v4)
TRANSACTION_ID = "123e4567-e89b-12d3-a456-426614174000"

# Example Policy Inquiry Request
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

# Example Policy Inquiry Response
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
            }
        ]
    },
    "enums": {
        "accountType": ["individual", "joint", "trust", "custodial", "entity"],
        "planType": ["nonQualified", "rothIra", "traditionalIra", "sep", "simple"]
    }
}

# Example BD Change Request
BD_CHANGE_REQUEST = {
    "transaction-id": TRANSACTION_ID,
    "receiving-broker-id": "BROKER-001",
    "delivering-broker-id": "BROKER-002",
    "carrier-id": "CARRIER-PL",
    "policy-id": "POL-001",
    "policy-details": {
        "policyNumber": "POL-001",
        "accountType": "individual",
        "planType": "nonQualified"
    },
    "broker-details": {
        "agentName": "John Smith",
        "npn": "12345678"
    },
    "request-timestamp": "2026-02-24T10:00:00Z"
}

# Example Transfer Notification
TRANSFER_NOTIFICATION = {
    "transaction-id": TRANSACTION_ID,
    "notification-type": "transfer-approved",
    "policy-id": "POL-001",
    "receiving-broker-id": "BROKER-001",
    "delivering-broker-id": "BROKER-002",
    "carrier-id": "CARRIER-PL",
    "notification-timestamp": "2026-02-24T11:00:00Z",
    "additional-data": {
        "approval-code": "APR-12345"
    }
}

# Example headers
HEADERS = {
    "Content-Type": "application/json",
    "transactionId": TRANSACTION_ID
}

if __name__ == "__main__":
    import json

    print("Example Policy Inquiry Request:")
    print(json.dumps(POLICY_INQUIRY_REQUEST, indent=2))
    print("\n" + "=" * 50 + "\n")

    print("Example BD Change Request:")
    print(json.dumps(BD_CHANGE_REQUEST, indent=2))
    print("\n" + "=" * 50 + "\n")

    print("Example Transfer Notification:")
    print(json.dumps(TRANSFER_NOTIFICATION, indent=2))
