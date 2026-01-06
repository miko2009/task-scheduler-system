"""LLM prompt templates for wrapped analysis."""

PERSONALITY_PROMPT = (
    "Infer a concise personality label from the user's TikTok watch history sample. "
    "Return a single lowercase token with underscores if needed (e.g., night_shift_scroller). No punctuation."
)

PERSONALITY_EXPLANATION_PROMPT = (
    "Explain in 1-2 sentences why this personality fits the user based on the provided watch patterns."
)

NICHE_JOURNEY_PROMPT = (
    "Summarize the user's 2025 niche interest journey in exactly 5 short words or phrases. "
    "Return a JSON array of 5 strings, no extra text."
)

TOP_NICHES_PROMPT = (
    "Identify the user's top 2 niche interests and estimate the percentile for the top niche (e.g., 'top 5%'). "
    "Return JSON: {\"top_niches\": [\"niche1\", \"niche2\"], \"top_niche_percentile\": \"top 5%\"}. No other text."
)

BRAINROT_SCORE_PROMPT = (
    "Assign a brainrot score from 0-100 based on the watch patterns. Return only the integer 0-100, no text."
)

BRAINROT_EXPLANATION_PROMPT = (
    "In 1-2 sentences, explain the brainrot score you assigned, grounded in the watch patterns."
)

KEYWORD_2026_PROMPT = "Suggest a single keyword that captures the user's likely 2026 vibe. Return only the keyword."

ROAST_THUMB_PROMPT = (
    "Write a playful one-liner roast about how much the user's thumb has scrolled, given the total videos/time watched."
)
