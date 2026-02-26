"""
Local test script for the PDF Policy Statement Extractor.

Usage:
  python test_extract.py <path/to/policy_statement.pdf>

  Encodes the PDF as Base64, starts a request against the local Flask server
  (http://localhost:5001/extract), and pretty-prints the full JSON response.

Requirements:
  - Flask server must be running: python app.py
  - AWS credentials with bedrock:InvokeModel permission must be in the environment

Examples:
  python test_extract.py ~/Downloads/policy_statement.pdf
  python test_extract.py ~/Downloads/policy_statement.pdf --url http://localhost:5001
"""

import argparse
import base64
import json
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description="Test the PDF policy extractor")
    parser.add_argument("pdf_path", help="Path to the policy statement PDF")
    parser.add_argument(
        "--url",
        default="http://localhost:5001",
        help="Base URL of the extractor service (default: http://localhost:5001)",
    )
    args = parser.parse_args()

    pdf_file = Path(args.pdf_path)
    if not pdf_file.exists():
        print(f"ERROR: File not found: {pdf_file}", file=sys.stderr)
        sys.exit(1)
    if not pdf_file.suffix.lower() == ".pdf":
        print(f"WARNING: File does not have a .pdf extension: {pdf_file}", file=sys.stderr)

    print(f"Reading PDF: {pdf_file} ({pdf_file.stat().st_size:,} bytes)")
    pdf_bytes = pdf_file.read_bytes()
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    print(f"Base64 length: {len(pdf_base64):,} characters")

    request_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())

    payload = {
        "requestId": request_id,
        "pdfBase64": pdf_base64,
    }

    endpoint = f"{args.url.rstrip('/')}/extract"
    print(f"\nPOSTing to: {endpoint}")
    print(f"  requestId: {request_id}")
    print(f"  requestId:     {request_id}")
    print("\nCalling Bedrock... (may take 10-30 seconds)\n")

    body = json.dumps(payload).encode("utf-8")
    req = Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "requestId": request_id,
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            status = resp.status
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        status = e.code
    except URLError as e:
        print(f"Connection error: {e}", file=sys.stderr)
        print("Is the Flask server running? Start it with: python app.py", file=sys.stderr)
        sys.exit(1)

    print(f"HTTP {status}")
    print("─" * 70)

    try:
        parsed = json.loads(raw)
        print(json.dumps(parsed, indent=2))

        # Quick summary
        if parsed.get("code") == "EXTRACTED":
            inquiry = (parsed.get("payload") or {}).get("policyInquiryResponse", {})
            client = inquiry.get("client", {})
            policies = client.get("policies", [])
            print("\n" + "─" * 70)
            print(f"✓ Extracted {len(policies)} policy/policies")
            print(f"  Client:     {client.get('clientName', 'N/A')}")
            print(f"  SSN last 4: {client.get('ssnLast4', 'N/A')}")
            for p in policies:
                print(f"  Policy:     {p.get('policyNumber')}  "
                      f"{p.get('productName', '')}  "
                      f"({p.get('contractStatus', '')})")
        else:
            print(f"\n✗ Response code: {parsed.get('code')} — {parsed.get('message')}")
    except json.JSONDecodeError:
        print(raw)


if __name__ == "__main__":
    main()
