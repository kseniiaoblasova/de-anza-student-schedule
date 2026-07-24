# AgentCore Chatbot — LLM scheduling assistant

## What

An LLM-backed chat assistant that answers natural-language questions about the
De Anza class schedule, program pathways, and scheduling conflicts. It replaces
the earlier no-LLM retrieval widget with a Bedrock AgentCore agent that reads the
three DynamoDB tables through tool calls.

## Why

The first LLM attempt stuffed whole tables into the prompt and overflowed the
model's context (25k+ schedule rows). The fix is **tool use**: the model calls a
tool, the tool runs a targeted DynamoDB query, and only the matching rows come
back. The prompt stays small regardless of table size, and the assistant
understands free-form questions the old 3-intent parser couldn't.

## Architecture

```
React ChatWidget
   │  POST { message, sessionId }
   ▼
API Gateway HTTP API (km7w10xv4e)      ← public; Lambda Function URLs are SCP-blocked in this account
   │
   ▼
deanza-agent-proxy (Lambda, Python)    ← invoke_agent_runtime; strips <thinking>/<response>; CORS
   │
   ▼
AgentCore Runtime  (deanza_scheduler)  ← Strands agent + Bedrock (amazon.nova-lite-v1:0) + STM memory
   │  tool calls
   ├─ list_pathways / get_pathway_plan / get_pathway_conflicts   → deanza-pathways-normalized, deanza-pathway-conflicts
   └─ find_course_sections / find_sections_without_room          → deanza-class-schedule
```

## Components

| Piece | Where | Notes |
|-------|-------|-------|
| Agent | `agentcore/agent.py` | Strands `Agent` with 5 `@tool` DynamoDB queries; entrypoint returns `{"result": ...}` |
| Agent deps | `agentcore/requirements.txt` | bedrock-agentcore, strands-agents, boto3 |
| Toolkit config | `agentcore/.bedrock_agentcore.yaml` | agent name, ECR, execution role, memory (committed) |
| Proxy Lambda | `agentcore/proxy/lambda_function.py` | browser-facing; calls the runtime, cleans output |
| Runtime IAM | role `AmazonBedrockAgentCoreSDKRuntime-us-west-2-7740ab71bf` | auto-created + inline `deanza-dynamodb-read` |
| Proxy IAM | role `deanza-agent-proxy-role` | basic exec + `bedrock-agentcore:InvokeAgentRuntime` |
| Frontend client | `web-app/src/chat/chatAgent.js` | `ask()` + page-lifetime session id |
| Widget | `web-app/src/components/ChatWidget.jsx` | imports `chatAgent` (was `chatEngine`) |
| Endpoint config | `web-app/src/config.js` | `CHAT_API_URL` (override `VITE_CHAT_API_URL`) |

Public endpoint: `https://km7w10xv4e.execute-api.us-west-2.amazonaws.com/`
Agent ARN: `arn:aws:bedrock-agentcore:us-west-2:374894298498:runtime/deanza_scheduler-LZoEXF69zV`

## Deploying / redeploying

Agent (from `agentcore/`, needs the starter toolkit installed):

```powershell
# UTF-8 env vars avoid a Windows console crash on the toolkit's emoji output
$env:AWS_PROFILE="deanza"; $env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"
agentcore launch          # cross-builds ARM64 via CodeBuild (no local Docker) and deploys
```

Proxy Lambda (from `agentcore/proxy/`):

```powershell
pip install boto3 -t build --upgrade      # bundle a recent boto3 (Lambda's is too old for bedrock-agentcore)
Copy-Item lambda_function.py build\ -Force
Compress-Archive build\* proxy.zip -Force
aws lambda update-function-code --function-name deanza-agent-proxy --zip-file fileb://proxy.zip --profile deanza --region us-west-2
```

## Decisions & alternatives

- **AgentCore Runtime + Strands over a plain Converse Lambda.** Chosen because
  the user asked for AgentCore and it gives managed session memory + observability.
  A single Converse+tool-use Lambda was the fallback if AgentCore was blocked.
- **CodeBuild build (no local Docker).** The machine has no Docker and AgentCore
  needs an ARM64 image; the toolkit's default CodeBuild path builds in the cloud.
- **API Gateway instead of a Lambda Function URL.** Function URLs with auth NONE
  return 403 here — an org SCP blocks unauthenticated function URLs. The existing
  `/plan` REST API proved API Gateway is allowed, so the proxy is fronted by an
  HTTP API instead.
- **Proxy Lambda over calling the runtime from the browser.** AgentCore Runtime
  needs SigV4/IAM auth; browsers can't hold credentials, so a keyless proxy signs
  the call server-side.
- **Tools do queries, not scans of everything.** Directly solves the token
  overflow that killed the earlier attempt.

## Gotchas

- **Windows + toolkit emoji crash.** `agentcore launch/invoke` throws a cp1252
  `UnicodeEncodeError` unless `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` are set.
- **Lambda's built-in boto3 is too old** for the `bedrock-agentcore` client — the
  proxy must bundle a current boto3 in its zip.
- **Function URLs are blocked** (SCP); always front public Lambdas with API Gateway
  in this account.
- **Execution role needs DynamoDB access** — the toolkit's auto-created runtime
  role only covers Bedrock; the inline `deanza-dynamodb-read` policy was added.
- **`find_course_sections` caps at 60 rows**, so "how many sections" counts can be
  capped — it's meant for listing, not exact totals.
- **Nova emits `<thinking>`/`<response>` tags**; the proxy strips them before
  returning to the browser.
- **Cold starts are slow** (agent container + model); the first question can take
  20-30s. The proxy Lambda timeout is 90s but API Gateway caps at 30s — a cold
  first call can occasionally time out, then succeed on retry.
- The old `web-app/src/chat/chatEngine.js` (no-LLM retrieval) is now unused but
  left in place; it still powers nothing and can be removed later.
