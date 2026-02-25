"""
PDF Policy Statement → PolicyInquiryResponse Extractor

Accepts a Base64-encoded carrier policy statement PDF, sends it to Claude via
the Bedrock converse() API as a native document block, and returns a structured
policyInquiryResponse JSON matching the Step 2 BD Change process format.

No text-extraction library is needed — Claude reads the PDF layout directly.
"""

import base64
import json
import logging

import boto3

logger = logging.getLogger(__name__)

MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
REGION = "us-east-1"

SYSTEM_PROMPT = """You are a document data extraction specialist for annuity policy statements.

Your job: read the provided policy statement PDF and extract every relevant field into a
policyInquiryResponse JSON object. Return ONLY the JSON — no markdown, no code fences,
no explanation, no prose before or after.

───────────────────────────────────────────────────────────────────────────────
FIELD EXTRACTION GUIDE
───────────────────────────────────────────────────────────────────────────────

requestingFirm
  firmName  → The BROKER-DEALER or financial advisory FIRM that submitted this application
              (e.g. "Strategic Wealth Advisors", "Premier Financial Services").
              This is NOT the insurance carrier. Look for labels like "Broker-Dealer",
              "Selling Firm", "Advisor Firm", "Receiving Firm", "BD Firm", or the
              firm associated with the servicing agent's employer.
  firmId    → The BD firm's identifier (DTCC ID, CRD, or internal firm ID shown on the
              document). null if not present.
  servicingAgent
    agentName → Full name of the financial adviser / agent of record / servicing agent
    npn       → Agent's National Producer Number (NPN). null if not shown.

producerValidation
  agentName → Same as requestingFirm.servicingAgent.agentName
  npn       → Same as requestingFirm.servicingAgent.npn
  errors    → Always []

client
  clientName  → For INDIVIDUAL accounts: the policy owner's full legal name.
                For TRUST accounts: the full trust name (e.g. "Foster Family Irrevocable Trust"),
                NOT the trustee's personal name.
                For BUSINESS/ENTITY accounts: the entity name.
  ssnLast4    → Last 4 digits of SSN. For trusts, use the trustee/representative's SSN last 4.
                For businesses, use the Tax ID last 4. null if not shown at all.
  policies    → Array — one entry per policy/contract found in the document.

For each policy found:
  policyNumber      → Contract or policy number exactly as printed
  carrierName       → Full name of the INSURANCE CARRIER that issued the annuity
                      (e.g. "Crestview Insurance", "Athene Annuity"). This is NOT the BD firm.
  accountType       → Map registration type to exactly one of:
                        individual | joint | trust | custodial | entity
                      (default "individual" if unclear)
  planType          → Map tax qualification to exactly one of:
                        nonQualified | rothIra | traditionalIra | sep | simple
                      (default "nonQualified" if unclear or not shown)
  ownership         → "single" | "joint" | "trust" | "other" — null if not shown
  productName       → Full annuity product name exactly as printed
  cusip             → 9-character CUSIP identifier. Search the ENTIRE document carefully —
                      it may appear in a product details section, header, or footer.
                      Return the value if found; null only if genuinely absent after
                      thorough review.
  trailingCommission → false unless the document explicitly states trailing commission applies
  contractStatus    → Map to exactly one of:
                        active          — policy is in force / issued / current
                        pending         — application submitted, not yet issued
                        surrendered     — contract has been surrendered
                        death claim pending — death claim in process
                      Use "pending" if the document shows status "Pending", "Application",
                      "Not Yet Issued", or similar pre-issuance language.
  withdrawalStructure
    systematicInPlace → true only if document explicitly shows a systematic withdrawal
                        plan is currently active; false otherwise
  errors            → [] (empty — no validation errors at extraction time)

enums (always include these fixed values):
  accountType: ["individual", "joint", "trust", "custodial", "entity"]
  planType:    ["nonQualified", "rothIra", "traditionalIra", "sep", "simple"]

───────────────────────────────────────────────────────────────────────────────
OUTPUT STRUCTURE — return exactly this shape, nothing else:
───────────────────────────────────────────────────────────────────────────────
{
  "policyInquiryResponse": {
    "requestingFirm": {
      "firmName": "...",
      "firmId": null,
      "servicingAgent": { "agentName": "...", "npn": "..." }
    },
    "producerValidation": {
      "agentName": "...",
      "npn": "...",
      "errors": []
    },
    "client": {
      "clientName": "...",
      "ssnLast4": "...",
      "policies": [
        {
          "policyNumber": "...",
          "carrierName": "...",
          "accountType": "individual",
          "planType": "nonQualified",
          "ownership": "single",
          "productName": "...",
          "cusip": null,
          "trailingCommission": false,
          "contractStatus": "active",
          "withdrawalStructure": { "systematicInPlace": false },
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
"""


def _strip_fences(text: str) -> str:
    """Strip markdown code fences that the model occasionally wraps around JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def extract_from_pdf(pdf_base64: str, request_id: str) -> dict:
    """
    Decode a Base64-encoded policy statement PDF and extract structured data.

    Uses the Bedrock converse() API with a native document block — Claude reads
    the PDF layout directly without any intermediate text extraction.

    Args:
        pdf_base64: Base64-encoded PDF bytes (standard or URL-safe encoding accepted).
        request_id: Caller-supplied request identifier, echoed in logs.

    Returns:
        Parsed dict with key "policyInquiryResponse" matching the Step 2 spec schema.

    Raises:
        ValueError: If pdf_base64 cannot be decoded.
        json.JSONDecodeError: If the model returns non-JSON output.
        botocore.exceptions.ClientError: On Bedrock API errors.
    """
    # Decode — handle both standard and URL-safe base64
    try:
        pdf_bytes = base64.b64decode(pdf_base64, validate=False)
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding: {e}") from e

    logger.info("Sending PDF to Bedrock for extraction — request_id=%s, size=%d bytes",
                request_id, len(pdf_bytes))

    client = boto3.client("bedrock-runtime", region_name=REGION)

    response = client.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "document": {
                            "format": "pdf",
                            "name": "policy_statement",
                            "source": {"bytes": pdf_bytes},
                        }
                    },
                    {
                        "text": (
                            f"Extract all policy information from this statement. "
                            f"Request ID: {request_id}. "
                            "Return ONLY the JSON object — no other text."
                        )
                    },
                ],
            }
        ],
    )

    raw = response["output"]["message"]["content"][0]["text"]
    logger.info("Bedrock extraction complete — request_id=%s, response_length=%d",
                request_id, len(raw))

    raw = _strip_fences(raw)
    return json.loads(raw)
