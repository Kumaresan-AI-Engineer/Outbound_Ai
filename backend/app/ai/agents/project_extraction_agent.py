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

import asyncio
import json
import logging
from datetime import datetime

from bson import ObjectId

from app.ai.prompts.project_extraction_prompts import (
    AGENT_TOOLS,
    build_agent_start_messages,
    build_fallback_messages,
)
from app.ai.providers.factory import get_provider
from app.ai.schemas.project_extraction import ProjectMetadata
from app.ai.tools import project_tools
from app.config import get_settings
from app.repositories.projects_repo import projects_repo
from app.services.document_service import ExtractionError, extract_text

logger = logging.getLogger(__name__)

CHUNK_SIZE = 6000  # chars per document chunk served to the agent
MAX_AGENT_ROUNDS = 8  # tool-loop budget before falling back
MAX_TEXT_CHARS = 24000  # context cap for the single-call fallback only


def _model_for(provider) -> str:
    settings = get_settings()
    return settings.groq_model if provider.name == "groq" else settings.openai_model


# ---------------------------------------------------------------- agent loop


async def _execute_agent_tool(
    name: str, args: dict, chunks: list, full_text: str, result_holder: dict
) -> str:
    if name == "read_document_chunk":
        return json.dumps(project_tools.read_document_chunk(chunks, int(args.get("index", 1))))

    if name == "search_document":
        return json.dumps(project_tools.search_document(full_text, str(args.get("query", ""))))

    if name == "list_known_domains_and_technologies":
        return json.dumps(await project_tools.list_known_domains_and_technologies())

    if name == "save_project_metadata":
        errors = project_tools.validate_metadata(args)
        if errors:
            return json.dumps({"saved": False, "errors": errors})
        result_holder["metadata"] = ProjectMetadata.model_validate(args)
        return json.dumps({"saved": True})

    return json.dumps({"error": f"Unknown tool: {name}"})


async def _run_agent_extraction(text: str, file_name: str) -> tuple[ProjectMetadata, list]:
    """Tool-calling agent loop. Returns (metadata, trace) or raises."""
    provider = get_provider()
    model = _model_for(provider)
    chunks = project_tools.chunk_text(text, CHUNK_SIZE)
    result_holder: dict = {}
    trace: list = []

    messages = build_agent_start_messages(file_name, len(chunks), chunks[0])

    for _ in range(MAX_AGENT_ROUNDS):
        response = await provider.complete(
            messages, model=model, temperature=0.2, max_tokens=2000, tools=AGENT_TOOLS
        )

        if not response.tool_calls:
            # The agent must act through tools — nudge it back on track
            messages.append({"role": "assistant", "content": response.content or ""})
            messages.append(
                {
                    "role": "user",
                    "content": "Use your tools. Finish by calling save_project_metadata with the complete metadata.",
                }
            )
            continue

        messages.append(
            {
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in response.tool_calls
                ],
            }
        )
        for tc in response.tool_calls:
            try:
                args = json.loads(tc.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = await _execute_agent_tool(tc.name, args, chunks, text, result_holder)
            step = tc.name
            if step == "save_project_metadata" and not result_holder.get("metadata"):
                step += " (validation failed, retrying)"
            trace.append(step)
            logger.info(f"[PROJECT AGENT] Tool: {step}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        if result_holder.get("metadata"):
            return result_holder["metadata"], trace

    raise RuntimeError(f"Agent did not save metadata within {MAX_AGENT_ROUNDS} rounds")


# ---------------------------------------------------------------- fallback


async def _single_call_extraction(text: str) -> ProjectMetadata:
    """Resilience fallback if the agent loop fails: one structured call."""
    provider = get_provider()
    messages = build_fallback_messages(text, MAX_TEXT_CHARS)
    return await provider.complete_structured(
        messages, ProjectMetadata, model=_model_for(provider), temperature=0.2, max_tokens=2000
    )


# ---------------------------------------------------------------- pipeline


async def process_project(project_id: str) -> None:
    """Extract text, run the processing agent, and store the result."""
    oid = ObjectId(project_id)
    project = await projects_repo.find_one({"_id": oid})
    if not project:
        logger.error(f"[PROJECT AGENT] Project {project_id} not found")
        return

    try:
        # Blocking parsers run off the event loop
        text = await asyncio.to_thread(extract_text, project["file_path"], project["file_type"])
        await projects_repo.update_one({"_id": oid}, {"$set": {"extracted_text": text}})

        trace: list = []
        try:
            metadata, trace = await _run_agent_extraction(text, project["file_name"])
            method = "agent"
        except Exception as e:
            logger.warning(f"[PROJECT AGENT] Agent loop failed for {project_id}, falling back: {e}")
            metadata = await _single_call_extraction(text)
            method = "single_call_fallback"

        name = metadata.title or project["name"]
        await projects_repo.update_one(
            {"_id": oid},
            {
                "$set": {
                    "name": name,
                    "metadata": metadata.model_dump(),
                    "extraction_method": method,
                    "agent_trace": trace,
                    "processing_status": "completed",
                    "processing_error": None,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        logger.info(f"[PROJECT AGENT] Processed '{name}' via {method} → domain={metadata.domain}")

        # A new project may now be the best match for already-enriched clients
        from app.ai.agents.client_domain_agent import refresh_matches_for_project

        await refresh_matches_for_project(project_id)

    except ExtractionError as e:
        logger.warning(f"[PROJECT AGENT] Extraction failed for {project_id}: {e}")
        await _mark_failed(oid, str(e))
    except Exception as e:
        logger.error(f"[PROJECT AGENT] Failed for {project_id}: {e}")
        await _mark_failed(oid, f"AI processing failed: {e}")


async def _mark_failed(oid: ObjectId, message: str) -> None:
    await projects_repo.update_one(
        {"_id": oid},
        {
            "$set": {
                "processing_status": "failed",
                "processing_error": message,
                "updated_at": datetime.utcnow(),
            }
        },
    )
