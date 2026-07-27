"""Project Processing Agent.

Runs in the background after a project document is uploaded. A tool-calling
agent (not a single prompt) analyzes the extracted text:

  - read_document_chunk / search_document — long documents are chunked, so
    the agent reads and searches instead of losing everything past a
    truncation limit
  - list_known_domains_and_technologies — keeps naming consistent with what
    is already in the repository
  - save_project_metadata — the required final action; it VALIDATES the
    payload and returns errors, so the agent self-corrects and retries

If the agent loop fails outright, a single structured-call fallback still
produces metadata so an upload is never left unprocessed.

Failure policy: never raises — all errors land on the project doc as
processing_status="failed" with a human-readable processing_error.
"""

import json
import asyncio
import logging
from datetime import datetime
from bson import ObjectId
from app.config import get_settings
from app.database import projects_collection
from app.services.ai_service import _get_groq, _get_openai
from app.services.document_service import extract_text, ExtractionError

logger = logging.getLogger(__name__)
settings = get_settings()

CHUNK_SIZE = 6000        # chars per document chunk served to the agent
MAX_AGENT_ROUNDS = 8     # tool-loop budget before falling back
MAX_TEXT_CHARS = 24000   # context cap for the single-call fallback only

# One canonical list shared by project classification and client matching so
# domains group consistently in queries and in the knowledge graph.
CANONICAL_DOMAINS = [
    "Healthcare",
    "Banking & Finance",
    "Insurance",
    "Retail & E-Commerce",
    "Logistics & Supply Chain",
    "Manufacturing",
    "Education",
    "Real Estate",
    "Travel & Hospitality",
    "Media & Entertainment",
    "Energy & Utilities",
    "Telecom",
    "Government",
    "HR & Recruitment",
    "Legal",
    "Other",
]

METADATA_FIELDS_SPEC = """{
  "title": "a short, clean project title",
  "domain": "the single primary business domain (canonical list only)",
  "related_domains": ["0-3 other closely related canonical domains"],
  "technologies": ["specific technologies, frameworks, tools mentioned"],
  "summary": "3-4 sentence summary of the project",
  "key_features": ["the main features/capabilities delivered"],
  "business_problem": "the business problem the project addressed",
  "solution_provided": "how the project solved that problem",
  "ai_ml_components": ["AI/ML models, techniques or components used (empty list if none)"],
  "tech_stack": {
    "frontend": ["..."], "backend": ["..."], "database": ["..."],
    "cloud_devops": ["..."], "other": ["..."]
  },
  "additional_metadata": {
    "client_industry": "if mentioned, else empty string",
    "team_size": "if mentioned, else empty string",
    "duration": "if mentioned, else empty string",
    "integrations": ["third-party integrations if mentioned"]
  }
}"""

AGENT_SYSTEM_PROMPT = f"""You are the Project Processing Agent for our internal project knowledge base. A project document has been uploaded and its raw text extracted. Your mission: analyze it and persist structured metadata.

You have tools:
- read_document_chunk: the document is split into chunks; only chunk 1 is given to you. Read further chunks before concluding — never guess about parts you have not read.
- search_document: find lines mentioning a specific fact (e.g. "team", "duration", "tech stack", "integration").
- list_known_domains_and_technologies: the canonical domain list and technology names already in our repository. Call this before saving so naming stays consistent (e.g. reuse "React" rather than introducing "ReactJS").
- save_project_metadata: REQUIRED final step. It validates your payload; if it returns errors, fix them and call it again.

The metadata shape to save:
{METADATA_FIELDS_SPEC}

Rules:
- "domain" and every "related_domains" entry MUST come from the canonical domain list.
- Base everything strictly on the document. Use empty strings/lists for facts not present — never invent.
- Work autonomously; there is no user to ask. Finish by calling save_project_metadata successfully."""

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_document_chunk",
            "description": "Read one chunk of the uploaded document's text. Chunks are 1-based.",
            "parameters": {
                "type": "object",
                "properties": {"index": {"type": "integer", "description": "Chunk number, 1-based"}},
                "required": ["index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_document",
            "description": "Case-insensitive search across the whole document. Returns matching lines.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Keyword or phrase to search for"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_known_domains_and_technologies",
            "description": "Get the canonical business-domain list and the technology names already used by projects in our repository.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_project_metadata",
            "description": "Validate and persist the final structured metadata for this project. Returns {saved: true} or {saved: false, errors: [...]} to fix.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "domain": {"type": "string"},
                    "related_domains": {"type": "array", "items": {"type": "string"}},
                    "technologies": {"type": "array", "items": {"type": "string"}},
                    "summary": {"type": "string"},
                    "key_features": {"type": "array", "items": {"type": "string"}},
                    "business_problem": {"type": "string"},
                    "solution_provided": {"type": "string"},
                    "ai_ml_components": {"type": "array", "items": {"type": "string"}},
                    "tech_stack": {"type": "object"},
                    "additional_metadata": {"type": "object"},
                },
                "required": ["title", "domain", "summary"],
            },
        },
    },
]


async def _chat(messages: list, tools: list = None, provider: str = None, **kwargs):
    """Provider switch shared by the agent loop and the fallback call."""
    provider = provider or settings.ai_provider
    params = dict(messages=messages, temperature=0.2, max_tokens=2000, **kwargs)
    if tools:
        params["tools"] = tools
        params["tool_choice"] = "auto"
    if provider == "groq":
        return await _get_groq().chat.completions.create(
            model="llama-3.3-70b-versatile", **params
        )
    return await _get_openai().chat.completions.create(model="gpt-4o", **params)


# ---------------------------------------------------------------- agent loop

def _validate_metadata(data: dict) -> list[str]:
    errors = []
    if not str(data.get("title") or "").strip():
        errors.append("'title' is required and must be a non-empty string")
    if not str(data.get("summary") or "").strip():
        errors.append("'summary' is required and must be a non-empty string")
    domain = data.get("domain")
    if domain not in CANONICAL_DOMAINS:
        errors.append(
            f"'domain' must be exactly one of the canonical domains, got {domain!r}. "
            f"Canonical: {', '.join(CANONICAL_DOMAINS)}"
        )
    bad = [d for d in (data.get("related_domains") or []) if d not in CANONICAL_DOMAINS]
    if bad:
        errors.append(f"'related_domains' entries not in the canonical list: {bad}")
    return errors


async def _execute_agent_tool(name: str, args: dict, chunks: list, full_text: str, result_holder: dict) -> str:
    if name == "read_document_chunk":
        idx = int(args.get("index", 1))
        if idx < 1 or idx > len(chunks):
            return json.dumps({"error": f"Chunk {idx} does not exist. Valid: 1..{len(chunks)}"})
        return json.dumps({"chunk": idx, "of": len(chunks), "text": chunks[idx - 1]})

    if name == "search_document":
        query = str(args.get("query", "")).lower().strip()
        if not query:
            return json.dumps({"error": "query is required"})
        hits = [
            line.strip()[:250]
            for line in full_text.split("\n")
            if query in line.lower()
        ][:12]
        return json.dumps({"matches": hits or [], "note": "" if hits else "No matches found."})

    if name == "list_known_domains_and_technologies":
        known_tech = await projects_collection.distinct(
            "metadata.technologies", {"processing_status": "completed"}
        )
        return json.dumps({
            "canonical_domains": CANONICAL_DOMAINS,
            "known_technologies": sorted(known_tech)[:100],
        })

    if name == "save_project_metadata":
        errors = _validate_metadata(args)
        if errors:
            return json.dumps({"saved": False, "errors": errors})
        result_holder["metadata"] = _normalize_metadata(args)
        return json.dumps({"saved": True})

    return json.dumps({"error": f"Unknown tool: {name}"})


async def _run_agent_extraction(text: str, file_name: str) -> tuple[dict, list]:
    """Tool-calling agent loop. Returns (metadata, trace) or raises."""
    chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
    result_holder: dict = {}
    trace: list = []

    messages = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Document: {file_name}\n"
                f"Total chunks: {len(chunks)}\n\n"
                f"--- CHUNK 1 of {len(chunks)} ---\n{chunks[0]}\n\n"
                "Analyze this project and save its metadata."
            ),
        },
    ]

    for _ in range(MAX_AGENT_ROUNDS):
        response = await _chat(messages, tools=AGENT_TOOLS)
        msg = response.choices[0].message

        if not msg.tool_calls:
            # The agent must act through tools — nudge it back on track
            messages.append({"role": "assistant", "content": msg.content or ""})
            messages.append({
                "role": "user",
                "content": "Use your tools. Finish by calling save_project_metadata with the complete metadata.",
            })
            continue

        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
        })
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = await _execute_agent_tool(
                tc.function.name, args, chunks, text, result_holder
            )
            step = tc.function.name
            if step == "save_project_metadata" and not result_holder.get("metadata"):
                step += " (validation failed, retrying)"
            trace.append(step)
            logger.info(f"[PROJECT AGENT] Tool: {step}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        if result_holder.get("metadata"):
            return result_holder["metadata"], trace

    raise RuntimeError(f"Agent did not save metadata within {MAX_AGENT_ROUNDS} rounds")


# ---------------------------------------------------------------- fallback

FALLBACK_PROMPT = f"""You are an expert business analyst. Analyze the following project document and extract structured information about the project.

The primary domain and related domains MUST be chosen from this exact list:
{", ".join(CANONICAL_DOMAINS)}

Return a JSON object with exactly these fields:
{METADATA_FIELDS_SPEC}

Base everything strictly on the document content. Use empty strings/lists for anything not mentioned."""


async def _single_call_extraction(text: str) -> dict:
    """Resilience fallback if the agent loop fails: one structured call."""
    messages = [
        {"role": "system", "content": FALLBACK_PROMPT},
        {"role": "user", "content": f"Project document:\n\n{text[:MAX_TEXT_CHARS]}\n\nExtract the structured information:"},
    ]
    response = await _chat(messages, response_format={"type": "json_object"})
    return _normalize_metadata(json.loads(response.choices[0].message.content))


# ---------------------------------------------------------------- pipeline

def _normalize_metadata(data: dict) -> dict:
    """Coerce LLM/tool output into a predictable shape."""
    def as_list(v):
        if isinstance(v, list):
            return [str(x) for x in v if x]
        return [str(v)] if v else []

    domain = str(data.get("domain") or "Other")
    if domain not in CANONICAL_DOMAINS:
        domain = "Other"
    related = [d for d in as_list(data.get("related_domains")) if d in CANONICAL_DOMAINS and d != domain]

    stack = data.get("tech_stack") or {}
    if not isinstance(stack, dict):
        stack = {}

    extra = data.get("additional_metadata") or {}
    if not isinstance(extra, dict):
        extra = {}

    return {
        "title": str(data.get("title") or ""),
        "domain": domain,
        "related_domains": related,
        "technologies": as_list(data.get("technologies")),
        "summary": str(data.get("summary") or ""),
        "key_features": as_list(data.get("key_features")),
        "business_problem": str(data.get("business_problem") or ""),
        "solution_provided": str(data.get("solution_provided") or ""),
        "ai_ml_components": as_list(data.get("ai_ml_components")),
        "tech_stack": {
            "frontend": as_list(stack.get("frontend")),
            "backend": as_list(stack.get("backend")),
            "database": as_list(stack.get("database")),
            "cloud_devops": as_list(stack.get("cloud_devops")),
            "other": as_list(stack.get("other")),
        },
        "additional_metadata": extra,
    }


async def process_project(project_id: str) -> None:
    """Extract text, run the processing agent, and store the result."""
    oid = ObjectId(project_id)
    project = await projects_collection.find_one({"_id": oid})
    if not project:
        logger.error(f"[PROJECT AGENT] Project {project_id} not found")
        return

    try:
        # Blocking parsers run off the event loop
        text = await asyncio.to_thread(
            extract_text, project["file_path"], project["file_type"]
        )
        await projects_collection.update_one(
            {"_id": oid}, {"$set": {"extracted_text": text}}
        )

        trace: list = []
        try:
            metadata, trace = await _run_agent_extraction(text, project["file_name"])
            method = "agent"
        except Exception as e:
            logger.warning(f"[PROJECT AGENT] Agent loop failed for {project_id}, falling back: {e}")
            metadata = await _single_call_extraction(text)
            method = "single_call_fallback"

        name = metadata["title"] or project["name"]
        await projects_collection.update_one(
            {"_id": oid},
            {"$set": {
                "name": name,
                "metadata": metadata,
                "extraction_method": method,
                "agent_trace": trace,
                "processing_status": "completed",
                "processing_error": None,
                "updated_at": datetime.utcnow(),
            }},
        )
        logger.info(
            f"[PROJECT AGENT] Processed '{name}' via {method} → domain={metadata['domain']}"
        )

        # A new project may now be the best match for already-enriched clients
        from app.services.client_agent import refresh_matches_for_project
        await refresh_matches_for_project(project_id)

    except ExtractionError as e:
        logger.warning(f"[PROJECT AGENT] Extraction failed for {project_id}: {e}")
        await _mark_failed(oid, str(e))
    except Exception as e:
        logger.error(f"[PROJECT AGENT] Failed for {project_id}: {e}")
        await _mark_failed(oid, f"AI processing failed: {e}")


async def _mark_failed(oid: ObjectId, message: str) -> None:
    await projects_collection.update_one(
        {"_id": oid},
        {"$set": {
            "processing_status": "failed",
            "processing_error": message,
            "updated_at": datetime.utcnow(),
        }},
    )
