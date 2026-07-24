"""
De Anza scheduling assistant — a Strands agent for Bedrock AgentCore Runtime.

The agent answers student/scheduler questions about the published class schedule,
program pathways, and scheduling conflicts. Instead of loading whole tables into
the prompt (which overflowed the context in an earlier attempt), it exposes
DynamoDB reads as tools and lets the model fetch only what each question needs.

Three tables back the tools:
  - deanza-pathways-normalized  (pathway_id)                -> required courses per quarter
  - deanza-pathway-conflicts    (pathway_id, quarter_key)   -> conflict pairs per quarter
  - deanza-class-schedule       (term_code, section_key)    -> the actual sections

Entry point is the BedrockAgentCoreApp `invoke` handler at the bottom.
"""

import os
import json
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr

from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# --- Configuration ---
REGION = os.environ.get("AWS_REGION", "us-west-2")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")

SCHEDULE_TABLE = os.environ.get("SCHEDULE_TABLE", "deanza-class-schedule")
CONFLICTS_TABLE = os.environ.get("CONFLICTS_TABLE", "deanza-pathway-conflicts")
PATHWAYS_TABLE = os.environ.get("PATHWAYS_TABLE", "deanza-pathways-normalized")

# Pathway (year, quarter) -> published schedule term_code. year_1 is AY2025-26,
# year_2 is AY2026-27; both are real terms loaded in deanza-class-schedule.
TERM_MAP = {
    ("year_1", "fall"): "202622", ("year_1", "winter"): "202632", ("year_1", "spring"): "202642",
    ("year_2", "fall"): "202722", ("year_2", "winter"): "202732", ("year_2", "spring"): "202742",
}

_dynamodb = boto3.resource("dynamodb", region_name=REGION)


# --- Serialization helpers ---
def _clean(obj):
    """Make DynamoDB items JSON-serializable (Decimal -> int/float) and drop the
    bulky raw payload that isn't useful to the model."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if k != "raw"}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


def _dumps(obj):
    return json.dumps(_clean(obj), separators=(",", ":"))


# --- Tools: pathway data ---
@tool
def list_pathways(name_contains: str = "") -> str:
    """List program pathways, optionally filtered by a substring of the program
    name (case-insensitive). Returns pathway_id, program_name, credential_type,
    and village for each match. Use this to find the pathway_id for a program
    before calling get_pathway_plan or get_pathway_conflicts.
    """
    table = _dynamodb.Table(PATHWAYS_TABLE)
    items, kwargs = [], {}
    while True:
        resp = table.scan(
            ProjectionExpression="pathway_id, program_name, credential_type, village",
            **kwargs,
        )
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    needle = name_contains.strip().lower()
    if needle:
        items = [i for i in items if needle in i.get("program_name", "").lower()]
    return _dumps(items[:40])


@tool
def get_pathway_plan(pathway_id: str) -> str:
    """Get the required courses for a pathway, organized by year and quarter.
    Pass a pathway_id obtained from list_pathways.
    """
    table = _dynamodb.Table(PATHWAYS_TABLE)
    item = table.get_item(Key={"pathway_id": pathway_id}).get("Item")
    if not item:
        return _dumps({"error": f"No pathway with id {pathway_id}"})

    # Flatten years -> quarters -> normalized course list for a compact answer.
    plan = []
    for year_key, quarters in (item.get("years") or {}).items():
        for quarter_key, data in quarters.items():
            courses = data.get("normalized_courses") or []
            if courses:
                plan.append({"period": f"{year_key}/{quarter_key}", "courses": courses})
    return _dumps({
        "pathway_id": pathway_id,
        "program_name": item.get("program_name"),
        "credential_type": item.get("credential_type"),
        "plan": plan,
    })


@tool
def get_pathway_conflicts(pathway_id: str) -> str:
    """Get precomputed scheduling conflicts for a pathway, per quarter. Returns
    the conflict count and sample conflicting course pairs (with overlapping days
    and times) for each quarter that has any.
    """
    table = _dynamodb.Table(CONFLICTS_TABLE)
    resp = table.query(KeyConditionExpression=Key("pathway_id").eq(pathway_id))
    out = []
    for item in resp.get("Items", []):
        if (item.get("conflict_count") or 0) > 0:
            samples = [
                {
                    "course_a": c.get("course_a"), "course_b": c.get("course_b"),
                    "days": (c.get("overlap") or {}).get("days"),
                    "time_a": (c.get("overlap") or {}).get("time_a"),
                    "time_b": (c.get("overlap") or {}).get("time_b"),
                }
                for c in (item.get("conflicts") or [])[:5]
            ]
            out.append({
                "quarter": item.get("quarter_key"),
                "term_code": item.get("term_code"),
                "conflict_count": item.get("conflict_count"),
                "samples": samples,
            })
    return _dumps({"pathway_id": pathway_id, "quarters_with_conflicts": out})


# --- Tools: class schedule ---
@tool
def find_course_sections(term_code: str, subject: str, number: str = "") -> str:
    """Find scheduled sections of a course in a term. term_code is one of
    202622 (Fall 2025), 202632 (Winter 2026), 202642 (Spring 2026),
    202722 (Fall 2026), 202732 (Winter 2027), 202742 (Spring 2027).
    subject is a department code like 'MATH' or 'CIS'; number is optional like
    'D001A.' (partial matches allowed). Returns meeting days/times, room,
    instructor, modality, and enrollment.
    """
    table = _dynamodb.Table(SCHEDULE_TABLE)
    filt = Attr("subject").eq(subject.upper())
    if number:
        filt = filt & Attr("number").begins_with(number)

    items, kwargs = [], {}
    while True:
        resp = table.query(
            KeyConditionExpression=Key("term_code").eq(term_code),
            FilterExpression=filt,
            **kwargs,
        )
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp or len(items) >= 60:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    sections = [{
        "course": i.get("course"), "crn": i.get("crn"), "section": i.get("section"),
        "days": i.get("meeting_days"), "times": i.get("meeting_times"),
        "room": i.get("room"), "building": i.get("building"),
        "method": i.get("instruction_method"), "instructor": i.get("instructor"),
        "enrolled": i.get("total_enroll"), "capacity": i.get("max_enroll"),
    } for i in items[:60]]
    return _dumps({"term_code": term_code, "count": len(sections), "sections": sections})


@tool
def find_sections_without_room(term_code: str, limit: int = 40) -> str:
    """Find in-person sections in a term that have no room assigned (room blank
    or 'TBA'). Useful for questions like 'which classes have no room?'. Online
    sections are excluded since they legitimately have no room.
    """
    table = _dynamodb.Table(SCHEDULE_TABLE)
    items, kwargs = [], {}
    while True:
        resp = table.query(KeyConditionExpression=Key("term_code").eq(term_code), **kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    # No-room = blank/TBA room, and not an online modality (online has no room by design).
    hits = []
    for i in items:
        room = (i.get("room") or "").strip().upper()
        method = (i.get("instruction_method") or "").strip().upper()
        online = method in ("ONL", "OL", "ONLINE", "W", "WEB")
        if (not room or room == "TBA") and not online:
            hits.append({
                "course": i.get("course"), "crn": i.get("crn"),
                "days": i.get("meeting_days"), "times": i.get("meeting_times"),
                "method": i.get("instruction_method"), "instructor": i.get("instructor"),
            })
        if len(hits) >= limit:
            break
    return _dumps({"term_code": term_code, "count": len(hits), "sections_without_room": hits})


# --- Agent definition ---
SYSTEM_PROMPT = """You are the De Anza Student-Centered Scheduling Assistant.

You help students, schedulers, and administrators with questions about the De Anza
College class schedule, program pathways, and scheduling conflicts.

Use your tools to look up data — never guess course offerings, times, or conflicts.
Typical flow:
- To answer about a program's requirements or conflicts, first call list_pathways to
  find the pathway_id, then get_pathway_plan or get_pathway_conflicts.
- For questions about specific class offerings, times, rooms, or modality, use
  find_course_sections with the right term_code.
- For "which classes have no room" style questions, use find_sections_without_room.

Term codes: 202622=Fall 2025, 202632=Winter 2026, 202642=Spring 2026,
202722=Fall 2026, 202732=Winter 2027, 202742=Spring 2027.

Be concise and student-friendly. When you list courses or sections, format them
clearly. If a tool returns nothing, say so plainly and suggest what to try. Do not
invent enrollment numbers or times."""

_model = BedrockModel(model_id=MODEL_ID, region_name=REGION)

agent = Agent(
    model=_model,
    system_prompt=SYSTEM_PROMPT,
    tools=[
        list_pathways,
        get_pathway_plan,
        get_pathway_conflicts,
        find_course_sections,
        find_sections_without_room,
    ],
)

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload):
    """AgentCore Runtime entry point. Expects {"prompt": "<user question>"} and
    returns {"result": "<assistant answer>"}."""
    prompt = (payload or {}).get("prompt", "").strip()
    if not prompt:
        return {"result": "Ask me about De Anza pathways, class schedules, or conflicts."}
    result = agent(prompt)
    return {"result": str(result)}


if __name__ == "__main__":
    app.run()
