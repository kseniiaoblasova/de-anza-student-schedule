"""
Load De Anza program-pathway maps from S3 (or a local file) into DynamoDB.

Each pathway in deanza_pathways.json becomes one item, keyed by a unique
"<source_file>#<page_number>" id. Run with --create-table the first time to
provision an on-demand table.

Usage:
    python scripts/pathways/load.py --create-table          # create + load local copy
    python scripts/pathways/load.py --from-s3                # load straight from S3
    python scripts/pathways/load.py --table my-table --file path/to/pathways.json
"""

import sys
import json
import argparse
from pathlib import Path

from botocore.exceptions import ClientError

# Make the shared helpers importable when run directly (python scripts/pathways/load.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import (
    PROJECT_ROOT, DEFAULT_BUCKET,
    get_session, get_s3_client, get_dynamodb, create_table_if_absent,
)

# Local copy produced by pull_s3_data.py, and the object key inside the bucket
DEFAULT_LOCAL_FILE = (
    PROJECT_ROOT / "data" / "s3-raw" / "data" / "program-pathways" / "deanza_pathways.json"
)
DEFAULT_S3_KEY = "data/program-pathways/deanza_pathways.json"
DEFAULT_TABLE = "deanza-pathways"


def load_pathways(args, session):
    """Read the pathways JSON either from S3 or from the local pulled copy."""
    if args.from_s3:
        s3 = get_s3_client(session)
        obj = s3.get_object(Bucket=DEFAULT_BUCKET, Key=args.s3_key)
        data = json.loads(obj["Body"].read())
    else:
        with open(args.file, "r") as f:
            data = json.load(f)
    return data["pathways"]


def to_item(pathway):
    """Shape one pathway record into a DynamoDB item.

    The unique key combines source file and page number, since program names
    are not guaranteed unique across the ~80 source PDFs. Program name, village
    and credential type are promoted to top-level attributes for filtering.
    """
    return {
        "pathway_id": f"{pathway['source_file']}#{pathway['page_number']}",
        "program_name": pathway.get("program_name", ""),
        "village": pathway.get("village", ""),
        "credential_type": pathway.get("credential_type", ""),
        "source_file": pathway.get("source_file", ""),
        "page_number": pathway.get("page_number"),
        "years": pathway.get("years", {}),
        "additional_notes": pathway.get("additional_notes", []),
    }


def load_items(table, pathways):
    """Batch-write all pathway items; batch_writer handles chunking + retries."""
    count = 0
    with table.batch_writer() as batch:
        for pathway in pathways:
            batch.put_item(Item=to_item(pathway))
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="Load pathways into DynamoDB")
    parser.add_argument("--table", default=DEFAULT_TABLE, help="DynamoDB table name")
    parser.add_argument("--create-table", action="store_true",
                        help="Create the table first if it does not exist")
    parser.add_argument("--from-s3", action="store_true",
                        help="Read the JSON directly from S3 instead of the local copy")
    parser.add_argument("--s3-key", default=DEFAULT_S3_KEY, help="S3 key of the pathways JSON")
    parser.add_argument("--file", default=str(DEFAULT_LOCAL_FILE),
                        help="Local path to the pathways JSON")
    args = parser.parse_args()

    session = get_session()
    dynamodb = get_dynamodb(session)

    if args.create_table:
        created = create_table_if_absent(args.table, session)
        print(f"{'Created' if created else 'Already exists'}: {args.table}")

    pathways = load_pathways(args, session)
    print(f"Loaded {len(pathways)} pathways from source.")

    table = dynamodb.Table(args.table)
    try:
        written = load_items(table, pathways)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"Table '{args.table}' not found. Re-run with --create-table first.")
            return
        raise

    print(f"Done — wrote {written} items to '{args.table}'.")


if __name__ == "__main__":
    main()
