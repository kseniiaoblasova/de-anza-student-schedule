/**
 * De Anza Chatbot Lambda — Bedrock + DynamoDB
 *
 * Queries three DynamoDB tables on cold start, builds a system prompt with
 * schedule/conflict/pathway data, then forwards user messages to Amazon Bedrock
 * (Converse API). Designed for student-facing questions like "which classes
 * have no room?", "what conflicts exist for my pathway?", etc.
 *
 * Architecture:
 *   React chat popup → API Gateway HTTP API → this Lambda → Bedrock Converse
 *                                                         ← DynamoDB (cold start cache)
 */

import {
  BedrockRuntimeClient,
  ConverseCommand,
} from "@aws-sdk/client-bedrock-runtime";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import {
  DynamoDBDocumentClient,
  ScanCommand,
} from "@aws-sdk/lib-dynamodb";

// --- Configuration from environment variables ---
const REGION = process.env.AWS_REGION || "us-west-2";
const MODEL_ID = process.env.BEDROCK_MODEL_ID || "amazon.nova-lite-v1:0";
const ALLOWED_ORIGIN = process.env.ALLOWED_ORIGIN || "*";
const SCHEDULE_TABLE = process.env.SCHEDULE_TABLE || "deanza-class-schedule";
const CONFLICTS_TABLE = process.env.CONFLICTS_TABLE || "deanza-pathway-conflicts";
const PATHWAYS_TABLE = process.env.PATHWAYS_TABLE || "deanza-pathways-normalized";

// --- AWS clients ---
const bedrockClient = new BedrockRuntimeClient({ region: REGION });
const ddbClient = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }));

// --- Data cache (loaded once per cold start) ---
let cachedData = null;

/**
 * Scan an entire DynamoDB table (handles pagination).
 */
async function scanFullTable(tableName) {
  const items = [];
  let lastKey = undefined;

  do {
    const resp = await ddbClient.send(new ScanCommand({
      TableName: tableName,
      ExclusiveStartKey: lastKey,
    }));
    items.push(...(resp.Items || []));
    lastKey = resp.LastEvaluatedKey;
  } while (lastKey);

  return items;
}

/**
 * Summarize schedule data to fit within Bedrock context limits.
 * Instead of sending every section row, aggregate into useful summaries.
 */
function summarizeSchedule(scheduleRows) {
  // Group by term, then by course — count sections and extract key info
  const byTerm = {};
  for (const row of scheduleRows) {
    const term = row.term_code || "unknown";
    const course = row.course || `${row.subject || ""} ${row.number || ""}`.trim();
    if (!byTerm[term]) byTerm[term] = {};
    if (!byTerm[term][course]) byTerm[term][course] = { sections: 0, methods: new Set(), seats: [] };
    byTerm[term][course].sections++;
    if (row.instruction_method) byTerm[term][course].methods.add(row.instruction_method);
    // Track enrollment capacity info if available
    if (row.enrolled !== undefined || row.capacity !== undefined) {
      byTerm[term][course].seats.push({
        crn: row.crn,
        enrolled: row.enrolled,
        capacity: row.capacity,
        waitlist: row.waitlist,
      });
    }
  }

  // Convert sets to arrays for JSON serialization
  for (const term of Object.values(byTerm)) {
    for (const course of Object.values(term)) {
      course.methods = [...course.methods];
    }
  }

  return byTerm;
}

/**
 * Summarize conflict data: per pathway, how many quarters have conflicts and totals.
 */
function summarizeConflicts(conflictRows) {
  const byPathway = {};
  for (const row of conflictRows) {
    const pid = row.pathway_id || "unknown";
    if (!byPathway[pid]) {
      byPathway[pid] = {
        program_name: row.program_name || "",
        quarters_with_conflicts: 0,
        total_conflicts: 0,
        details: [],
      };
    }
    if (row.conflict_count > 0) {
      byPathway[pid].quarters_with_conflicts++;
      byPathway[pid].total_conflicts += row.conflict_count;
      // Include up to 3 sample conflicts per quarter for context
      const samples = (row.conflicts || []).slice(0, 3).map(c => ({
        course_a: c.course_a,
        course_b: c.course_b,
        days: c.overlap?.days,
        time_a: c.overlap?.time_a,
        time_b: c.overlap?.time_b,
      }));
      byPathway[pid].details.push({
        quarter: row.quarter_key,
        conflict_count: row.conflict_count,
        samples,
      });
    }
  }
  return byPathway;
}

/**
 * Summarize pathways: program name, courses per quarter, credential type.
 */
function summarizePathways(pathwayRows) {
  return pathwayRows.map(p => ({
    pathway_id: p.pathway_id,
    program_name: p.program_name,
    credential_type: p.credential_type,
    village: p.village,
    // Flatten normalized courses per quarter for quick reference
    quarters: Object.entries(p.years || {}).flatMap(([year, quarters]) =>
      Object.entries(quarters).map(([quarter, data]) => ({
        period: `${year}/${quarter}`,
        courses: data.normalized_courses || [],
      }))
    ).filter(q => q.courses.length > 0),
  }));
}

/**
 * Load and cache all DynamoDB data on cold start.
 */
async function loadData() {
  if (cachedData) return cachedData;

  console.log("Cold start: loading DynamoDB tables...");
  const [scheduleRows, conflictRows, pathwayRows] = await Promise.all([
    scanFullTable(SCHEDULE_TABLE),
    scanFullTable(CONFLICTS_TABLE),
    scanFullTable(PATHWAYS_TABLE),
  ]);
  console.log(`Loaded: ${scheduleRows.length} schedule rows, ${conflictRows.length} conflict rows, ${pathwayRows.length} pathway rows`);

  // Summarize to keep the prompt within Bedrock's context window
  cachedData = {
    schedule: summarizeSchedule(scheduleRows),
    conflicts: summarizeConflicts(conflictRows),
    pathways: summarizePathways(pathwayRows),
    stats: {
      total_schedule_rows: scheduleRows.length,
      total_conflict_records: conflictRows.length,
      total_pathways: pathwayRows.length,
    },
  };

  return cachedData;
}

// --- System prompt template ---
function buildSystemPrompt(data) {
  return `You are the De Anza Student-Centered Scheduling Assistant.

You help students, schedulers, and administrators understand the De Anza College class schedule, pathway requirements, and scheduling conflicts.

CAPABILITIES:
- Answer questions about course availability, section counts, and modalities
- Identify scheduling conflicts between courses in a pathway
- Explain which courses are required for specific program pathways
- Report on enrollment capacity (when data is available)
- Help students understand their options when courses conflict

RULES:
1. Use the supplied data as your source of truth.
2. Be concise and student-friendly. Use plain language.
3. When listing courses or conflicts, format them clearly.
4. If the data does not answer a question, say so clearly and suggest what info is needed.
5. Do not invent statistics or enrollment numbers.
6. When discussing conflicts, explain what it means practically for a student.

DATA SUMMARY:
- ${data.stats.total_pathways} program pathways loaded
- ${data.stats.total_schedule_rows} class schedule rows across all terms
- ${data.stats.total_conflict_records} pathway-quarter conflict records

SCHEDULE DATA (courses grouped by term, with section counts and modalities):
${JSON.stringify(data.schedule, null, 0)}

PATHWAY CONFLICT SUMMARY (pathways with scheduling conflicts):
${JSON.stringify(data.conflicts, null, 0)}

PATHWAY REQUIREMENTS (programs with their required courses per quarter):
${JSON.stringify(data.pathways, null, 0)}`;
}

// --- HTTP response helpers ---
const corsHeaders = {
  "content-type": "application/json",
  "access-control-allow-origin": ALLOWED_ORIGIN,
  "access-control-allow-headers": "content-type",
  "access-control-allow-methods": "OPTIONS,POST",
};

function respond(statusCode, body) {
  return { statusCode, headers: corsHeaders, body: JSON.stringify(body) };
}

/**
 * Normalize incoming messages to the Bedrock Converse format.
 * Keep last 12 messages, enforce alternating user/assistant pattern.
 */
function normalizeMessages(messages) {
  if (!Array.isArray(messages)) return [];
  return messages
    .slice(-12)
    .filter(m => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string" && m.content.trim().length > 0)
    .map(m => ({ role: m.role, content: [{ text: m.content.trim().slice(0, 6000) }] }));
}

// --- Lambda handler ---
export const handler = async (event) => {
  // CORS preflight
  if (event?.requestContext?.http?.method === "OPTIONS") {
    return respond(204, {});
  }

  try {
    // Parse request body
    const body = event?.body ? JSON.parse(event.body) : {};
    const messages = normalizeMessages(body.messages);

    if (messages.length === 0 || messages.at(-1)?.role !== "user") {
      return respond(400, { error: "Send at least one user message in the messages array." });
    }

    // Load DynamoDB data (cached after first invocation)
    const data = await loadData();
    const systemPrompt = buildSystemPrompt(data);

    // Call Bedrock Converse API
    const command = new ConverseCommand({
      modelId: MODEL_ID,
      system: [{ text: systemPrompt }],
      messages,
      inferenceConfig: {
        maxTokens: 1200,
        temperature: 0.2,
        topP: 0.9,
      },
    });

    const result = await bedrockClient.send(command);
    const content = result?.output?.message?.content || [];
    const answer = content
      .filter(item => typeof item?.text === "string")
      .map(item => item.text)
      .join("\n")
      .trim();

    if (!answer) {
      throw new Error("Bedrock returned an empty response.");
    }

    return respond(200, { answer, modelId: MODEL_ID, usage: result.usage || null });
  } catch (error) {
    console.error("Chat request failed:", error);

    const message = error?.name === "AccessDeniedException"
      ? "Bedrock access was denied. Check the Lambda role, model access, model ID, and AWS Region."
      : error?.name === "ResourceNotFoundException"
        ? "A DynamoDB table was not found. Ensure all tables are deployed."
        : "The chatbot could not complete the request.";

    return respond(500, {
      error: message,
      details: process.env.DEBUG_ERRORS === "true" ? String(error) : undefined,
    });
  }
};
