#!/usr/bin/env python3
"""
Load sample data into the request-tracking DynamoDB table.
Uses UUIDs for pk and sk as specified.
"""

import boto3
import uuid
from datetime import datetime, timedelta
import random
import os

# Configuration
TABLE_NAME = os.environ.get("REQUEST_TRACKING_TABLE", "request-tracking")
REGION = os.environ.get("AWS_REGION", "us-east-1")

# Status progression per the API spec
STATUSES = [
    "MANIFEST_REQUESTED",
    "MANIFEST_RECEIVED",
    "DUE_DILIGENCE_COMPLETE",
    "CARRIER_VALIDATION_PENDING",
    "CARRIER_APPROVED",
    "CARRIER_REJECTED",
    "TRANSFER_INITIATED",
    "TRANSFER_PROCESSING",
    "TRANSFER_CONFIRMED",
    "COMPLETE",
]

# Sample broker and carrier IDs
RECEIVING_BROKERS = ["RBD-001", "RBD-002", "RBD-003"]
DELIVERING_BROKERS = ["DBD-001", "DBD-002", "DBD-003"]
CARRIERS = [
    {"id": "athene", "name": "Athene"},
    {"id": "pacific-life", "name": "Pacific Life"},
]

# Sample client data
CLIENTS = [
    {"name": "John Smith", "ssnLast4": "6789"},
    {"name": "Mary Johnson", "ssnLast4": "4321"},
    {"name": "Robert Williams", "ssnLast4": "5555"},
    {"name": "Patricia Brown", "ssnLast4": "1234"},
    {"name": "Michael Davis", "ssnLast4": "9876"},
    {"name": "Jennifer Garcia", "ssnLast4": "2468"},
    {"name": "David Martinez", "ssnLast4": "1357"},
    {"name": "Linda Wilson", "ssnLast4": "8642"},
]

# Sample policy prefixes
POLICY_PREFIXES = {"athene": "ATH", "pacific-life": "PAC"}


def generate_status_history(current_status_idx: int, base_time: datetime) -> list:
    """Generate status history up to the current status."""
    history = []
    notes_map = {
        "MANIFEST_REQUESTED": "Policy inquiry request received from receiving broker",
        "MANIFEST_RECEIVED": "Policy inquiry response received from delivering broker",
        "DUE_DILIGENCE_COMPLETE": "Due diligence checks completed",
        "CARRIER_VALIDATION_PENDING": "BD change request sent to carrier for validation",
        "CARRIER_APPROVED": "Carrier validated and approved the BD change request",
        "CARRIER_REJECTED": "Carrier rejected the BD change request",
        "TRANSFER_INITIATED": "Transfer process initiated",
        "TRANSFER_PROCESSING": "Transfer is being processed",
        "TRANSFER_CONFIRMED": "Transfer confirmed by delivering broker",
        "COMPLETE": "BD change process completed successfully",
    }

    for i in range(current_status_idx + 1):
        status = STATUSES[i]
        timestamp = base_time + timedelta(hours=i * 2, minutes=random.randint(0, 59))
        history.append({
            "status": status,
            "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "notes": notes_map.get(status, ""),
        })

    return history


def generate_sample_records(count: int = 15) -> list:
    """Generate sample request tracking records."""
    records = []
    base_time = datetime.utcnow() - timedelta(days=7)

    for i in range(count):
        # Generate UUIDs for pk and sk
        pk = str(uuid.uuid4())
        sk = str(uuid.uuid4())
        request_id = pk  # Use pk as transaction ID for simplicity

        # Select random entities
        carrier = random.choice(CARRIERS)
        client = random.choice(CLIENTS)
        receiving_broker = random.choice(RECEIVING_BROKERS)
        delivering_broker = random.choice(DELIVERING_BROKERS)

        # Determine status - weight toward middle/end of process
        if i < 3:
            # Some early stage
            status_idx = random.randint(0, 3)
        elif i < 8:
            # Mid stage
            status_idx = random.randint(3, 6)
        else:
            # Later stages
            status_idx = random.randint(6, 9)

        # Skip CARRIER_REJECTED sometimes for variety
        if STATUSES[status_idx] == "CARRIER_REJECTED" and random.random() > 0.3:
            status_idx = 4  # Use CARRIER_APPROVED instead

        current_status = STATUSES[status_idx]

        # Generate policy numbers
        prefix = POLICY_PREFIXES[carrier["id"]]
        policy_count = random.randint(1, 3)
        policies = [f"{prefix}-{100000 + i * 10 + j}" for j in range(policy_count)]

        # Calculate timestamps
        record_base_time = base_time + timedelta(days=i % 5, hours=random.randint(0, 23))
        status_history = generate_status_history(status_idx, record_base_time)

        created_at = status_history[0]["timestamp"]
        updated_at = status_history[-1]["timestamp"]

        record = {
            "pk": pk,
            "sk": sk,
            "requestId": request_id,
            "currentStatus": current_status,
            "createdAt": created_at,
            "updatedAt": updated_at,
            "statusHistory": status_history,
            "receivingBrokerId": receiving_broker,
            "deliveringBrokerId": delivering_broker,
            "carrierId": carrier["id"],
            "carrierName": carrier["name"],
            "clientName": client["name"],
            "ssnLast4": client["ssnLast4"],
            "policiesAffected": policies,
            "additionalData": {
                "requestType": "BD_CHANGE",
                "priority": random.choice(["normal", "high"]),
            },
        }

        # Add rejection reason if rejected
        if current_status == "CARRIER_REJECTED":
            record["rejectionReason"] = random.choice([
                "Producer is not appointed with carrier",
                "Producer is not licensed in state",
                "Policy is not eligible for transfer",
                "Suitability requirements not met",
            ])

        records.append(record)

    return records


def verify_table_exists(dynamodb_client):
    """Verify the request-tracking table exists."""
    try:
        response = dynamodb_client.describe_table(TableName=TABLE_NAME)
        status = response["Table"]["TableStatus"]
        print(f"Table '{TABLE_NAME}' exists (status: {status}).")
        return True
    except dynamodb_client.exceptions.ResourceNotFoundException:
        print(f"ERROR: Table '{TABLE_NAME}' does not exist!")
        print("Please create the table first or check the TABLE_NAME environment variable.")
        return False


def load_data(records: list):
    """Load records into DynamoDB."""
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(TABLE_NAME)

    print(f"Loading {len(records)} records into '{TABLE_NAME}'...")

    with table.batch_writer() as batch:
        for record in records:
            batch.put_item(Item=record)

    print(f"Successfully loaded {len(records)} records.")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Request Tracking Data Loader")
    print("=" * 60)
    print(f"Table: {TABLE_NAME}")
    print(f"Region: {REGION}")
    print()

    # Create DynamoDB client
    dynamodb_client = boto3.client("dynamodb", region_name=REGION)

    # Verify table exists
    if not verify_table_exists(dynamodb_client):
        return

    # Generate sample data
    records = generate_sample_records(15)

    # Print sample record for verification
    print("\nSample record structure:")
    print("-" * 40)
    sample = records[0]
    for key in ["pk", "sk", "requestId", "currentStatus", "carrierId", "clientName"]:
        print(f"  {key}: {sample.get(key)}")
    print(f"  policiesAffected: {sample.get('policiesAffected')}")
    print(f"  statusHistory: [{len(sample.get('statusHistory', []))} entries]")
    print()

    # Load data
    load_data(records)

    print("\nData loading complete!")
    print("=" * 60)

    # Print transaction IDs for testing
    print("\nTransaction IDs for testing query-status endpoint:")
    for i, record in enumerate(records[:5]):
        print(f"  {i + 1}. {record['requestId']} ({record['currentStatus']})")


if __name__ == "__main__":
    main()
