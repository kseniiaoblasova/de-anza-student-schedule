"""
AWS Lambda entry point for the schedule-conflict service.

Thin adapter over the pure `conflict_engine`: it unwraps the request (API
Gateway HTTP API proxy event, or a direct payload for console/local testing),
validates input, runs the engine, and returns an HTTP-shaped response. All the
real logic lives in `conflict_engine` / `time_parsing`, so this stays trivial.

Request body:
    {
      "sections": [ { course, crn, meeting_days, meeting_times, ... }, ... ],
      "require_day_overlap": true,      // optional, default true
      "require_date_overlap": false,    // optional, default false
      "term_code": "202722"             // optional, echoed back for traceability
    }

Response: 200 with the engine report, 400 for bad input, 500 otherwise.

CORS: every response carries CORS headers and an OPTIONS preflight is answered
(without requiring the API key) so a browser/React client can call the endpoint.
The allowed origin comes from CORS_ALLOW_ORIGIN (default "*"); set it to the
frontend's origin to lock things down.
"""

import os
import json
import base64

from conflicts.conflict_engine import find_conflicts


def _cors_headers():
    """CORS headers for browser callers. Origin is env-configurable."""
    return {
        "Access-Control-Allow-Origin": os.environ.get("CORS_ALLOW_ORIGIN", "*"),
        "Access-Control-Allow-Headers": "Content-Type,x-api-key",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
    }


def _response(status, payload):
    headers = {"Content-Type": "application/json", **_cors_headers()}
    return {"statusCode": status, "headers": headers, "body": json.dumps(payload)}


def _request_method(event):
    """The HTTP method for an API Gateway event (REST v1 or HTTP v2), else None."""
    if not isinstance(event, dict):
        return None
    if event.get("httpMethod"):                       # REST API (v1)
        return event["httpMethod"]
    # HTTP API (v2)
    return event.get("requestContext", {}).get("http", {}).get("method")


def _preflight_response():
    """Answer a CORS preflight: 204, CORS headers, empty body, no API key needed."""
    return {"statusCode": 204, "headers": _cors_headers(), "body": ""}


def _extract_payload(event):
    """Get the request dict from either an API Gateway event or a direct invoke.

    API Gateway (HTTP API) delivers the JSON as a string in event["body"],
    optionally base64-encoded. A direct/console invoke may pass the payload dict
    as the event itself. Raises ValueError on malformed JSON.
    """
    if isinstance(event, dict) and "body" in event:
        body = event.get("body")
        if body is None:
            return {}
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")
        if isinstance(body, (str, bytes)):
            return json.loads(body)
        return body  # already a dict (some test harnesses)
    return event if isinstance(event, dict) else {}


def handler(event, context=None):
    """Lambda handler: validate, detect conflicts, return an HTTP response."""
    # Short-circuit CORS preflight before any validation (browsers send OPTIONS
    # with no body and no API key).
    if _request_method(event) == "OPTIONS":
        return _preflight_response()

    # Unwrap and parse the request body.
    try:
        payload = _extract_payload(event)
    except (ValueError, TypeError):
        return _response(400, {"error": "Request body is not valid JSON."})

    # Validate the one required field.
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return _response(400, {"error": "Field 'sections' is required and must be a list."})

    # Run the engine with optional overlap toggles, and echo term_code if given.
    try:
        report = find_conflicts(
            sections,
            require_day_overlap=bool(payload.get("require_day_overlap", True)),
            require_date_overlap=bool(
                payload.get("require_date_overlap", False)),
        )
        if payload.get("term_code"):
            report["term_code"] = payload["term_code"]
        return _response(200, report)
    except Exception as e:  # noqa: BLE001 - never leak a stack trace to the caller
        return _response(500, {"error": "Internal error computing conflicts.",
                               "detail": type(e).__name__})
