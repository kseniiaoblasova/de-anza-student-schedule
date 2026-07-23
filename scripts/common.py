"""
Shared helpers for the data-loading scripts.

Centralizes the .env credential loading and boto3 wiring that every loader and
query script needs, so the AWS setup lives in one place. Scripts in subfolders
import this by adding the scripts/ dir to sys.path (see their header), e.g.:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from common import get_table, get_s3_client, PROJECT_ROOT
"""

import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

# Project root is two levels up from this file (scripts/common.py -> repo root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load credentials/config from .env once, on import
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
DEFAULT_BUCKET = os.environ.get(
    "S3_BUCKET_NAME", "dxhub-camp-2026-foothill-student-scheduler"
)


def get_session():
    """Build a boto3 session from env vars.

    Supports both long-lived IAM keys (AKIA...) and temporary STS credentials
    (ASIA...); the session token is passed through when present.
    """
    return boto3.Session(
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
        region_name=DEFAULT_REGION,
    )


def get_s3_client(session=None):
    """Return an S3 client (reuses a session if one is passed in)."""
    return (session or get_session()).client("s3")


def get_dynamodb(session=None):
    """Return a DynamoDB resource."""
    return (session or get_session()).resource("dynamodb")


def get_table(table_name, session=None):
    """Return a DynamoDB Table resource by name."""
    return get_dynamodb(session).Table(table_name)


# Single source of truth for every DynamoDB table this project uses. Both the
# loaders and scripts/create_tables.py provision tables from here, so the key
# schema never drifts between "create" and "load".
TABLE_SCHEMAS = {
    # Program-pathway maps: one item per pathway, unique by source file + page.
    "deanza-pathways": {
        "KeySchema": [{"AttributeName": "pathway_id", "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": "pathway_id", "AttributeType": "S"}],
    },
    # Normalized pathways: cleaned course lists derived from deanza-pathways.
    # Same identity key so a normalized item lines up 1:1 with its source, but
    # this is a separate table so the source is never mutated.
    "deanza-pathways-normalized": {
        "KeySchema": [{"AttributeName": "pathway_id", "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": "pathway_id", "AttributeType": "S"}],
    },
    # Pathway conflicts: one item per pathway per quarter, holding the conflict
    # pairs found among that quarter's course sections. Partitioned by pathway
    # so "all quarters of a pathway" is one query (the React per-pathway view); a
    # GSI on term_code serves "all pathways in a quarter" for cross-pathway views.
    "deanza-pathway-conflicts": {
        "KeySchema": [
            {"AttributeName": "pathway_id", "KeyType": "HASH"},
            {"AttributeName": "quarter_key", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "pathway_id", "AttributeType": "S"},
            {"AttributeName": "quarter_key", "AttributeType": "S"},
            {"AttributeName": "term_code", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "term-index",
                "KeySchema": [
                    {"AttributeName": "term_code", "KeyType": "HASH"},
                    {"AttributeName": "pathway_id", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    },
    # Class schedule (both years): partition by term so a whole quarter is one
    # query; sort key CRN#seq keeps multi-meeting sections from colliding.
    "deanza-class-schedule": {
        "KeySchema": [
            {"AttributeName": "term_code", "KeyType": "HASH"},
            {"AttributeName": "section_key", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "term_code", "AttributeType": "S"},
            {"AttributeName": "section_key", "AttributeType": "S"},
        ],
    },
}


def list_table_names(session=None):
    """Return the names of all DynamoDB tables in the account/region."""
    return get_dynamodb(session).meta.client.list_tables()["TableNames"]


def create_table_if_absent(table_name, session=None):
    """Create an on-demand table from TABLE_SCHEMAS if it doesn't exist yet.

    Returns True if a table was created, False if it already existed. Blocks
    until a newly created table is ACTIVE so callers can write immediately.
    """
    if table_name not in TABLE_SCHEMAS:
        raise KeyError(
            f"No schema registered for '{table_name}'. Add it to TABLE_SCHEMAS."
        )
    client = get_dynamodb(session).meta.client
    if table_name in client.list_tables()["TableNames"]:
        return False

    # On-demand billing: no capacity planning, no idle cost for these datasets
    client.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        **TABLE_SCHEMAS[table_name],
    )
    client.get_waiter("table_exists").wait(TableName=table_name)
    return True
