"""
Pull data from the project's S3 bucket into the local data/ directory.

Usage:
    python scripts/pull_s3_data.py              # download everything
    python scripts/pull_s3_data.py --prefix schedule/  # download only a prefix
    python scripts/pull_s3_data.py --list       # list bucket contents without downloading
"""

import os
import argparse
from pathlib import Path

import boto3
from dotenv import load_dotenv

# Load credentials and config from .env at project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data" / "s3-raw"


def get_s3_client():
    """Build an S3 client using credentials from environment variables.

    Supports both long-lived IAM keys (AKIA...) and temporary STS credentials
    (ASIA...). Temporary keys additionally require AWS_SESSION_TOKEN, so it is
    passed through when present.
    """
    session = boto3.Session(
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-west-2"),
    )
    return session.client("s3")


def list_objects(s3, bucket: str, prefix: str = ""):
    """Yield all object keys under the given prefix (handles pagination)."""
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
    for page in pages:
        for obj in page.get("Contents", []):
            yield obj["Key"]


def download_file(s3, bucket: str, key: str, dest_dir: Path):
    """Download a single S3 object, preserving its key as a relative path."""
    local_path = dest_dir / key
    local_path.parent.mkdir(parents=True, exist_ok=True)
    s3.download_file(bucket, key, str(local_path))
    return local_path


def main():
    parser = argparse.ArgumentParser(description="Pull data from S3 bucket")
    parser.add_argument(
        "--prefix", default="", help="S3 key prefix to filter downloads"
    )
    parser.add_argument(
        "--list", action="store_true", dest="list_only",
        help="List bucket contents without downloading"
    )
    parser.add_argument(
        "--dest", default=str(DATA_DIR),
        help=f"Local destination directory (default: {DATA_DIR})"
    )
    args = parser.parse_args()

    bucket = os.environ.get("S3_BUCKET_NAME", "dxhub-camp-2026-foothill-student-scheduler")
    s3 = get_s3_client()

    # List mode: print keys and exit
    if args.list_only:
        print(f"Contents of s3://{bucket}/{args.prefix}")
        print("-" * 60)
        for key in list_objects(s3, bucket, args.prefix):
            print(f"  {key}")
        return

    # Download mode
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    print(f"Downloading from s3://{bucket}/{args.prefix}")
    print(f"Destination: {dest}\n")

    count = 0
    for key in list_objects(s3, bucket, args.prefix):
        # Skip "directory" markers
        if key.endswith("/"):
            continue
        local_path = download_file(s3, bucket, key, dest)
        count += 1
        print(f"  [{count}] {key}")

    print(f"\nDone — {count} file(s) downloaded to {dest}")


if __name__ == "__main__":
    main()
