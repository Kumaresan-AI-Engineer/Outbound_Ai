from app.ai.schemas.project_extraction import CANONICAL_DOMAINS

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

FALLBACK_PROMPT = f"""You are an expert business analyst. Analyze the following project document and extract structured information about the project.

The primary domain and related domains MUST be chosen from this exact list:
{", ".join(CANONICAL_DOMAINS)}

Return a JSON object with exactly these fields:
{METADATA_FIELDS_SPEC}

Base everything strictly on the document content. Use empty strings/lists for anything not mentioned."""


def build_agent_start_messages(file_name: str, chunk_count: int, first_chunk: str) -> list[dict]:
    return [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Document: {file_name}\n"
                f"Total chunks: {chunk_count}\n\n"
                f"--- CHUNK 1 of {chunk_count} ---\n{first_chunk}\n\n"
                "Analyze this project and save its metadata."
            ),
        },
    ]


def build_fallback_messages(text: str, max_chars: int) -> list[dict]:
    return [
        {"role": "system", "content": FALLBACK_PROMPT},
        {
            "role": "user",
            "content": f"Project document:\n\n{text[:max_chars]}\n\nExtract the structured information:",
        },
    ]
