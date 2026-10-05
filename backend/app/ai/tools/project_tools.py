"""Standalone tool functions for the project-extraction agent's tool-calling
loop (read chunk / search text / list known taxonomy / validate the final
save payload). Independently callable/testable, not nested inside the
agent's control-flow function.
"""

from app.ai.schemas.project_extraction import CANONICAL_DOMAINS
from app.repositories.projects_repo import projects_repo


def chunk_text(text: str, chunk_size: int) -> list[str]:
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def read_document_chunk(chunks: list[str], index: int) -> dict:
    if index < 1 or index > len(chunks):
        return {"error": f"Chunk {index} does not exist. Valid: 1..{len(chunks)}"}
    return {"chunk": index, "of": len(chunks), "text": chunks[index - 1]}


def search_document(full_text: str, query: str) -> dict:
    query = query.lower().strip()
    if not query:
        return {"error": "query is required"}
    hits = [line.strip()[:250] for line in full_text.split("\n") if query in line.lower()][:12]
    return {"matches": hits or [], "note": "" if hits else "No matches found."}


async def list_known_domains_and_technologies() -> dict:
    known_tech = await projects_repo.distinct("metadata.technologies", {"processing_status": "completed"})
    return {"canonical_domains": CANONICAL_DOMAINS, "known_technologies": sorted(known_tech)[:100]}


def validate_metadata(data: dict) -> list[str]:
    """Used by the save_project_metadata tool to let the agent self-correct
    before the final ProjectMetadata schema validation runs."""
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
