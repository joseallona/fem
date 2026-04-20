"""
Signal scoring + ranking — Stage 9.
Scenario update engine — Stage 11.
Change detection — Stage 12.

All deterministic. No LLM. (per Decision Logic Specification)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.scenario import Scenario
from app.models.signal import Signal, SignalScenario

logger = logging.getLogger(__name__)

# Signal score weights — default values; overridden at runtime via SystemSetting
W_RELEVANCE = 0.30
W_NOVELTY = 0.25
W_IMPACT = 0.20
W_SOURCE_TRUST = 0.15
W_RECENCY = 0.10

# Recency: full score if published within 3 days, decays to 0 at 30 days
RECENCY_FULL_DAYS = 3
RECENCY_ZERO_DAYS = 30


def _get_weights() -> dict[str, float]:
    """Read scoring weights from runtime settings, falling back to module constants."""
    from app.core.config import get_runtime_setting
    return {
        "relevance": float(get_runtime_setting("scoring_w_relevance", W_RELEVANCE)),
        "novelty": float(get_runtime_setting("scoring_w_novelty", W_NOVELTY)),
        "impact": float(get_runtime_setting("scoring_w_impact", W_IMPACT)),
        "source_trust": float(get_runtime_setting("scoring_w_source_trust", W_SOURCE_TRUST)),
        "recency": float(get_runtime_setting("scoring_w_recency", W_RECENCY)),
    }

# Impact keywords (deterministic heuristic)
HIGH_IMPACT_KEYWORDS = [
    "breakthrough", "approval", "ban", "collapse", "launch", "billion",
    "regulation", "law", "policy", "clinical trial", "funding", "acquisition",
    "partnership", "failure", "shortage", "crisis", "record",
]

SCENARIO_WINDOW_DAYS = 30

# Momentum thresholds (normalized delta over last 7 days)
MOMENTUM_UP = 1.0
MOMENTUM_DOWN = -1.0


# ---------- Signal scoring ----------

def _recency_score(created_at: Optional[datetime]) -> float:
    if not created_at:
        return 0.5
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_days = (now - created_at).total_seconds() / 86400
    if age_days <= RECENCY_FULL_DAYS:
        return 1.0
    if age_days >= RECENCY_ZERO_DAYS:
        return 0.0
    return 1.0 - (age_days - RECENCY_FULL_DAYS) / (RECENCY_ZERO_DAYS - RECENCY_FULL_DAYS)


def _impact_heuristic(title: str, summary: str) -> float:
    text = f"{title} {summary}".lower()
    hits = sum(1 for kw in HIGH_IMPACT_KEYWORDS if kw in text)
    return min(hits / 3, 1.0)


def compute_signal_score(signal: Signal) -> tuple[float, dict]:
    """Returns (final_score, breakdown_dict)."""
    w = _get_weights()
    recency = _recency_score(signal.created_at)
    impact = _impact_heuristic(signal.title or "", signal.summary or "")
    source_trust = 0.5  # default when no source attached
    if signal.source:
        source_trust = signal.source.trust_score or 0.5

    relevance = signal.relevance_score or 0.5
    novelty = signal.novelty_score or 0.5

    score = (
        w["relevance"] * relevance
        + w["novelty"] * novelty
        + w["impact"] * impact
        + w["source_trust"] * source_trust
        + w["recency"] * recency
    )
    final = round(min(score, 1.0), 4)
    breakdown = {
        "relevance": round(relevance, 4),
        "novelty": round(novelty, 4),
        "impact": round(impact, 4),
        "source_trust": round(source_trust, 4),
        "recency": round(recency, 4),
        "weights": w,
        "weighted_contributions": {
            "relevance": round(w["relevance"] * relevance, 4),
            "novelty": round(w["novelty"] * novelty, 4),
            "impact": round(w["impact"] * impact, 4),
            "source_trust": round(w["source_trust"] * source_trust, 4),
            "recency": round(w["recency"] * recency, 4),
        },
        "final_score": final,
    }
    return final, breakdown


def apply_signal_scores(db: Session, signals: list[Signal]):
    for signal in signals:
        score, breakdown = compute_signal_score(signal)
        signal.importance_score = score
        signal.score_breakdown = breakdown
    db.commit()


# ---------- Scenario mapping (deterministic keyword overlap) ----------

def _axis_pole_alignment(signal_tokens: set, pole_text: str) -> float:
    """
    Score how much a signal's tokens overlap with a pole description.
    Returns 0.0–1.0 (fraction of pole tokens matched by signal).
    """
    from app.services.relevance import _tokenize
    STOPWORDS = {"the", "and", "for", "that", "this", "with", "are", "was", "has",
                 "will", "would", "could", "when", "where", "which", "their", "into",
                 "from", "have", "been", "more", "than", "its", "also", "such"}
    pole_tokens = _tokenize(pole_text.lower()) - STOPWORDS
    if not pole_tokens or not signal_tokens:
        return 0.0
    return len(signal_tokens & pole_tokens) / len(pole_tokens)


def score_signal_vs_scenario(
    signal: Signal,
    scenario: Scenario,
    axis1,  # ScenarioAxis
    axis2,  # ScenarioAxis
) -> tuple[Optional[str], float]:
    """
    Score a signal's alignment with a scenario using axis-pole alignment.

    For each axis, compute how much the signal pushes toward the high pole vs the low pole.
    Combine the two axis scores based on which poles this scenario assumes.

    Returns (relationship_type, score):
      - relationship_type: 'supports' | 'weakens' | None
      - score: 0.0–1.0 (how strongly aligned)

    A signal SUPPORTS a scenario when it pushes toward both of its assumed poles.
    A signal WEAKENS a scenario when it consistently pushes toward the opposite poles.
    A signal is NEUTRAL (None) when it doesn't discriminate between scenarios.
    """
    from app.services.relevance import _tokenize
    STOPWORDS = {"the", "and", "for", "that", "this", "with", "are", "was", "has",
                 "will", "would", "could", "when", "where", "which", "their", "into",
                 "from", "have", "been", "more", "than", "its", "also", "such"}

    signal_text = f"{signal.title or ''} {signal.summary or ''}".lower()
    signal_tokens = _tokenize(signal_text) - STOPWORDS
    if not signal_tokens:
        return None, 0.0

    def _axis_net(axis) -> float:
        """Net alignment: positive = toward high pole, negative = toward low pole."""
        # Use pole_high_direction / pole_low_direction if available (richer text),
        # fall back to pole labels themselves
        high_text = (axis.driver.pole_high_direction or axis.pole_high or "") if hasattr(axis, 'driver') and axis.driver else (axis.pole_high or "")
        low_text = (axis.driver.pole_low_direction or axis.pole_low or "") if hasattr(axis, 'driver') and axis.driver else (axis.pole_low or "")
        score_high = _axis_pole_alignment(signal_tokens, high_text)
        score_low = _axis_pole_alignment(signal_tokens, low_text)
        return score_high - score_low  # positive = leans high, negative = leans low

    net1 = _axis_net(axis1)
    net2 = _axis_net(axis2)

    # Scenario's expected direction: +1 if pole is "high", -1 if "low"
    expected1 = 1.0 if (scenario.axis1_pole == "high") else -1.0
    expected2 = 1.0 if (scenario.axis2_pole == "high") else -1.0

    # Alignment = dot product of signal direction with scenario expectation
    alignment1 = net1 * expected1
    alignment2 = net2 * expected2
    combined = (alignment1 + alignment2) / 2.0

    # Thresholds: only map if there's meaningful discriminating signal
    SUPPORT_THRESHOLD = 0.04   # clearly pushes toward this scenario's poles
    WEAKEN_THRESHOLD = -0.04   # clearly pushes against this scenario's poles

    if combined >= SUPPORT_THRESHOLD:
        score = min(1.0, (combined + 0.04) / 0.25)  # normalize to 0–1
        return "supports", round(score, 3)
    if combined <= WEAKEN_THRESHOLD:
        score = min(1.0, (abs(combined) + 0.04) / 0.25)
        return "weakens", round(score, 3)
    return None, 0.0


def auto_map_signals_to_scenarios(db: Session, theme_id: UUID, new_signal_ids: list[UUID]):
    """
    Map signals to scenarios using axis-pole alignment scoring.
    Each signal is scored against each axis's pole descriptions — signals that
    discriminate between poles get mapped to the matching scenario(s) only.
    Signals that are equally relevant to all scenarios (topic overlap only) are not mapped.
    """
    from app.models.scenario_pipeline import ScenarioAxis
    from app.models.trend import Driver

    scenarios = db.query(Scenario).filter(Scenario.theme_id == theme_id).all()
    if not scenarios:
        return

    # Only do axis-pole mapping if scenarios carry pole info
    axes = (
        db.query(ScenarioAxis)
        .filter(ScenarioAxis.theme_id == theme_id, ScenarioAxis.user_confirmed == True)  # noqa: E712
        .order_by(ScenarioAxis.axis_number)
        .all()
    )

    # Eagerly load drivers for pole_high/low_direction
    for axis in axes:
        if axis.driver_id:
            axis.driver = db.get(Driver, axis.driver_id)
        else:
            axis.driver = None

    use_axis_scoring = (
        len(axes) >= 2
        and all(s.axis1_pole and s.axis2_pole for s in scenarios)
    )

    for signal_id in new_signal_ids:
        signal = db.get(Signal, signal_id)
        if not signal:
            continue

        for scenario in scenarios:
            existing = db.query(SignalScenario).filter_by(
                signal_id=signal_id, scenario_id=scenario.id
            ).first()
            if existing and existing.user_confirmed:
                continue

            if use_axis_scoring:
                rel, score = score_signal_vs_scenario(signal, scenario, axes[0], axes[1])
            else:
                # Fallback: topic overlap (old behaviour) when axes not yet confirmed
                rel, score = _topic_overlap_mapping(signal, scenario)

            if rel:
                if existing:
                    existing.relationship_type = rel
                    existing.relationship_score = score
                else:
                    db.add(SignalScenario(
                        signal_id=signal_id,
                        scenario_id=scenario.id,
                        relationship_type=rel,
                        relationship_score=score,
                        user_confirmed=False,
                    ))
            elif existing and not existing.user_confirmed:
                # Remove stale mapping that no longer aligns
                db.delete(existing)

    db.commit()


def _topic_overlap_mapping(signal: Signal, scenario: Scenario) -> tuple[Optional[str], float]:
    """Legacy topic-overlap fallback used before axes are confirmed."""
    from app.services.relevance import _tokenize
    signal_text = f"{signal.title or ''} {signal.summary or ''}".lower()
    assumptions_text = " ".join(str(a) for a in (scenario.assumptions or [])).lower()
    scenario_text = f"{scenario.name or ''} {scenario.narrative or ''} {assumptions_text}".lower()
    if not scenario_text.strip():
        return None, 0.0
    stopwords = {"the", "and", "for", "that", "this", "with", "are", "was", "has", "scenario"}
    signal_tokens = _tokenize(signal_text) - stopwords
    scenario_tokens = _tokenize(scenario_text) - stopwords
    if not signal_tokens or not scenario_tokens:
        return None, 0.0
    overlap = len(signal_tokens & scenario_tokens) / min(len(signal_tokens), len(scenario_tokens))
    if signal.steep_category and signal.steep_category.lower() in scenario_text:
        overlap += 0.08
    negation_words = {"not", "decline", "fail", "against", "ban", "block", "oppose", "stall", "reject"}
    negation_adjacent = bool((signal_tokens & scenario_tokens) & negation_words)
    if overlap > 0.08:
        return "weakens" if negation_adjacent else "supports", round(overlap, 3)
    return None, 0.0


# ---------- Scenario update engine ----------

def update_scenario_state(db: Session, scenario: Scenario):
    """
    Recompute confidence and momentum for a scenario from its signal links.
    Deterministic — no LLM. (per Decision Logic Specification)
    """
    from app.core.config import get_runtime_setting
    window_days = int(float(get_runtime_setting("scenario_window_days", SCENARIO_WINDOW_DAYS)))
    cutoff_all = datetime.now(timezone.utc) - timedelta(days=window_days)
    cutoff_recent = datetime.now(timezone.utc) - timedelta(days=7)

    links = (
        db.query(SignalScenario)
        .join(Signal, Signal.id == SignalScenario.signal_id)
        .filter(
            SignalScenario.scenario_id == scenario.id,
            Signal.created_at >= cutoff_all,
        )
        .all()
    )

    support = 0.0
    contradiction = 0.0
    recent_support = 0.0
    recent_contradiction = 0.0

    for link in links:
        signal = db.get(Signal, link.signal_id)
        if not signal:
            continue
        weight = (signal.importance_score or 0.5) * (link.relationship_score or 0.5)
        is_recent = signal.created_at and signal.created_at.replace(tzinfo=timezone.utc) >= cutoff_recent

        if link.relationship_type == "supports":
            support += weight
            if is_recent:
                recent_support += weight
        elif link.relationship_type == "weakens":
            contradiction += weight
            if is_recent:
                recent_contradiction += weight

    net = support - contradiction
    recent_delta = recent_support - recent_contradiction

    # Confidence mapping — normalize net score by total signal weight so that
    # themes with many signals don't automatically reach "high" confidence.
    # Uses the ratio of net support to total signal mass (support + contradiction).
    total_mass = support + contradiction
    if total_mass > 0:
        normalized_net = net / total_mass  # range: -1.0 to +1.0
    else:
        normalized_net = 0.0

    if normalized_net >= 0.5:
        confidence = "high"
    elif normalized_net >= 0.2:
        confidence = "medium"
    else:
        confidence = "low"

    # Momentum mapping
    if recent_delta >= MOMENTUM_UP:
        momentum = "increasing"
    elif recent_delta <= MOMENTUM_DOWN:
        momentum = "decreasing"
    else:
        momentum = "stable"

    scenario.support_score = round(support, 4)
    scenario.contradiction_score = round(contradiction, 4)
    scenario.internal_score = round(net, 4)
    scenario.recent_delta = round(recent_delta, 4)
    scenario.confidence_level = confidence
    scenario.momentum_state = momentum


def update_all_scenarios(db: Session, theme_id: UUID):
    scenarios = db.query(Scenario).filter(Scenario.theme_id == theme_id).all()
    for scenario in scenarios:
        update_scenario_state(db, scenario)
    db.commit()
    logger.info("Updated %d scenarios for theme %s", len(scenarios), theme_id)


# ---------- Change detection ----------

def detect_changes(db: Session, theme_id: UUID, run_id: UUID, previous_run_id: Optional[UUID]) -> dict:
    """
    Compare current run signals against previous run state.
    Returns a change summary dict (stored in monitoring run notes).
    """
    from app.models.crawl import CrawlRun

    current_signals = (
        db.query(Signal)
        .filter(Signal.theme_id == theme_id)
        .order_by(Signal.importance_score.desc())
        .limit(100)
        .all()
    )

    new_signals = []
    elevated_signals = []

    if previous_run_id:
        prev_run = db.get(CrawlRun, previous_run_id)
        prev_cutoff = prev_run.started_at if prev_run else None
        for signal in current_signals:
            created = signal.created_at
            if created and prev_cutoff:
                if created.replace(tzinfo=timezone.utc) > prev_cutoff.replace(tzinfo=timezone.utc):
                    new_signals.append(str(signal.id))
            if signal.importance_score and signal.importance_score >= 0.7:
                elevated_signals.append(str(signal.id))

    scenarios_changed = (
        db.query(Scenario)
        .filter(Scenario.theme_id == theme_id, Scenario.momentum_state != "stable")
        .count()
    )

    return {
        "new_signal_count": len(new_signals),
        "elevated_signal_count": len(elevated_signals),
        "scenarios_with_momentum_change": scenarios_changed,
        "new_signal_ids": new_signals[:10],
    }
