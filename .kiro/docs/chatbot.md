# Chatbot — Bedrock + DynamoDB scheduling assistant

## What

A floating chat widget in the web app that lets students ask natural-language
questions about the De Anza schedule, pathway requirements, and course
conflicts. Backed by an AWS Lambda that reads three DynamoDB tables and calls
Amazon Bedrock (Converse API) with the data as context.

## Why

Students and schedulers need quick answers to questions like "which classes have
no room?", "what conflicts exist in my pathway this quarter?", or "is MATH 1A
offered online in winter?" — without manually cross-referencing tables. An AI
assistant backed by live data answers these instantly.

## Architecture

```
React ChatWidget  ──POST /chat──►  API Gateway (REST, no API key)
                                        │
                                        ▼
                                  ChatFunction (Lambda, Node.js 22)
                                        │
                          ┌─────────────┼─────────────┐
                          ▼             ▼             ▼
              deanza-class-schedule  deanza-pathway-  deanza-pathways-
                                    conflicts         normalized
                          │             │             │
                          └──── summarized ───────────┘
                                        │
                                        ▼
                              Amazon Bedrock (Converse API)
                              amazon.nova-lite-v1:0
                                        │
                                        ▼
                              { answer } → React
```

## Key components

| File | Role |
|------|------|
| `scripts/chatbot/index.mjs` | Lambda handler: scans DynamoDB on cold start, builds system prompt, calls Bedrock |
| `scripts/chatbot/package.json` | Node.js dependencies (AWS SDK for Bedrock + DynamoDB) |
| `infra/template.yaml` | SAM template — ChatFunction resource, IAM policies, /chat route |
| `web-app/src/components/ChatWidget.jsx` | React popup: toggle button, message list, input form |
| `web-app/src/styles.css` | Chat widget styles (bottom of file) |

## Data strategy

The Lambda scans all three tables **once per cold start** and caches the result.
The raw data is summarized before insertion into the system prompt:

- **Schedule:** grouped by term → course → section count, modalities, enrollment/capacity
- **Conflicts:** per pathway summary with sample conflict pairs
- **Pathways:** program name, credential, courses per quarter

This keeps the prompt within Bedrock's context window while giving the model
enough detail to answer specific questions.

## Deployment

Prerequisites: AWS SAM CLI, Node.js 22, Bedrock model access enabled in your
region.

```bash
cd infra
sam build
sam deploy --guided
```

Guided deploy answers:
- Stack name: `deanza-schedule-services` (or your existing stack)
- Region: where Bedrock + your model are available (us-west-2)
- BedrockModelId: `amazon.nova-lite-v1:0` (or another Converse-compatible model)
- Allow IAM role creation: Y

After deploy, copy the `ChatEndpoint` output URL and set it in `.env`:

```
VITE_CHAT_API_URL=https://XXXXXX.execute-api.us-west-2.amazonaws.com/prod/chat
```

Then restart the dev server or rebuild.

## Security notes

- The Lambda uses its IAM role to call Bedrock — no AWS keys in the browser.
- The /chat endpoint has no API key (public) since the underlying data is
  published schedule info. Add Cognito or an API key before production.
- CORS is set to `*` for development; tighten `ALLOWED_ORIGIN` before prod.
- Chat history is browser-only (no persistence). Last 12 messages sent per
  request.

## Decisions & alternatives

- **Cold-start scan vs. per-request query:** Scanning on cold start adds ~2-4s
  to the first request but makes subsequent responses fast. Acceptable for a
  prototype; for production, move to Bedrock Knowledge Bases with S3 source
  documents for proper RAG.
- **Summarization vs. full data:** Full table dumps exceed Bedrock's context
  window. Summarizing trades some granularity for reliability. Students can ask
  follow-ups for specifics.
- **Node.js vs. Python:** Chose Node.js 22 to match the friend's existing
  chatbot pattern and because the AWS SDK v3 for JS has strong Bedrock support.
- **REST API (not HTTP API):** Reuses the existing ConflictApi gateway which
  needs REST for API key + usage plans. The chat route opts out of the key
  requirement.

## Gotchas

- First request after a cold start is slow (DynamoDB scans + Bedrock inference).
  Subsequent requests in the same Lambda instance are fast.
- If the DynamoDB tables are empty or don't exist, the Lambda returns a clear
  error message rather than crashing.
- The `VITE_CHAT_API_URL` env var must be set at **build time** for Vite to
  embed it. Changing it requires restarting the dev server or rebuilding.
- Model token limits: if the summarized data grows too large (more terms loaded,
  more pathways), the system prompt may need further compression or a move to
  RAG.
