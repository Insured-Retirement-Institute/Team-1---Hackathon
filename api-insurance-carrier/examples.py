"""
Test examples for Insurance Carrier API endpoints
"""

# Example transaction ID (UUID v4)
TRANSACTION_ID = "123e4567-e89b-12d3-a456-426614174000"

# Example BD Change Validation Request (from clearinghouse)
BD_CHANGE_REQUEST = {
    "receivingBrokerId": "BROKER-001",
    "deliveringBrokerId": "BROKER-002",
    "carrierId": "CARRIER-PL",
    "policyNumber": "POL-001",
    "policyDetails": {
        "accountType": "individual",
        "planType": "nonQualified",
        "productName": "Pacific Select Variable Annuity",
        "cusip": "123456789",
        "policyValue": "$125,000.00",
        "issueDate": "2020-05-15"
    },
    "brokerDetails": {
        "firmName": "Acme Financial Services",
        "firmId": "DTCC-12345",
        "agentName": "John Smith",
        "npn": "12345678",
        "licenseState": "CA",
        "licenseNumber": "0A12345",
        "email": "jsmith@acmefinancial.com",
        "phone": "555-123-4567"
    },
    "validationRequirements": {
        "licensing": True,
        "appointments": True,
        "suitability": True,
        "backgroundCheck": False
    },
    "requestTimestamp": "2026-02-24T10:30:00Z",
    "additionalData": {
        "priority": "normal",
        "requestSource": "clearinghouse"
    }
}

# Example Transfer Notification (from clearinghouse)
TRANSFER_NOTIFICATION = {
    "notificationType": "service-agent-change-complete",
    "policyNumber": "POL-001",
    "carrierId": "CARRIER-PL",
    "receivingBrokerId": "BROKER-001",
    "deliveringBrokerId": "BROKER-002",
    "effectiveDate": "2026-03-01",
    "notificationTimestamp": "2026-02-25T15:30:00Z",
    "additionalData": {
        "newAgentName": "John Smith",
        "newAgentNpn": "12345678",
        "previousAgentName": "Jane Doe",
        "previousAgentNpn": "87654321",
        "transferType": "broker-dealer-change",
        "confirmationNumber": "CONF-12345"
    }
}

# Example headers
HEADERS = {
    "Content-Type": "application/json",
    "transactionId": TRANSACTION_ID
}

# Example Carrier Response - Approved (to be sent to clearinghouse)
CARRIER_RESPONSE_APPROVED = {
    "transaction-id": TRANSACTION_ID,
    "carrier-id": "CARRIER-PL",
    "policy-id": "POL-001",
    "validation-result": "approved",
    "validation-details": {
        "licensingCheck": "passed",
        "appointmentCheck": "passed",
        "suitabilityCheck": "passed",
        "policyRulesCheck": "passed",
        "validatedBy": "System Automated Validation",
        "validationTimestamp": "2026-02-24T11:00:00Z"
    },
    "approval-details": {
        "approvalCode": "APR-12345",
        "effectiveDate": "2026-03-01",
        "notes": "All validation checks passed successfully"
    },
    "response-timestamp": "2026-02-24T11:00:00Z",
    "additional-data": {
        "commissionStructure": "standard",
        "trailingCommissionRate": "0.25%"
    }
}

# Example Carrier Response - Rejected (to be sent to clearinghouse)
CARRIER_RESPONSE_REJECTED = {
    "transaction-id": TRANSACTION_ID,
    "carrier-id": "CARRIER-PL",
    "policy-id": "POL-001",
    "validation-result": "rejected",
    "rejection-reason": "Agent not appointed with Pacific Life",
    "validation-details": {
        "licensingCheck": "passed",
        "appointmentCheck": "failed",
        "suitabilityCheck": "not-checked",
        "policyRulesCheck": "not-checked",
        "validatedBy": "System Automated Validation",
        "validationTimestamp": "2026-02-24T11:00:00Z"
    },
    "response-timestamp": "2026-02-24T11:00:00Z",
    "additional-data": {
        "rejectionCode": "REJ-001",
        "requiredAction": "Agent must complete appointment process"
    }
}

# Example API Response - Deferred Processing
CARRIER_API_RESPONSE_DEFERRED = {
    "code": "RECEIVED",
    "message": "BD change validation request received and queued for processing",
    "processingStatus": "deferred",
    "estimatedResponseTime": "Within 24 hours"
}

# Example API Response - Immediate Processing
CARRIER_API_RESPONSE_IMMEDIATE = {
    "code": "APPROVED",
    "message": "BD change request validated and approved",
    "processingStatus": "processing"
}

# Example Transaction Status Query Response
TRANSACTION_STATUS = {
    "currentStatus": "CARRIER_APPROVED",
    "createdAt": "2026-02-24T10:30:00Z",
    "updatedAt": "2026-02-24T11:00:00Z",
    "statusHistory": [
        {
            "status": "CARRIER_VALIDATION_PENDING",
            "timestamp": "2026-02-24T10:30:00Z",
            "notes": "BD change validation request received from clearinghouse"
        },
        {
            "status": "CARRIER_APPROVED",
            "timestamp": "2026-02-24T11:00:00Z",
            "notes": "All validation checks passed - approved"
        }
    ],
    "carrierValidationDetails": {
        "licensingCheck": "passed",
        "appointmentCheck": "passed",
        "suitabilityCheck": "passed",
        "policyRulesCheck": "passed",
        "validatedBy": "System Automated Validation",
        "validationTimestamp": "2026-02-24T11:00:00Z"
    },
    "policiesAffected": ["POL-001"],
    "additionalData": {
        "carrier": "CARRIER-PL",
        "policyNumber": "POL-001",
        "newBroker": "BROKER-001",
        "previousBroker": "BROKER-002",
        "approvalCode": "APR-12345"
    }
}

if __name__ == "__main__":
    import json

    print("Example BD Change Validation Request:")
    print(json.dumps(BD_CHANGE_REQUEST, indent=2))
    print("\n" + "=" * 50 + "\n")

    print("Example Transfer Notification:")
    print(json.dumps(TRANSFER_NOTIFICATION, indent=2))
    print("\n" + "=" * 50 + "\n")

    print("Example Carrier Response (Approved) - Sent to Clearinghouse:")
    print(json.dumps(CARRIER_RESPONSE_APPROVED, indent=2))
    print("\n" + "=" * 50 + "\n")

    print("Example Carrier Response (Rejected) - Sent to Clearinghouse:")
    print(json.dumps(CARRIER_RESPONSE_REJECTED, indent=2))
    print("\n" + "=" * 50 + "\n")

    print("Example Transaction Status:")
    print(json.dumps(TRANSACTION_STATUS, indent=2))
