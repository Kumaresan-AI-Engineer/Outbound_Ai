CLASSIFY_PROMPT = """You are a business domain classifier. Given a client's details, determine which business domain they operate in.

The primary domain and related domains MUST be chosen from this exact list:
{domains}

Return a JSON object with exactly these fields:
{{
  "domain": "the single most likely primary domain from the list above",
  "related_domains": ["0-3 other closely related domains from the list above"]
}}"""


def build_classify_messages(details: str, domains: list[str]) -> list[dict]:
    return [
        {"role": "system", "content": CLASSIFY_PROMPT.format(domains=", ".join(domains))},
        {"role": "user", "content": f"{details}\n\nClassify this client's business domain:"},
    ]
