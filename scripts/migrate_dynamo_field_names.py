#!/usr/bin/env python3
"""
Migrate DynamoDB field names to match unified spec v0.1.1.

Field renames:
- requestId → requestId
- trailingCommission → hasTrailingCommission
- systematicWithdrawal → hasSystematicWithdrawal
- withdrawalStructure.systematicInPlace → withdrawalStructure.hasSystematicWithdrawal

Tables affected:
- carrier (Athene)
- carrier-2 (Pacific Life)
- carrier-3 (Prudential)
- iiex
- distributor
- distributor-2
- request-tracking
"""

import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

TABLES = [
    'carrier',
    'carrier-2',
    'carrier-3',
    'iiex',
    'distributor',
    'distributor-2',
    'request-tracking'
]

# Field rename mappings
FIELD_RENAMES = {
    'requestId': 'requestId',
    'trailingCommission': 'hasTrailingCommission',
    'systematicWithdrawal': 'hasSystematicWithdrawal',
    'commissionTrails': 'hasTrailingCommission',  # alias used in some tables
}

# Nested field renames (parent_field -> {old_key: new_key})
NESTED_FIELD_RENAMES = {
    'withdrawalStructure': {
        'systematicInPlace': 'hasSystematicWithdrawal'
    }
}


def scan_all_items(table_name):
    """Scan all items from a table."""
    table = dynamodb.Table(table_name)
    items = []

    response = table.scan()
    items.extend(response.get('Items', []))

    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))

    return items


def rename_fields(item):
    """Rename fields in an item according to the mappings."""
    updated = False
    new_item = dict(item)

    # Rename top-level fields
    for old_name, new_name in FIELD_RENAMES.items():
        if old_name in new_item and new_name not in new_item:
            new_item[new_name] = new_item.pop(old_name)
            updated = True

    # Rename nested fields
    for parent_field, renames in NESTED_FIELD_RENAMES.items():
        if parent_field in new_item and isinstance(new_item[parent_field], dict):
            parent = new_item[parent_field]
            for old_name, new_name in renames.items():
                if old_name in parent and new_name not in parent:
                    parent[new_name] = parent.pop(old_name)
                    updated = True

    # Handle statusHistory array - rename requestId in each entry
    if 'statusHistory' in new_item and isinstance(new_item['statusHistory'], list):
        for entry in new_item['statusHistory']:
            if isinstance(entry, dict) and 'requestId' in entry and 'requestId' not in entry:
                entry['requestId'] = entry.pop('requestId')
                updated = True

    return new_item, updated


def update_item(table_name, item):
    """Update an item in the table."""
    table = dynamodb.Table(table_name)
    table.put_item(Item=item)


def migrate_table(table_name):
    """Migrate all items in a table."""
    print(f"\nMigrating table: {table_name}")
    print("-" * 40)

    try:
        items = scan_all_items(table_name)
        print(f"  Found {len(items)} items")

        updated_count = 0
        for item in items:
            new_item, was_updated = rename_fields(item)
            if was_updated:
                update_item(table_name, new_item)
                updated_count += 1
                pk = item.get('pk', 'unknown')
                print(f"  Updated: {pk}")

        print(f"  Updated {updated_count} items")
        return len(items), updated_count

    except Exception as e:
        print(f"  Error: {e}")
        return 0, 0


def main():
    print("=" * 60)
    print("DynamoDB Field Name Migration - Unified Spec v0.1.1")
    print("=" * 60)
    print(f"\nStarted at: {datetime.now(timezone.utc).isoformat()}")

    print("\nField renames:")
    for old, new in FIELD_RENAMES.items():
        print(f"  {old} -> {new}")
    print("\nNested field renames:")
    for parent, renames in NESTED_FIELD_RENAMES.items():
        for old, new in renames.items():
            print(f"  {parent}.{old} -> {parent}.{new}")

    total_items = 0
    total_updated = 0

    for table_name in TABLES:
        items, updated = migrate_table(table_name)
        total_items += items
        total_updated += updated

    print("\n" + "=" * 60)
    print("Migration Complete!")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  Tables processed: {len(TABLES)}")
    print(f"  Total items scanned: {total_items}")
    print(f"  Total items updated: {total_updated}")
    print(f"\nCompleted at: {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
