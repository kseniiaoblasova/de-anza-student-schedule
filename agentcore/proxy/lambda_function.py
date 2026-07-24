"""
Public proxy Lambda for the De Anza AgentCore chatbot.

The browser can't call AgentCore Runtime directly (that needs SigV4 signing with
AWS credentials, which must never live in a browser). This Lambda sits in front
with a public Function URL: it takes a chat message, invokes the agent runtime
with the caller's IAM role, strips the model's internal <thinking> notes, and
returns a clean answer with CORS headers.

Request  : POST { "message": "<text>", "sessionId": "<optional>" }
Response : 200 { "answer": "<text>", "sessionId": "<id>" }
"""

import os
import re
import json
import uuid

import boto3

REGION = os.environ.get("AWS_REGION", "us-west-2")
AGENT_RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")

_client = boto3.client("bedrock-agentcore", region_name=REGION)

# Nova wraps its chain-of-thought in <thinking>...</thinking> (remove entirely)
# and sometimes wraps the reply in <response>...</response> (unwrap, keep text).
_THINKING = re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE)
_WRAPPER_TAGS = re.compile(r"</?response>", re.IGNORECASE)


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "access-control-allow-origin": ALLOWED_ORIGIN,
            "access-control-allow-headers": "content-type",
            "access-control-allow-methods": "OPTIONS,POST",
        },
        "body": json.dumps(body),
    }


def _method(event):
    return (event.get("requestContext", {}).get("http", {}) or {}).get("method")


def handler(event, context=None):
    # CORS preflight
    if _method(event) == "OPTIONS":
        return _response(204, {})

    # Parse the request body
    try:
        body = json.loads(event.get("body") or "{}")
    except (ValueError, TypeError):
        return _response(400, {"error": "Request body is not valid JSON."})

    prompt = (body.get("message") or body.get("prompt") or "").strip()
    if not prompt:
        return _response(400, {"error": "A 'message' field is required."})

    # AgentCore requires a runtime session id of at least 33 characters; reuse
    # the caller's if valid, otherwise mint one so multi-turn memory can work.
    session_id = str(body.get("sessionId") or "")
    if len(session_id) < 33:
        session_id = (session_id + uuid.uuid4().hex + uuid.uuid4().hex)[:48]

    # Invoke the agent runtime and unwrap its streamed response
    try:
        resp = _client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=json.dumps({"prompt": prompt}).encode("utf-8"),
            contentType="application/json",
            accept="application/json",
        )
        raw = resp["response"].read().decode("utf-8")

        # The agent returns {"result": "..."}; fall back to raw text if not JSON.
        answer = raw
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and "result" in parsed:
                answer = parsed["result"]
        except (ValueError, TypeError):
            pass

        answer = _THINKING.sub("", answer)
        answer = _WRAPPER_TAGS.sub("", answer).strip()
        return _response(200, {"answer": answer, "sessionId": session_id})
    except Exception as e:  # noqa: BLE001 - don't leak stack traces to the browser
        return _response(500, {
            "error": "The assistant could not complete the request.",
            "detail": type(e).__name__,
        })
