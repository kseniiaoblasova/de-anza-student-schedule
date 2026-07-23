"""
Create every DynamoDB table this project needs, skipping any that already exist.

Provisions tables only — it does not load data. Schemas come from
common.TABLE_SCHEMAS, so this stays in sync with the loaders. Safe to re-run.

Usage:
    python scripts/create_tables.py            # create missing tables
    python scripts/create_tables.py --list     # just show which exist vs missing
"""

import sys
import argparse
from pathlib import Path

# Make the shared helpers importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import TABLE_SCHEMAS, get_session, list_table_names, create_table_if_absent


def main():
    parser = argparse.ArgumentParser(description="Create project DynamoDB tables")
    parser.add_argument("--list", action="store_true",
                        help="Only report existing vs missing tables")
    args = parser.parse_args()

    session = get_session()

    # Show current state before doing anything
    existing = set(list_table_names(session))
    print("Registered tables:")
    for name in TABLE_SCHEMAS:
        state = "exists" if name in existing else "missing"
        print(f"  {name}: {state}")

    if args.list:
        return

    # Create only the ones that are missing
    print("\nCreating missing tables...")
    created_any = False
    for name in TABLE_SCHEMAS:
        created = create_table_if_absent(name, session)
        if created:
            print(f"  created: {name}")
            created_any = True
        else:
            print(f"  skipped (already exists): {name}")

    print("\nDone." if created_any else "\nNothing to create — all tables exist.")


if __name__ == "__main__":
    main()
