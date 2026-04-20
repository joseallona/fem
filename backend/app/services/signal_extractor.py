"""
Signal extraction + classification — Stages 7 + 8.

Stage 7 (LLM): extract candidate signal from relevant document.
Stage 8 (deterministic rules first, LLM assist for ambiguous): classify STEEP / type / horizon.
"""
import logging
from typing import Optional

from app.services.llm_gateway import extract_signal as llm_extract_signal

logger = logging.getLogger(__name__)

# Deterministic classification rules.
# Note: drug/therapy/clinical/genomics moved to political — healthcare signals
# are usually about regulation (FDA approval, clinical trials, policy) not pure
# technology. LLM extraction can still override this if context is clearly R&D.
STEEP_KEYWORDS: dict[str, list[str]] = {
    "social": ["aging", "demographics", "population", "culture", "lifestyle", "inequality", "education", "health behavior", "workforce", "migration", "consumer", "wellbeing", "mental health"],
    "technological": ["ai", "biotech", "robot", "automation", "software", "platform", "patent", "research", "innovation", "startup", "algorithm", "semiconductor", "quantum"],
    "economic": ["market", "investment", "funding", "gdp", "insurance", "finance", "cost", "revenue", "labor", "employment", "pension", "retirement", "economic", "trade", "tariff"],
    "environmental": ["climate", "environment", "carbon", "energy", "sustainability", "ecology", "pollution", "biodiversity", "emissions", "renewable"],
    "political": ["policy", "regulation", "law", "government", "legislation", "approval", "fda", "regulatory", "compliance", "election", "political", "drug", "therapy", "clinical", "genomics", "trial"],
}

TYPE_KEYWORDS: dict[str, list[str]] = {
    "wildcard": ["unprecedented", "breakthrough", "unexpected", "shock", "sudden", "unprecedented", "extreme"],
    "weak_signal": ["emerging", "niche", "early", "experimental", "pilot", "prototype", "nascent", "novel"],
    "trend": ["growing", "increasing", "rising", "declining", "shift", "trend", "steady", "continuous", "momentum"],
    "driver": ["fundamental", "structural", "underlying", "force", "pressure", "catalyst", "driver"],
    "indicator": ["measure", "metric", "indicator", "index", "rate", "level", "data shows", "statistics"],
}

HORIZON_KEYWORDS: dict[str, list[str]] = {
    "H3": ["long-term", "decade", "next generation", "visionary", "speculative", "by 2040", "by 2050"],
    "H2": ["transition", "emerging", "medium-term", "disrupt", "shift", "by 2030", "within five years"],
    "H1": ["current", "today", "now", "present", "existing", "immediate", "short-term", "this year", "this quarter"],
}

# Horizon classification also considers referenced years relative to today.
# See _classify_horizon() — year-based detection is computed dynamically.
_HORIZON_YEAR_RANGES = {
    "H1": (0, 2),   # 0–2 years from now
    "H2": (2, 7),   # 2–7 years from now
    "H3": (7, 100), # 7+ years from now
}


def _classify_steep(text: str) -> str:
    text_lower = text.lower()
    scores = {cat: sum(1 for kw in kws if kw in text_lower) for cat, kws in STEEP_KEYWORDS.items()}
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "social"


def _classify_type(text: str) -> str:
    text_lower = text.lower()
    scores = {t: sum(1 for kw in kws if kw in text_lower) for t, kws in TYPE_KEYWORDS.items()}
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "trend"


def _classify_horizon(text: str) -> str:
    """
    Classify horizon by keyword match first, then by any 4-digit year found
    in the text relative to the current year. Falls back to H2.
    """
    import re
    from datetime import datetime
    text_lower = text.lower()
    for horizon in ("H1", "H2", "H3"):
        if any(kw in text_lower for kw in HORIZON_KEYWORDS[horizon]):
            return horizon

    # Dynamic year detection: find 4-digit years and classify by distance
    current_year = datetime.now().year
    years_found = [int(y) for y in re.findall(r"\b(20\d{2})\b", text)]
    if years_found:
        min_distance = min(abs(y - current_year) for y in years_found)
        for horizon, (lo, hi) in _HORIZON_YEAR_RANGES.items():
            if lo <= min_distance < hi:
                return horizon

    return "H2"  # default


def extract_and_classify(
    raw_text: str,
    title: str,
    theme_name: str,
    focal_question: Optional[str],
    relevance_score: float,
) -> Optional[dict]:
    """
    Extract a signal via LLM, then apply deterministic classification overrides.
    Returns a signal dict or None if extraction fails.
    """
    fq = focal_question or f"Monitor developments related to {theme_name}"
    combined_text = f"{title}\n\n{raw_text[:4000]}"

    try:
        signal = llm_extract_signal(combined_text, theme_name, fq)
    except Exception as e:
        logger.warning("LLM extraction failed, using fallback: %s", e)
        # Graceful degradation: build minimal signal from title
        signal = {
            "title": title[:200],
            "summary": raw_text[:300].strip(),
            "signal_type": _classify_type(combined_text),
            "steep_category": _classify_steep(combined_text),
            "horizon": _classify_horizon(combined_text),
            "importance_score": 0.4,
            "novelty_score": 0.4,
        }

    # Apply deterministic classification as override/validation
    text_for_rules = f"{signal.get('title', '')} {signal.get('summary', '')} {combined_text}"

    # Only override if LLM value is missing or invalid
    valid_steep = set(STEEP_KEYWORDS.keys())
    valid_types = set(TYPE_KEYWORDS.keys())
    valid_horizons = {"H1", "H2", "H3"}

    if signal.get("steep_category") not in valid_steep:
        signal["steep_category"] = _classify_steep(text_for_rules)
    if signal.get("signal_type") not in valid_types:
        signal["signal_type"] = _classify_type(text_for_rules)
    if signal.get("horizon") not in valid_horizons:
        signal["horizon"] = _classify_horizon(text_for_rules)

    # Clamp scores
    for field in ("importance_score", "novelty_score"):
        val = signal.get(field, 0.5)
        try:
            signal[field] = max(0.0, min(1.0, float(val)))
        except (TypeError, ValueError):
            signal[field] = 0.5

    signal["relevance_score"] = relevance_score
    return signal
