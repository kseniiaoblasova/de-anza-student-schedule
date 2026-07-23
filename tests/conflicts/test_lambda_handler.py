"""Tests for the Lambda handler adapter."""

import json

from conflicts.lambda_handler import handler

CONFLICTING = [
    {"course": "MATH 1A", "crn": "100", "meeting_days": "MW",
        "meeting_times": "09:30 am-10:20 am"},
    {"course": "ENGL 1A", "crn": "200", "meeting_days": "MW",
        "meeting_times": "09:30 am-10:20 am"},
]


def _apigw(body, base64_encoded=False):
    """Wrap a body string the way API Gateway (HTTP API) delivers it."""
    return {"body": body, "isBase64Encoded": base64_encoded,
            "requestContext": {"http": {"method": "POST"}}}


def test_apigw_event_returns_200_and_report():
    resp = handler(_apigw(json.dumps({"sections": CONFLICTING})))
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["conflict_count"] == 1
    assert body["pairs_evaluated"] == 1


def test_direct_payload_invoke():
    """Console/direct invoke passes the payload as the event itself."""
    resp = handler({"sections": CONFLICTING})
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["conflict_count"] == 1


def test_term_code_echoed():
    resp = handler({"sections": CONFLICTING, "term_code": "202722"})
    assert json.loads(resp["body"])["term_code"] == "202722"


def test_require_day_overlap_false_changes_result():
    payload = {
        "sections": [
            {"course": "MATH 1A", "crn": "100", "meeting_days": "MW",
                "meeting_times": "09:30 am-10:20 am"},
            {"course": "ENGL 1A", "crn": "200", "meeting_days": "TR",
                "meeting_times": "09:30 am-10:20 am"},
        ],
        "require_day_overlap": False,
    }
    # same time, different days -> conflict only when day check is disabled
    assert json.loads(handler(payload)["body"])["conflict_count"] == 1


def test_missing_sections_is_400():
    resp = handler({"term_code": "202722"})
    assert resp["statusCode"] == 400
    assert "sections" in json.loads(resp["body"])["error"]


def test_sections_not_a_list_is_400():
    resp = handler({"sections": "MATH 1A"})
    assert resp["statusCode"] == 400


def test_malformed_json_body_is_400():
    resp = handler(_apigw("{not valid json"))
    assert resp["statusCode"] == 400


def test_base64_encoded_body():
    import base64
    raw = json.dumps({"sections": CONFLICTING}).encode("utf-8")
    resp = handler(_apigw(base64.b64encode(
        raw).decode("ascii"), base64_encoded=True))
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["conflict_count"] == 1


def test_empty_sections_list_is_200_zero_conflicts():
    resp = handler({"sections": []})
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["conflict_count"] == 0
    assert body["sections_evaluated"] == 0


# ---- CORS ----

def test_options_preflight_rest_api():
    """REST API preflight (httpMethod OPTIONS): 204, CORS headers, no body, no engine run."""
    resp = handler({"httpMethod": "OPTIONS", "body": None})
    assert resp["statusCode"] == 204
    assert resp["body"] == ""
    assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
    assert "POST" in resp["headers"]["Access-Control-Allow-Methods"]
    assert "x-api-key" in resp["headers"]["Access-Control-Allow-Headers"]


def test_options_preflight_http_api_v2():
    """HTTP API v2 preflight (requestContext.http.method OPTIONS)."""
    resp = handler({"requestContext": {"http": {"method": "OPTIONS"}}})
    assert resp["statusCode"] == 204
    assert resp["headers"]["Access-Control-Allow-Origin"] == "*"


def test_post_response_has_cors_header():
    resp = handler(_apigw(json.dumps({"sections": CONFLICTING})))
    assert resp["statusCode"] == 200
    assert resp["headers"]["Access-Control-Allow-Origin"] == "*"


def test_error_response_has_cors_header():
    """CORS headers must be present even on 400s (browser needs them to read the error)."""
    resp = handler({"sections": "not-a-list"})
    assert resp["statusCode"] == 400
    assert resp["headers"]["Access-Control-Allow-Origin"] == "*"


def test_cors_allow_origin_env_override(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGIN", "https://app.example.edu")
    resp = handler({"sections": []})
    assert resp["headers"]["Access-Control-Allow-Origin"] == "https://app.example.edu"
