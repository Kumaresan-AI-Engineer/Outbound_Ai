SYSTEM_PROMPT = """You are a real-time AI sales coach assisting a business agent DURING a live outbound call with {contact_name}{company_part}. Call elapsed: {elapsed}.
{project_context}
Respond with a JSON object with exactly these fields:
{{
  "next_talking_point": "what the agent should say or ask next (1-2 sentences)",
  "objection_handling": "how to address any concern the prospect just raised (empty string if none)",
  "sentiment": "Positive" or "Neutral" or "Negative" (the prospect's current sentiment),
  "key_insight": "the single most important thing the prospect has revealed (empty string if none)",
  "recommended_project": "which ONE of our past projects to bring up right now, as 'Project Name — one-line pitch tailored to what the prospect just said' (empty string if none fits this moment)",
  "clarifying_question": "if the prospect just described a technical concept, system, tool, workflow, metric, or requirement, ONE specific, sharp follow-up question the BA should ask to dig deeper into it and uncover real requirements - empty string if they haven't said anything technical worth probing this turn"
}}

Keep advice concise, specific, and immediately actionable. Only fill clarifying_question when the prospect's last message actually contained technical detail worth following up on - don't force one every turn."""

PROJECT_CONTEXT_TEMPLATE = """
OUR COMPANY'S RELEVANT PAST PROJECTS — the client{client_domain_part}:
{project_lines}
Ground your coaching in these real projects: reference them by name with concrete outcomes instead of generic claims. Only recommend one when it genuinely fits the conversation.
"""

# Fast Groq gate deciding whether THIS turn should pull our project portfolio
# into the coaching prompt, and whether the client is describing their own
# need (worth a live project-match attempt). See suggestion_agent module
# docstring for the latency/accuracy rationale behind a separate small model.
PROJECT_SIGNAL_PROMPT = """Analyze the customer's message during a live sales call and decide two things:
1. is_project_inquiry: are they asking about, or would they clearly benefit from hearing about, OUR company's past projects, case studies, or capabilities?
2. is_describing_own_need: are they describing THEIR OWN project, business problem, or requirement (what they're trying to build or solve)?

Respond with ONLY a JSON object: {"is_project_inquiry": true or false, "is_describing_own_need": true or false}"""


def build_project_context(relevant: dict | None) -> str:
    """Render the matched-projects block for the coaching system prompt.
    Empty string when the contact has no imported client record or matches."""
    if not relevant or not relevant.get("projects"):
        return ""
    client = relevant.get("client") or {}
    domain_part = f" is in the {client['domain']} domain" if client.get("domain") else ""
    if client.get("project"):
        domain_part += f"; their current initiative: {client['project']}"

    lines = []
    for i, p in enumerate(relevant["projects"], 1):
        bits = [f"{i}. {p['name']}"]
        if p.get("domain"):
            bits.append(f"[{p['domain']}]")
        if p.get("summary"):
            bits.append(f"— {p['summary']}")
        if p.get("key_features"):
            bits.append(f"Key features: {', '.join(p['key_features'])}.")
        if p.get("technologies"):
            bits.append(f"Tech: {', '.join(p['technologies'])}.")
        lines.append(" ".join(bits))

    return PROJECT_CONTEXT_TEMPLATE.format(client_domain_part=domain_part, project_lines="\n".join(lines))


def build_coaching_messages(
    contact_name: str,
    company_part: str,
    elapsed: str,
    project_context: str,
    transcript_tail: str,
) -> list[dict]:
    return [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                contact_name=contact_name,
                company_part=company_part,
                elapsed=elapsed,
                project_context=project_context,
            ),
        },
        {
            "role": "user",
            "content": f"Live transcript (most recent last):\n\n{transcript_tail}\n\nProvide your coaching suggestion now.",
        },
    ]


def build_project_signal_messages(utterance: str) -> list[dict]:
    return [
        {"role": "system", "content": PROJECT_SIGNAL_PROMPT},
        {"role": "user", "content": f'Customer said: "{utterance}"'},
    ]
