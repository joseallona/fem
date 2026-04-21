"""
LLM Gateway — single interface for all model calls.
Supports Ollama (local) and Groq (free cloud).
Add new providers by implementing the _call_* methods.

Job-type routing:
  bulk/cheap tasks (triage, extraction, classification, summary) → default: ollama
  quality tasks (brief prose) → default: configurable via LLM_ROUTING env var
  e.g. LLM_ROUTING="brief:groq,summary:ollama"
"""
import logging

import httpx

from app.core.config import get_runtime_setting, settings

logger = logging.getLogger(__name__)


def _escape_control_chars_in_strings(s: str) -> str:
    """
    Escape literal control characters that appear inside JSON string values only.
    Structural whitespace (newlines between keys/values) is left intact so that
    pretty-printed JSON from Ollama still parses correctly.
    """
    result = []
    in_string = False
    escaped = False
    _escapes = {'\n': '\\n', '\r': '\\r', '\t': '\\t'}
    for ch in s:
        if escaped:
            result.append(ch)
            escaped = False
        elif ch == '\\' and in_string:
            result.append(ch)
            escaped = True
        elif ch == '"':
            in_string = not in_string
            result.append(ch)
        elif in_string and ch in _escapes:
            result.append(_escapes[ch])
        else:
            result.append(ch)
    return ''.join(result)


def _parse_llm_json(raw: str) -> dict:
    """
    Robustly extract and parse a JSON object from LLM output.
    Handles:
      - Markdown code fences
      - Array responses (unwraps first element)
      - Literal control characters inside JSON string values (Ollama quirk)
    """
    import json
    raw = raw.strip()
    # Strip markdown code fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()

    # Isolate the outermost JSON value (object or array)
    first_brace = raw.find("{")
    first_bracket = raw.find("[")
    use_array = first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace)

    if use_array:
        open_ch, close_ch = "[", "]"
        start = first_bracket
    else:
        open_ch, close_ch = "{", "}"
        start = first_brace

    if start == -1:
        return json.loads(raw)  # let it fail naturally

    raw = raw[start:]
    depth, end = 0, -1
    for i, ch in enumerate(raw):
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                end = i
                break
    if end != -1:
        raw = raw[: end + 1]

    # First attempt: parse as-is (handles well-formed pretty-printed JSON)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Second attempt: escape control chars inside string values
        parsed = json.loads(_escape_control_chars_in_strings(raw))

    if use_array:
        return parsed[0] if isinstance(parsed, list) and parsed else parsed
    return parsed

# Default routing table: job_type → provider
#
# Tiers:
#   ollama      — local model (OLLAMA_MODEL, e.g. llama3.1)
#   ollama-r1   — local reasoning model (OLLAMA_MODEL_REASONING, e.g. deepseek-r1:32b)
#   deepseek    — DeepSeek V3 via DeepSeek API (requires DEEPSEEK_API_KEY)
#   deepseek-r1 — DeepSeek R1 via DeepSeek API (requires DEEPSEEK_API_KEY)
#
# Fallback chain when a provider's API key is missing:
#   ollama-r1   → ollama
#   deepseek-r1 → deepseek → ollama-r1 → ollama
#   deepseek    → ollama
_DEFAULT_ROUTING: dict[str, str] = {
    "triage":         "ollama",      # bulk — local light model
    "extraction":     "ollama",      # high volume — local light model
    "classification": "ollama",      # structured but simple — local light model
    "summary":        "ollama",      # trend synthesis / driver extraction — llama3.1 sufficient
    "scenario":       "ollama-r1",   # narrative generation — R1-14B for quality
    "brief":          "ollama",      # final prose
    "axis":           "ollama-r1",   # axis reasoning + divergence scoring — R1-14B excels here
}


def _build_routing_table() -> dict[str, str]:
    """Merge default routing with runtime overrides (DB → env)."""
    table = dict(_DEFAULT_ROUTING)
    routing_str = get_runtime_setting("llm_routing", settings.LLM_ROUTING)
    if routing_str:
        for entry in routing_str.split(","):
            entry = entry.strip()
            if ":" in entry:
                job, provider = entry.split(":", 1)
                table[job.strip()] = provider.strip()
    return table


def _deepseek_key_configured() -> bool:
    return bool(get_runtime_setting("deepseek_api_key", settings.DEEPSEEK_API_KEY).strip())


def _resolve_provider(job_type: str) -> str:
    """
    Return the effective provider for a job_type, walking the fallback chain
    when the preferred provider's API key is not configured.

    Providers:
      ollama      — local model (OLLAMA_MODEL)
      ollama-r1   — local reasoning model (OLLAMA_MODEL_REASONING, e.g. deepseek-r1:32b)
      groq        — Groq API (requires GROQ_API_KEY)
      deepseek    — DeepSeek V3 API (requires DEEPSEEK_API_KEY)
      deepseek-r1 — DeepSeek R1 API (requires DEEPSEEK_API_KEY)

    Fallback chain:
      ollama-r1   → groq → ollama
      deepseek-r1 → deepseek → groq → ollama
      deepseek    → groq → ollama
      groq        → ollama
    """
    routing = _build_routing_table()
    preferred = routing.get(job_type, get_runtime_setting("llm_provider", settings.LLM_PROVIDER))

    if preferred == "ollama-r1":
        chain = ["ollama-r1", "ollama"]
    elif preferred == "deepseek-r1":
        chain = ["deepseek-r1", "deepseek", "ollama-r1", "ollama"]
    elif preferred == "deepseek":
        chain = ["deepseek", "ollama"]
    else:
        chain = [preferred]

    for provider in chain:
        if provider in ("deepseek-r1", "deepseek") and not _deepseek_key_configured():
            continue
        if provider != preferred:
            logger.debug("LLM fallback: %s → %s (job=%s)", preferred, provider, job_type)
        return provider

    return "ollama"


def _call_ollama(prompt: str, system: str = "", reasoning: bool = False) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    base_url = get_runtime_setting("ollama_base_url", settings.OLLAMA_BASE_URL)
    if reasoning:
        model = get_runtime_setting("ollama_model_reasoning", settings.OLLAMA_MODEL_REASONING)
    else:
        model = get_runtime_setting("ollama_model", settings.OLLAMA_MODEL)
    response = httpx.post(
        f"{base_url}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=180.0,  # reasoning models take longer
    )
    response.raise_for_status()
    content = response.json()["message"]["content"]
    # Strip DeepSeek R1 chain-of-thought block if present
    if "<think>" in content:
        content = content.split("</think>")[-1].strip()
    return content



def _call_deepseek(prompt: str, system: str = "", reasoning: bool = False) -> str:
    """
    Call DeepSeek API.
    reasoning=True uses DeepSeek R1 (deepseek-reasoner) — strips <think> block from output.
    reasoning=False uses DeepSeek V3 (deepseek-chat).
    """
    messages = []
    if system and not reasoning:
        # R1 doesn't support system messages in the same way; fold into user turn
        messages.append({"role": "system", "content": system})
    elif system and reasoning:
        prompt = f"{system}\n\n{prompt}"
    messages.append({"role": "user", "content": prompt})

    api_key = get_runtime_setting("deepseek_api_key", settings.DEEPSEEK_API_KEY)
    model = settings.DEEPSEEK_MODEL if reasoning else settings.DEEPSEEK_MODEL_FAST
    response = httpx.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": messages},
        timeout=120.0,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    # Strip R1 chain-of-thought block if present
    if "<think>" in content:
        content = content.split("</think>")[-1].strip()
    return content


def call_llm(prompt: str, system: str = "", job_type: str = "quality") -> str:
    """
    Route to the appropriate LLM provider based on job_type.

    job_type → default provider:
      triage, extraction, classification  → ollama  (local, high volume)
      summary, scenario, brief            → groq    (Llama 3.3 70B)
      axis                                → deepseek-r1 (R1 reasoning, falls back to groq)

    Providers fall back gracefully when API keys are missing:
      deepseek-r1 → deepseek → groq → ollama
    """
    provider = _resolve_provider(job_type)
    if provider == "ollama-r1":
        return _call_ollama(prompt, system, reasoning=True)
    if provider == "deepseek-r1":
        return _call_deepseek(prompt, system, reasoning=True)
    if provider == "deepseek":
        return _call_deepseek(prompt, system, reasoning=False)
    return _call_ollama(prompt, system)


# --- Embedding ---

def get_embedding(text: str) -> list[float]:
    """
    Compute a text embedding via Ollama's embedding endpoint.
    Uses OLLAMA_EMBEDDING_MODEL (default: nomic-embed-text).
    """
    base_url = get_runtime_setting("ollama_base_url", settings.OLLAMA_BASE_URL)
    model = get_runtime_setting("ollama_embedding_model", settings.OLLAMA_EMBEDDING_MODEL)
    response = httpx.post(
        f"{base_url}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()["embedding"]


# --- Task-specific wrappers ---

def extract_signal(document_text: str, theme_name: str, focal_question: str) -> dict:
    system = (
        "You are a strategic intelligence analyst. "
        "Extract a concise signal from the provided text. "
        "Return JSON only, no explanation."
    )
    prompt = f"""Theme: {theme_name}
Focal question: {focal_question}

Document text:
{document_text[:3000]}

Extract a signal as JSON with these fields:
- title (string, max 120 chars)
- summary (string, 2-3 sentences)
- relevance_reason (string, 1-2 sentences — why this signal is specifically relevant to the theme and focal question)
- signal_type (one of: trend, weak_signal, wildcard, driver, indicator)
- steep_category (one of: social, technological, economic, environmental, political)
- horizon (one of: H1, H2, H3)
- importance_score (float 0.0-1.0)
- novelty_score (float 0.0-1.0)

JSON only:"""
    raw = call_llm(prompt, system, job_type="extraction")
    return _parse_llm_json(raw)


def draft_brief_section(section: str, context: str) -> str:
    system = (
        "You are a strategic analyst writing a concise intelligence brief. "
        "Write clearly and without filler. Avoid speculation beyond evidence."
    )
    prompt = f"""Section: {section}

Evidence and context:
{context}

Write this section in 2-4 sentences. Be direct and strategic."""
    return call_llm(prompt, system, job_type="brief")


def summarize_cluster(signals_text: str, theme_name: str) -> str:
    system = "You are a strategic analyst. Summarize the common pattern across these signals concisely."
    prompt = f"Theme: {theme_name}\n\nSignals:\n{signals_text}\n\nSummary (2-3 sentences):"
    return call_llm(prompt, system, job_type="summary")


def synthesize_trend(signals: list[dict], theme_name: str, focal_question: str) -> dict:
    """
    Given a cluster of related signals, synthesize a named trend with directional framing.
    Returns: {name, description, direction, counterpole, steep_domains, s_curve_position, horizon}
    """
    signals_text = "\n".join(
        f"- [{s.get('steep_category','?')}|{s.get('horizon','?')}] {s.get('title','')} — {s.get('summary','')[:120]}"
        for s in signals[:15]
    )
    system = (
        "You are a strategic foresight analyst identifying distinct trends within a theme. "
        "Each trend must capture a SPECIFIC angle — avoid broad theme labels. "
        "Return JSON only, no explanation."
    )
    prompt = f"""Theme: {theme_name}
Focal question: {focal_question}

Signals cluster ({len(signals)} signals — sample below):
{signals_text}

Identify the SPECIFIC trend this cluster represents. Do NOT name it after the broad theme.
Instead, name it after what is DISTINCTIVELY happening in these signals:
- What specific technology, policy, actor, geography, or mechanism is driving this?
- What concrete change is underway that differs from other parts of the energy story?

Bad name examples (too generic): "Energy Transition", "Renewable Energy Growth", "Sustainable Energy"
Good name examples (specific): "Battery Storage Cost Collapse", "Offshore Wind Policy Acceleration", "Corporate PPA Market Maturation"

Return JSON with:
- name (string, max 80 chars — specific, distinctive trend name — NOT a broad theme label)
- description (string, 2-3 sentences describing the specific dynamic and where it's heading)
- direction (string, max 120 chars — the specific future state this cluster is pushing toward)
- counterpole (string, max 120 chars — the opposing future state that would look completely different)
- steep_domains (list of strings from: social, technological, economic, environmental, political)
- s_curve_position (one of: emerging, growth, mature, declining)
- horizon (one of: H1, H2, H3)

JSON only:"""
    raw = call_llm(prompt, system, job_type="summary")
    return _parse_llm_json(raw)


def reason_signal_link(
    title_a: str, summary_a: str,
    title_b: str, summary_b: str,
    theme_name: str,
) -> dict:
    """
    Determine whether two signals are meaningfully connected and the nature of their relationship.
    Returns: {connected: bool, relationship: "reinforcing"|"tensioning", reason: str}
    """
    system = (
        "You are a strategic foresight analyst evaluating whether two signals are meaningfully "
        "connected within a theme. Return JSON only."
    )
    prompt = f"""Theme: {theme_name}

Signal A: {title_a}
{summary_a}

Signal B: {title_b}
{summary_b}

Are these two signals meaningfully connected — do they share an underlying force, dynamic, or implication relevant to the theme?

If connected, classify the relationship:
- reinforcing: both signals push in the same direction or amplify the same trend
- tensioning: the signals point in opposing directions or represent competing forces

Return JSON with:
- connected (boolean)
- relationship (string: "reinforcing" or "tensioning" — only if connected is true, else null)
- reason (string, 1 sentence — why they are or aren't connected)

JSON only:"""
    raw = call_llm(prompt, system, job_type="summary")
    return _parse_llm_json(raw)


def extract_driver(trend_name: str, trend_description: str, theme_name: str, time_horizon: str,
                   direction: str = "", counterpole: str = "") -> dict:
    """
    Extract a driver of change from a trend and score its impact and uncertainty.
    Returns: {name, description, impact_score, uncertainty_score, is_predetermined, steep_domain,
              pole_high_direction, pole_low_direction}
    """
    direction_block = ""
    if direction and counterpole:
        direction_block = f"""
Trend direction: {direction}
Trend counterpole: {counterpole}
"""
    system = (
        "You are a strategic foresight analyst. Extract a driver of change from the provided trend "
        "and score it for strategic scenario planning. Return JSON only."
    )
    prompt = f"""Theme: {theme_name}
Time horizon: {time_horizon}

Trend: {trend_name}
Description: {trend_description}{direction_block}

Extract the underlying driver of change that makes this trend genuinely uncertain — it could resolve in either direction.

Return JSON with:
- name (string, max 100 chars — the fundamental force driving change, framed as a genuine uncertainty)
- description (string, 2-3 sentences explaining what this driver is and why its outcome is uncertain)
- impact_score (float 1.0-10.0 — how strongly does this driver shape the theme's future?)
- uncertainty_score (float 1.0-10.0 — how unpredictable is the direction/magnitude of this driver?)
- is_predetermined (boolean — true if high impact but low uncertainty, i.e. this will happen regardless)
- steep_domain (one of: social, technological, economic, environmental, political)
- pole_high_direction (string, max 150 chars — describe what signals would look like if this driver resolves toward its HIGH/accelerating/optimistic extreme. Be specific: what would you observe?)
- pole_low_direction (string, max 150 chars — describe what signals would look like if this driver resolves toward its LOW/decelerating/pessimistic extreme. Be specific: what would you observe?)

Note: A predetermined element has impact_score >= 7 and uncertainty_score <= 3.
Critical uncertainties have impact_score >= 7 AND uncertainty_score >= 7.
The pole_high and pole_low directions MUST describe observable signal patterns, not abstract states.

JSON only:"""
    raw = call_llm(prompt, system, job_type="summary")
    return _parse_llm_json(raw)


def propose_axis_poles(driver_name: str, driver_description: str, theme_name: str) -> dict:
    """
    For a selected critical uncertainty, propose pole labels and selection rationale.
    Returns: {pole_low, pole_high, rationale}
    """
    system = (
        "You are a strategic foresight analyst. For a given driver of change, define the two extreme "
        "poles that bound its uncertainty range. Return JSON only."
    )
    prompt = f"""Theme: {theme_name}
Driver: {driver_name}
Description: {driver_description}

Define the two poles for this uncertainty axis.

CRITICAL RULE: Each pole must represent the MOST EXTREME PLAUSIBLE outcome in its direction — not a moderate or average case. The two poles should feel like they belong to different worlds. If someone reads both poles together, they should feel genuine cognitive dissonance.

BAD example (too moderate): pole_low="Slow AI adoption" pole_high="Fast AI adoption"
GOOD example (genuinely extreme): pole_low="AI remains a niche specialist tool; most organisations rely on human judgement for core decisions" pole_high="Autonomous AI agents manage the majority of knowledge work; human oversight is the exception, not the rule"

Return JSON with:
- pole_low (string, max 150 chars — the extreme restrictive/minimal/pessimistic end; fully commit to this direction)
- pole_high (string, max 150 chars — the extreme permissive/maximal/optimistic end; fully commit to this direction)
- rationale (string, 2-3 sentences — why this driver was selected as a critical uncertainty and why the poles represent genuine extremes)

JSON only:"""
    raw = call_llm(prompt, system, job_type="axis")
    return _parse_llm_json(raw)


def check_pole_opposition(pole_low: str, pole_high: str, driver_name: str) -> dict:
    """
    Score how genuinely opposite two axis poles are.
    Returns: {opposition_score: float 0.0-1.0, rationale: str}
    A score below the configured threshold means the driver is excluded from axis candidacy.
    """
    system = "You are a strategic foresight analyst evaluating scenario axis quality. Return JSON only."
    prompt = f"""Evaluate whether these two poles for the driver "{driver_name}" are GENUINELY OPPOSITE.

Pole Low: {pole_low}
Pole High: {pole_high}

GENUINE OPPOSITES means:
- They describe mutually exclusive future states — both cannot be true simultaneously
- They are collectively exhaustive — one of them must eventually be true
- A world at the low pole is qualitatively incompatible with a world at the high pole

POOR OPPOSITES (score near 0):
- Same thing in different degree ("slow AI" vs "fast AI" with no qualitative difference)
- One subsumes the other
- Both could coexist in the same future

TRUE OPPOSITES (score near 1):
- Completely incompatible worlds
- Reading both poles together creates genuine cognitive dissonance

Return JSON with:
- opposition_score (float 0.0-1.0)
- rationale (string, 1-2 sentences explaining the score)

JSON only:"""
    raw = call_llm(prompt, system, job_type="axis")
    return _parse_llm_json(raw)


def check_axis_independence(
    driver1_name: str,
    driver1_description: str,
    driver2_name: str,
    driver2_description: str,
) -> dict:
    """
    Check whether two proposed scenario axes are sufficiently independent.
    Returns: {independent: bool, correlation_reason: str}
    """
    system = (
        "You are a strategic foresight analyst evaluating scenario axis quality. Return JSON only."
    )
    prompt = f"""Evaluate whether these two proposed scenario axes are INDEPENDENT of each other.

Axis 1: {driver1_name}
Description: {driver1_description}

Axis 2: {driver2_name}
Description: {driver2_description}

INDEPENDENCE MEANS: Knowing how Axis 1 resolves tells you NOTHING about how Axis 2 resolves.
All four quadrant combinations (High/High, High/Low, Low/High, Low/Low) must be independently plausible.

CORRELATED axes fail this test — e.g. "AI investment levels" and "AI adoption rates" are correlated because high investment drives high adoption.

Return JSON with:
- independent (boolean — true only if both axes can plausibly resolve in either direction regardless of the other)
- correlation_reason (string — brief explanation of why they are or aren't independent)

JSON only:"""
    raw = call_llm(prompt, system, job_type="axis")
    return _parse_llm_json(raw)


def score_axis_pair_divergence(
    driver1_name: str,
    driver1_pole_high: str,
    driver1_pole_low: str,
    driver2_name: str,
    driver2_pole_high: str,
    driver2_pole_low: str,
    theme_name: str,
) -> dict:
    """
    Score how much scenario space a pair of axes creates.
    Returns: {divergence_score: float 0-10, rationale: str}
    A high divergence score means the 4 quadrant combinations feel like genuinely different worlds.
    """
    system = "You are a strategic foresight analyst evaluating scenario axis quality. Return JSON only."
    prompt = f"""Theme: {theme_name}

Evaluate how much SCENARIO SPACE this pair of axes creates.

Axis 1: {driver1_name}
  High pole: {driver1_pole_high}
  Low pole:  {driver1_pole_low}

Axis 2: {driver2_name}
  High pole: {driver2_pole_high}
  Low pole:  {driver2_pole_low}

Mentally construct the 4 quadrant combinations (High/High, High/Low, Low/High, Low/Low).
A good axis pair creates 4 worlds that feel QUALITATIVELY different — different power structures, different daily life, different winners and losers.
A poor pair creates 4 worlds that feel like variations of the same theme.

Return JSON with:
- divergence_score (float 0.0-10.0 — how much scenario space these axes create together; 10 = four radically different worlds)
- rationale (string — brief explanation of why this pair does or doesn't create rich scenario space)

JSON only:"""
    raw = call_llm(prompt, system, job_type="axis")
    return _parse_llm_json(raw)


def generate_scenario_draft(
    theme_name: str,
    focal_question: str,
    time_horizon: str,
    axis1_name: str,
    axis1_pole: str,
    axis2_name: str,
    axis2_pole: str,
    signals_text: str,
    predetermined_elements: list[str],
    diagonal_axis1_pole: str = "",
    diagonal_axis2_pole: str = "",
) -> dict:
    """
    Generate a full scenario narrative for one quadrant of the 2x2 matrix.
    Uses inside-out construction: builds the world from the quadrant logic first,
    then derives narrative. Maximally diverges from the diagonal opposite quadrant.

    Returns: {name, narrative, key_characteristics, stakeholder_implications,
              early_indicators, opportunities, threats}
    """
    predetermined_text = (
        "\n".join(f"- {p}" for p in predetermined_elements)
        if predetermined_elements
        else "None identified."
    )
    diagonal_block = ""
    if diagonal_axis1_pole and diagonal_axis2_pole:
        diagonal_block = f"""
DIAGONAL OPPOSITE (this scenario must feel like a completely different world from its opposite):
- {axis1_name}: {diagonal_axis1_pole}
- {axis2_name}: {diagonal_axis2_pole}
Your scenario must diverge MAXIMALLY from this diagonal. If someone reads both scenarios back-to-back,
they should feel genuine cognitive dissonance — not just different shades of the same future.
"""

    system = (
        "You are a strategic foresight analyst creating vivid, plausible scenario narratives "
        "for executive decision-making. Write in present tense set in the future. Return JSON only."
    )
    prompt = f"""Theme: {theme_name}
Focal question: {focal_question}
Time horizon: {time_horizon}

THIS SCENARIO'S QUADRANT POSITION:
- {axis1_name}: {axis1_pole}
- {axis2_name}: {axis2_pole}
{diagonal_block}
PREDETERMINED ELEMENTS (true in ALL scenarios):
{predetermined_text}

SUPPORTING SIGNALS (evidence from the world):
{signals_text[:2000]}

CONSTRUCTION METHOD — follow this sequence:
1. FULLY COMMIT to the quadrant: this world has fully resolved to [{axis1_pole}] AND [{axis2_pole}]. Do not hedge or moderate — live at the extreme.
2. Ask: given this combination, who holds power? What has disappeared? What do ordinary people experience daily?
3. Build a world that COULD NOT be confused with any other quadrant.
4. Name it with 2-5 evocative words that encode the internal logic (e.g. "Fortress of Plenty", "The Long Unravelling", "Quiet Dominance") — NOT generic labels like "Optimistic Future".

Return JSON with:
- name (string, 2-5 evocative words — the name should make the scenario logic immediately legible)
- narrative (string, 3-4 paragraphs in present tense set at the end of {time_horizon} — be specific: name institutions, describe what changed, show what daily life looks like for a key stakeholder)
- key_characteristics (list of 5-7 short strings — defining features that ONLY this quadrant would have)
- stakeholder_implications (string, 2-3 sentences — who specifically wins, who specifically loses, and why this quadrant produces that outcome)
- early_indicators (list of 5 strings — specific, observable signals RIGHT NOW that would confirm this scenario is emerging; avoid vague indicators like "increased investment")
- opportunities (list of 3-5 strings — strategic opportunities unique to this world)
- threats (list of 3-5 strings — strategic risks unique to this world)

JSON only:"""
    raw = call_llm(prompt, system, job_type="scenario")
    return _parse_llm_json(raw)
