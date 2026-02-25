o# Policy Inquiry API — Steps 1 & 2

## Overview

The Policy Inquiry is the first exchange in the BD Change Process for producer changes on existing annuities. The **Receiving Broker/Dealer** submits a request through DTCC to the **Delivering Broker/Dealer**, asking for details on specific contracts held by a client. This is a single-client-per-request operation.

The Receiving Firm provides minimal identifying information — client name, SSN, and policy numbers — and receives back enriched policy details for each contract.

---

## Step 1 — Policy Inquiry Request

Submitted by the Receiving Broker/Dealer to DTCC.

**DTCC Status:** `MANIFEST_REQUESTED`

### Payload

```json
{
  "policyInquiryRequest": {
    "requestingFirm": {
      "firmName": null,
      "firmId": null,
      "servicingAgent": {
        "agentName": null,
        "npn": null
      }
    },
    "client": {
      "clientName": null,
      "ssn": null,
      "policyNumbers": []
    }
  }
}
```

### Field Reference

| Field                                     | Type     | Description                               |
| ----------------------------------------- | -------- | ----------------------------------------- |
| `requestingFirm.firmName`                 | string   | Name of the receiving broker/dealer       |
| `requestingFirm.firmId`                   | string   | DTCC firm identifier                      |
| `requestingFirm.servicingAgent.agentName` | string   | Name of the new servicing agent           |
| `requestingFirm.servicingAgent.npn`       | string   | National Producer Number of the new agent |
| `client.clientName`                       | string   | Full name of the client                   |
| `client.ssn`                              | string   | Client's Social Security Number           |
| `client.policyNumbers`                    | string[] | List of policy numbers to inquire about   |

### Notes

- This is a **one client at a time** request.
- The delivering firm is not specified in the request — DTCC routes based on the policy numbers provided.
- The servicing agent information is included so the delivering firm and carrier are aware of the intended new agent from the outset.

---

## Step 2 — Policy Inquiry Response

Returned by the Delivering Broker/Dealer through DTCC to the Receiving Firm.

**DTCC Status:** `MANIFEST_RECEIVED`

### Payload

```json
{
  "policyInquiryResponse": {
    "requestingFirm": {
      "firmName": null,
      "firmId": null,
      "servicingAgent": {
        "agentName": null,
        "npn": null
      }
    },
    "producerValidation": {
      "agentName": null,
      "npn": null,
      "errors": []
    },
    "client": {
      "clientName": null,
      "ssnLast4": null,
      "policies": [
        {
          "policyNumber": null,
          "carrierName": null,
          "accountType": null,
          "planType": null,
          "ownership": null,
          "productName": null,
          "cusip": null,
          "trailingCommission": false,
          "contractStatus": null,
          "withdrawalStructure": {
            "systematicInPlace": false
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
}
```

### Field Reference

| Field                                     | Type   | Description                                          |
| ----------------------------------------- | ------ | ---------------------------------------------------- |
| `requestingFirm.firmName`                 | string | Echoed requesting firm name from the request         |
| `requestingFirm.firmId`                   | string | Echoed DTCC firm identifier from the request         |
| `requestingFirm.servicingAgent.agentName` | string | Echoed agent name from the request                   |
| `requestingFirm.servicingAgent.npn`       | string | Echoed NPN from the request                          |
| `producerValidation.agentName`            | string | Echoed agent name from the request                   |
| `producerValidation.npn`                  | string | Echoed NPN from the request                          |
| `producerValidation.errors`               | array  | Producer-level validation errors (see error catalog) |
| `client.clientName`                       | string | Client name echoed back for confirmation             |
| `client.ssnLast4`                         | string | Last four digits of the client's SSN                 |
| `client.policies`                         | array  | List of policy details                               |

#### Policy Object

| Field                                   | Type    | Description                                                       |
| --------------------------------------- | ------- | ----------------------------------------------------------------- |
| `policyNumber`                          | string  | Policy number identifying the policy                              |
| `carrierName`                           | string  | Name of the insurance carrier that wrote the annuity              |
| `accountType`                           | enum    | Registration type of the account (see enums)                      |
| `planType`                              | enum    | Tax qualification type of the account (see enums)                 |
| `ownership`                             | string  | Ownership structure of the policy                                 |
| `productName`                           | string  | Name of the annuity product                                       |
| `cusip`                                 | string  | CUSIP identifier for the product                                  |
| `trailingCommission`                    | boolean | Whether trailing commission will apply to the new servicing agent |
| `contractStatus`                        | string  | Current status of the contract                                    |
| `withdrawalStructure.systematicInPlace` | boolean | Whether a systematic withdrawal plan is currently active          |
| `errors`                                | array   | Any errors or issues associated with this policy                  |

### Notes

- The `policies` array contains one entry per policy number submitted in the request, with `policyNumber` identifying each policy.
- The delivering firm information is **not** included in the response — DTCC is aware of the delivering firm but does not pass it back to the receiving firm.
- The response returns only the **last four digits** of the SSN for security.
- The `trailingCommission` field is a simple yes/no indicating whether the new servicing agent will receive trailing commissions on this policy.

---

## Enums

### accountType

| Value        | Description        |
| ------------ | ------------------ |
| `individual` | Individual account |
| `joint`      | Joint account      |
| `trust`      | Trust account      |
| `custodial`  | Custodial account  |
| `entity`     | Entity account     |

### planType

| Value            | Description                                |
| ---------------- | ------------------------------------------ |
| `nonQualified`   | Non-qualified (after-tax) account          |
| `rothIra`        | Roth Individual Retirement Account         |
| `traditionalIra` | Traditional Individual Retirement Account  |
| `sep`            | Simplified Employee Pension                |
| `simple`         | Savings Incentive Match Plan for Employees |

> **Note:** The planType list is a starting set. The full DTCC qualified account type list will be incorporated in a future revision.

---

## Error Catalog

### Producer-Level Errors

Returned in the `producerValidation.errors` array at the response level. These errors apply to the servicing agent across all contracts in the request.

| Error Code            | Message                                                                        | Description                                                                                                              |
| --------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `notAppointed`        | Producer is not appointed with {carrierName}                                   | The servicing agent does not have an active appointment with the carrier                                                 |
| `notLicensed`         | Producer is not licensed in {state}                                            | The servicing agent does not hold the required license for the applicable jurisdiction                                   |
| `affiliationMismatch` | Producer {agentName} is affiliated with {affiliatedFirm}, not {requestingFirm} | The carrier's records show the producer is associated with a different broker/dealer than the one submitting the request |

### Policy-Level Errors

Returned in the `errors` array within each policy object.

| Error Code            | Message                                                            | Description                                                                                         |
| --------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| `ssnContractMismatch` | Client's SSN does not match the contract on file                   | The SSN provided in the request does not match the delivering firm's records for that policy number |
| `proprietaryProduct`  | Contract {policyNumber} is a proprietary product                   | The product is proprietary to the delivering firm and is not eligible for transfer                  |
| `policyInactive`      | Policy is inactive                                                 | The contract is no longer active (e.g., surrendered, matured, lapsed)                               |
| `policyRestricted`    | Policy is restricted for the following reason: {restrictionReason} | The policy has a restriction that prevents or limits the BD change process                          |

### Example — Mixed Results

```json
"policies": [
  {
    "policyNumber": "ABC123",
    "carrierName": null,
    "accountType": null,
    "planType": null,
    "ownership": null,
    "productName": null,
    "cusip": null,
    "trailingCommission": false,
    "contractStatus": null,
    "withdrawalStructure": {
      "systematicInPlace": false
    },
    "errors": [
      {
        "errorCode": "ssnContractMismatch",
        "message": "Client's SSN does not match the contract on file"
      }
    ]
  },
  {
    "policyNumber": "DEF456",
    "carrierName": "Pacific Life",
    "accountType": "individual",
    "planType": "nonQualified",
    "ownership": "single",
    "productName": "Pacific Destinations",
    "cusip": "694308AB1",
    "trailingCommission": true,
    "contractStatus": "active",
    "withdrawalStructure": {
      "systematicInPlace": false
    },
    "errors": []
  },
  {
    "policyNumber": "GHI789",
    "carrierName": "Nationwide",
    "accountType": "individual",
    "planType": "traditionalIra",
    "ownership": null,
    "productName": null,
    "cusip": null,
    "trailingCommission": false,
    "contractStatus": "surrendered",
    "withdrawalStructure": {
      "systematicInPlace": false
    },
    "errors": [
      {
        "errorCode": "policyInactive",
        "message": "Policy is inactive"
      }
    ]
  }
]
```

---

## Sequence Context

This request/response pair covers Steps 1 and 2 of the broader BD Change Process. After the Receiving Firm reviews the returned policy details (Step 3 — Due Diligence), in-scope policies proceed to Step 4 where individual BD Change Requests are sent to each carrier for validation.
