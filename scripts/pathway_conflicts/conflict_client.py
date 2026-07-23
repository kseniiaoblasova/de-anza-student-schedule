"""
Client for the deployed schedule-conflict service.

Two ways to reach the same Lambda:
  - direct  : boto3 lambda.invoke (server-to-server, uses AWS creds, no API key,
              not subject to the API-gateway usage-plan throttle) — the default
              for this batch job.
  - http    : POST to the API Gateway endpoint with an x-api-key header — the
              same path external callers use.

Both return the engine report dict ({conflict_count, pairs_evaluated,
conflicts, ...}) and raise ConflictServiceError on a non-200 result.
"""

import os
import json
import urllib.request
import urllib.error

DEFAULT_FUNCTION = "deanza-schedule-conflicts"


class ConflictServiceError(RuntimeError):
    """Raised when the conflict service returns a non-200 / unusable response."""


def _unwrap(response_dict):
    """Turn the Lambda's {statusCode, body} envelope into the report dict."""
    status = response_dict.get("statusCode")
    body = response_dict.get("body")
    if isinstance(body, str):
        body = json.loads(body)
    if status != 200:
        raise ConflictServiceError(f"conflict service returned {status}: {body}")
    return body


def invoke_direct(payload, function_name=DEFAULT_FUNCTION, session=None):
    """Invoke the Lambda directly via boto3 and return the report dict."""
    from common import get_session  # local import: keeps this module import-light

    client = (session or get_session()).client("lambda")
    resp = client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )
    # A function-level failure (unhandled exception) shows up as FunctionError.
    if resp.get("FunctionError"):
        raise ConflictServiceError(
            f"Lambda FunctionError: {resp['Payload'].read().decode('utf-8')}")
    return _unwrap(json.loads(resp["Payload"].read()))


def invoke_http(payload, url=None, api_key=None):
    """POST to the API Gateway endpoint (x-api-key) and return the report dict.

    Reads CONFLICTS_API_URL / CONFLICTS_API_KEY from the environment when not
    passed explicitly.
    """
    url = url or os.environ.get("CONFLICTS_API_URL")
    api_key = api_key or os.environ.get("CONFLICTS_API_KEY")
    if not url or not api_key:
        raise ConflictServiceError(
            "HTTP mode needs CONFLICTS_API_URL and CONFLICTS_API_KEY.")

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            report = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise ConflictServiceError(
            f"conflict service HTTP {e.code}: {e.read().decode('utf-8')}") from e
    # The HTTP path already returns the report body (API Gateway proxy unwraps it).
    return report


def make_caller(mode="direct", function_name=DEFAULT_FUNCTION, session=None,
                url=None, api_key=None):
    """Return a payload -> report callable for the chosen transport."""
    if mode == "direct":
        return lambda payload: invoke_direct(payload, function_name, session)
    if mode == "http":
        return lambda payload: invoke_http(payload, url, api_key)
    raise ValueError(f"unknown mode '{mode}' (use 'direct' or 'http')")
