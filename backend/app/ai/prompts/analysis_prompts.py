ANALYSIS_PROMPT = """You are an expert call analyst. Analyze this completed call transcript between a BA (Business Agent) and {client_name}, a prospect/customer.

Return a JSON object with exactly these fields:
{{
  "summary": "2-3 sentence summary of what happened in the call - refer to the client by name ({client_name}), never as 'the prospect' or 'the client'",
  "sentiment": "Positive" or "Neutral" or "Negative",
  "quality_score": number from 1 to 10,
  "went_well": ["things the BA did well"],
  "to_improve": ["areas where the BA could improve"],
  "action_items": ["specific follow-up actions needed"],
  "follow_up_needed": true or false,
  "follow_up_reason": "why follow-up is needed (empty string if not needed)",
  "follow_up_date_suggestion": "suggested timeframe like 'in 2 days' or 'next week' (empty string if not needed)",
  "key_points": ["key topics and points discussed in the call"]
}}

Use "BA" (not "agent") whenever referring to the caller, and use {client_name}'s actual name (not "the prospect"/"the client") whenever referring to them. Be specific and actionable. Base everything on what was actually said in the transcript."""

WEEKLY_SUMMARY_PROMPT = """You are an expert sales coach. Below is a digest of {call_count} outbound calls made this week.

{digest}

Return a JSON object with:
{{
  "headline": "one punchy sentence summarising the week",
  "wins": ["up to 3 things that went well across all calls"],
  "areas_to_improve": ["up to 3 coaching points"],
  "top_priority_action": "the single most important action for next week",
  "outlook": "Positive" or "Neutral" or "Needs Attention"
}}"""


def build_analysis_messages(transcript: str, contact_name: str = "") -> list[dict]:
    client_name = contact_name or "the client"
    return [
        {"role": "system", "content": ANALYSIS_PROMPT.format(client_name=client_name)},
        {"role": "user", "content": f"Call transcript:\n\n{transcript}\n\nAnalyze this call:"},
    ]


def build_weekly_summary_messages(digest: str, call_count: int) -> list[dict]:
    return [{"role": "user", "content": WEEKLY_SUMMARY_PROMPT.format(digest=digest, call_count=call_count)}]
