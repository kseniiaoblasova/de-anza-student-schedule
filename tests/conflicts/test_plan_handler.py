"""Tests for the student-planner Lambda handler (section lookup is stubbed)."""

import json

import pytest

from conflicts import plan_handler
from conflicts.plan_handler import handler


@pytest.fixture
def stub_lookup(monkeypatch):
    """Replace the DynamoDB-backed lookup with a canned (sections, offered,
    not_offered) result so the handler can be tested without AWS."""
    def _install(sections, offered, not_offered):
        monkeypatch.setattr(
            plan_handler, "lookup_sections",
            lambda term_code, courses: (sections, offered, not_offered))
    return _install


CONFLICTING_SECTIONS = [
    {"course": "MATH 1A", "crn": "100", "meeting_days": "MW",
     "meeting_times": "09:30 am-10:20 am"},
    {"course": "ENGL 1A", "crn": "200", "meeting_days": "MW",
     "meeting_times": "09:30 am-10:20 am"},
    {"course": "HIST 1A", "crn": "300", "meeting_days": "TR",
     "meeting_times": "01:00 pm-01:50 pm"},
]


def test_returns_overlap_split_and_percentage(stub_lookup):
    stub_lookup(CONFLICTING_SECTIONS, ["MATH 1A", "ENGL 1A", "HIST 1A"], [])
    resp = handler({"term_code": "202722", "courses": ["MATH 1A", "ENGL 1A", "HIST 1A"]})
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    assert body["term_code"] == "202722"
    assert body["pairs_evaluated"] == 3
    assert body["overlap_count"] == 1
    assert body["clear_count"] == 2
    assert body["overlap_percentage"] == pytest.approx(33.3)
    assert len(body["overlaps"]) == 1 and len(body["clear"]) == 2
    assert body["offered_courses"] == ["MATH 1A", "ENGL 1A", "HIST 1A"]


def test_not_offered_courses_surfaced(stub_lookup):
    stub_lookup(CONFLICTING_SECTIONS[:1], ["MATH 1A"], ["PHYS 4A"])
    body = json.loads(handler({"term_code": "202722",
                               "courses": ["MATH 1A", "PHYS 4A"]})["body"])
    assert body["not_offered_courses"] == ["PHYS 4A"]
    assert body["pairs_evaluated"] == 0
    assert body["overlap_percentage"] == 0.0


def test_missing_term_code_is_400():
    resp = handler({"courses": ["MATH 1A"]})
    assert resp["statusCode"] == 400
    assert "term_code" in json.loads(resp["body"])["error"]


def test_missing_courses_is_400():
    resp = handler({"term_code": "202722"})
    assert resp["statusCode"] == 400
    assert "courses" in json.loads(resp["body"])["error"]


def test_empty_courses_list_is_400():
    resp = handler({"term_code": "202722", "courses": []})
    assert resp["statusCode"] == 400


def test_apigw_wrapped_body(stub_lookup):
    stub_lookup(CONFLICTING_SECTIONS, ["MATH 1A", "ENGL 1A", "HIST 1A"], [])
    event = {"body": json.dumps({"term_code": "202722",
                                 "courses": ["MATH 1A", "ENGL 1A", "HIST 1A"]}),
             "requestContext": {"http": {"method": "POST"}}}
    resp = handler(event)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["overlap_count"] == 1


def test_malformed_json_is_400():
    resp = handler({"body": "{not json", "requestContext": {"http": {"method": "POST"}}})
    assert resp["statusCode"] == 400


def test_lookup_failure_is_500(monkeypatch):
    def _boom(term_code, courses):
        raise RuntimeError("dynamo down")
    monkeypatch.setattr(plan_handler, "lookup_sections", _boom)
    resp = handler({"term_code": "202722", "courses": ["MATH 1A"]})
    assert resp["statusCode"] == 500


# ---- CORS ----

def test_options_preflight_no_lookup():
    """Preflight short-circuits before any lookup: 204 + CORS headers."""
    resp = handler({"requestContext": {"http": {"method": "OPTIONS"}}})
    assert resp["statusCode"] == 204
    assert resp["headers"]["Access-Control-Allow-Origin"] == "*"


def test_response_has_cors_header(stub_lookup):
    stub_lookup([], [], [])
    resp = handler({"term_code": "202722", "courses": ["MATH 1A"]})
    assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
