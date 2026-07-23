"""Tests for the conflict-service client (no real AWS/network)."""

import io
import json

import pytest

from pathway_conflicts.conflict_client import (
    _unwrap,
    invoke_direct,
    make_caller,
    ConflictServiceError,
)

REPORT = {"conflict_count": 1, "pairs_evaluated": 3, "conflicts": [{"course_a": "MATH 1A"}]}


def test_unwrap_200_returns_report():
    envelope = {"statusCode": 200, "body": json.dumps(REPORT)}
    assert _unwrap(envelope) == REPORT


def test_unwrap_non_200_raises():
    envelope = {"statusCode": 400, "body": json.dumps({"error": "bad"})}
    with pytest.raises(ConflictServiceError, match="400"):
        _unwrap(envelope)


class FakeLambdaClient:
    """Stand-in boto3 lambda client returning a canned invoke response."""

    def __init__(self, envelope, function_error=None):
        self._payload = json.dumps(envelope).encode("utf-8")
        self._function_error = function_error
        self.last_kwargs = None

    def invoke(self, **kwargs):
        self.last_kwargs = kwargs
        resp = {"Payload": io.BytesIO(self._payload)}
        if self._function_error:
            resp["FunctionError"] = self._function_error
        return resp


class FakeSession:
    def __init__(self, client):
        self._client = client

    def client(self, name):
        assert name == "lambda"
        return self._client


def test_invoke_direct_parses_report_and_sends_payload():
    fake = FakeLambdaClient({"statusCode": 200, "body": json.dumps(REPORT)})
    payload = {"sections": [{"course": "MATH 1A"}]}
    report = invoke_direct(payload, session=FakeSession(fake))
    assert report == REPORT
    # payload was forwarded to the function as JSON bytes
    sent = json.loads(fake.last_kwargs["Payload"])
    assert sent == payload
    assert fake.last_kwargs["FunctionName"] == "deanza-schedule-conflicts"


def test_invoke_direct_raises_on_function_error():
    fake = FakeLambdaClient({"statusCode": 200, "body": "{}"}, function_error="Unhandled")
    with pytest.raises(ConflictServiceError, match="FunctionError"):
        invoke_direct({"sections": []}, session=FakeSession(fake))


def test_invoke_direct_raises_on_non_200():
    fake = FakeLambdaClient({"statusCode": 500, "body": json.dumps({"error": "x"})})
    with pytest.raises(ConflictServiceError, match="500"):
        invoke_direct({"sections": []}, session=FakeSession(fake))


def test_make_caller_direct_and_bad_mode():
    caller = make_caller("direct", session=FakeSession(
        FakeLambdaClient({"statusCode": 200, "body": json.dumps(REPORT)})))
    assert caller({"sections": []}) == REPORT
    with pytest.raises(ValueError, match="unknown mode"):
        make_caller("carrier-pigeon")
