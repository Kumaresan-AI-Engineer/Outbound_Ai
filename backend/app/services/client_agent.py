"""Client enrichment agent.

After a client row is imported from Excel, this agent classifies the client's
business domain from their name / company details / project description, then
matches our internal project repository for same-or-related-domain projects.
The matches feed the in-call suggestion agent so recommendations reference
real past work instead of generic advice.

Failure policy: never raises — errors land on the client doc as
enrichment_status="failed".
"""

import json
import asyncio
import logging
from datetime import datetime
from bson import ObjectId
from app.config import get_settings
from app.database import clients_collection, projects_collection
from app.services.ai_service import _get_groq, _get_openai
from app.services.project_agent import CANONICAL_DOMAINS

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_MATCHED_PROJECTS = 5

CLASSIFY_PROMPT = """You are a business domain classifier. Given a client's details, determine which business domain they operate in.

The primary domain and related domains MUST be chosen from this exact list:
{domains}

Return a JSON object with exactly these fields:
{{
  "domain": "the single most likely primary domain from the list above",
  "related_domains": ["0-3 other closely related domains from the list above"]
}}"""


async def _classify_domain_from_text(details: str, provider: str = None) -> dict:
    """Domain classification from arbitrary free text. Shared by the Excel
    import path (structured client fields) and the live-call path (whatever
    the client just said about their own need)."""
    provider = provider or settings.ai_provider
    messages = [
        {"role": "system", "content": CLASSIFY_PROMPT.format(domains=", ".join(CANONICAL_DOMAINS))},
        {"role": "user", "content": f"{details}\n\nClassify this client's business domain:"},
    ]

    if provider == "groq":
        response = await _get_groq().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.1,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
    else:
        response = await _get_openai().chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.1,
            max_tokens=200,
            response_format={"type": "json_object"},
        )

    data = json.loads(response.choices[0].message.content)
    domain = str(data.get("domain") or "Other")
    if domain not in CANONICAL_DOMAINS:
        domain = "Other"
    related = [
        d for d in (data.get("related_domains") or [])
        if isinstance(d, str) and d in CANONICAL_DOMAINS and d != domain
    ]
    return {"domain": domain, "related_domains": related}


async def _classify_domain(client: dict, provider: str = None) -> dict:
    details = (
        f"Client name: {client.get('name', '')}\n"
        f"Company details: {client.get('company', '')}\n"
        f"Client project: {client.get('project', '')}"
    )
    return await _classify_domain_from_text(details, provider)


async def _find_matching_projects(domain: str, related_domains: list) -> list:
    """Match processed projects whose domain overlaps the client's domains."""
    client_domains = [domain] + related_domains
    matched = []
    async for doc in (
        projects_collection.find({
            "processing_status": "completed",
            "$or": [
                {"metadata.domain": {"$in": client_domains}},
                {"metadata.related_domains": domain},
            ],
        })
        .sort("created_at", -1)
        .limit(MAX_MATCHED_PROJECTS * 3)
    ):
        # Primary-domain matches rank above related-domain matches
        exact = doc.get("metadata", {}).get("domain") == domain
        matched.append((0 if exact else 1, str(doc["_id"])))
    matched.sort(key=lambda m: m[0])
    return [pid for _, pid in matched[:MAX_MATCHED_PROJECTS]]


async def enrich_client(client_id: str) -> None:
    """Classify a client's domain and store matching internal projects."""
    oid = ObjectId(client_id)
    client = await clients_collection.find_one({"_id": oid})
    if not client:
        return

    await clients_collection.update_one(
        {"_id": oid}, {"$set": {"enrichment_status": "processing"}}
    )
    try:
        classification = await _classify_domain(client)
        matched_ids = await _find_matching_projects(
            classification["domain"], classification["related_domains"]
        )
        await clients_collection.update_one(
            {"_id": oid},
            {"$set": {
                "domain": classification["domain"],
                "related_domains": classification["related_domains"],
                "matched_project_ids": matched_ids,
                "enrichment_status": "completed",
                "updated_at": datetime.utcnow(),
            }},
        )
        logger.info(
            f"[CLIENT AGENT] {client.get('name')} → {classification['domain']} "
            f"({len(matched_ids)} matched projects)"
        )
    except Exception as e:
        logger.error(f"[CLIENT AGENT] Enrichment failed for {client_id}: {e}")
        await clients_collection.update_one(
            {"_id": oid}, {"$set": {"enrichment_status": "failed"}}
        )


async def refresh_matches_for_project(project_id: str) -> None:
    """Re-run (Mongo-only) project matching for clients whose domain overlaps
    a newly processed project — no LLM calls needed."""
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project or project.get("processing_status") != "completed":
        return
    meta = project.get("metadata", {}) or {}
    domains = [meta.get("domain")] + (meta.get("related_domains") or [])
    domains = [d for d in domains if d]
    if not domains:
        return

    async for client in clients_collection.find({
        "enrichment_status": "completed",
        "$or": [
            {"domain": {"$in": domains}},
            {"related_domains": {"$in": domains}},
        ],
    }):
        try:
            matched_ids = await _find_matching_projects(
                client.get("domain", "Other"), client.get("related_domains", [])
            )
            await clients_collection.update_one(
                {"_id": client["_id"]},
                {"$set": {"matched_project_ids": matched_ids, "updated_at": datetime.utcnow()}},
            )
        except Exception as e:
            logger.error(f"[CLIENT AGENT] Rematch failed for {client['_id']}: {e}")


async def _serialize_matched_projects(project_ids: list) -> list:
    ids = [ObjectId(pid) for pid in project_ids if ObjectId.is_valid(pid)]
    if not ids:
        return []
    projects = []
    async for doc in projects_collection.find({"_id": {"$in": ids}}):
        meta = doc.get("metadata", {}) or {}
        projects.append({
            "name": doc.get("name", ""),
            "domain": meta.get("domain", ""),
            "summary": meta.get("summary", ""),
            "key_features": meta.get("key_features", [])[:5],
            "technologies": meta.get("technologies", [])[:8],
            "business_problem": meta.get("business_problem", ""),
            "solution_provided": meta.get("solution_provided", ""),
        })
    return projects


async def get_relevant_projects_for_contact(contact_id: str, phone: str = "") -> dict | None:
    """Look up the imported client record for a contact (by linked contact_id,
    falling back to phone) and return their profile + matched project metadata.
    Used by the in-call suggestion agent."""
    query = {"$or": [{"contact_id": contact_id}]}
    if phone:
        query["$or"].append({"phone": phone})
    client = await clients_collection.find_one(query, sort=[("created_at", -1)])
    if not client:
        return None

    projects = await _serialize_matched_projects(client.get("matched_project_ids", []))
    return {
        "client": {
            "name": client.get("name", ""),
            "company": client.get("company", ""),
            "project": client.get("project", ""),
            "domain": client.get("domain", ""),
        },
        "projects": projects,
    }


async def match_projects_from_description(description: str) -> dict | None:
    """Live, mid-call equivalent of enrich_client() for contacts with no
    pre-matched projects - either the Excel row had a blank Project field, or
    the contact was never imported at all. Classifies domain straight from
    what the client just said and matches our project repository against it.

    Call-scoped only (nothing is written back to the clients collection) -
    a single call's transcript isn't reliable enough to permanently relabel
    a client's domain. The suggestion agent locks in the first successful
    result for the rest of the call rather than calling this repeatedly."""
    if not description.strip():
        return None
    try:
        classification = await _classify_domain_from_text(
            f"Client's described need: {description}"
        )
        matched_ids = await _find_matching_projects(
            classification["domain"], classification["related_domains"]
        )
        projects = await _serialize_matched_projects(matched_ids)
        if not projects:
            return None
        logger.info(
            f"[CLIENT AGENT] Live-matched {len(projects)} project(s) from call "
            f"description → {classification['domain']}"
        )
        return {
            "client": {"domain": classification["domain"], "project": description},
            "projects": projects,
        }
    except Exception as e:
        logger.error(f"[CLIENT AGENT] Live description match failed: {e}")
        return None
