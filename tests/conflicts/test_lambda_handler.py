"""Tests for the Lambda handler adapter."""

import json

from conflicts.lambda_handler import handler

CONFLICTING = [
    {"course": "MATH 1A", "crn": "100", "meeting_days": "MW", "meeting_times": "09:30 am-10:20 am"},
    {"course": "ENGL 1A", "crn": "200", "meeting_days": "MW", "meeting_times": "09:30 am-10:20 am"},
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
            {"course": "MATH 1A", "crn": "100", "meeting_days": "MW", "meeting_times": "09:30 am-10:20 am"},
            {"course": "ENGL 1A", "crn": "200", "meeting_days": "TR", "meeting_times": "09:30 am-10:20 am"},
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
    resp = handler(_apigw(base64.b64encode(raw).decode("ascii"), base64_encoded=True))
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["conflict_count"] == 1


def test_empty_sections_list_is_200_zero_conflicts():
    resp = handler({"sections": []})
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["conflict_count"] == 0
    assert body["sections_evaluated"] == 0
