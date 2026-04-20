"""
Scenario Monitor — Pipeline Stage 16.

Runs after each pipeline cycle once scenarios are live (Gate 2 passed).
For each scenario's early indicators, scans new signals for keyword matches
and updates match counts, timestamps, and relative probability scores.

Generates alerts when:
  - A scenario's score increases > 15% in one run (yellow alert)
  - A scenario reaches > 50% of total score mass (red alert — dominant)
  - Scores split nearly evenly between two opposing scenarios (divergence alert)
"""
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.scenario import Scenario
from app.models.scenario_pipeline import ScenarioIndicator
from app.models.signal import Signal

logger = logging.getLogger(__name__)

YELLOW_ALERT_DELTA = 0.15   # 15% relative increase triggers yellow alert
RED_ALERT_THRESHOLD = 0.50  # 50% of score mass → dominant scenario
DIVERGENCE_THRESHOLD = 0.40  # top two scenarios each > 40% → divergence


def _tokenize(text: str) -> set[str]:
    stopwords = {"a", "an", "the", "and", "or", "in", "on", "at", "to", "for",
                 "of", "with", "by", "is", "are", "was", "were", "this", "that"}
    return {t for t in re.findall(r"[a-z]{3,}", text.lower()) if t not in stopwords}


def _matches_query(signal: Signal, monitoring_query: str) -> bool:
    if not monitoring_query:
        return False
    query_tokens = _tokenize(monitoring_query)
    signal_tokens = _tokenize(f"{signal.title or ''} {signal.summary or ''}")
    if not query_tokens:
        return False
    overlap = len(query_tokens & signal_tokens) / len(query_tokens)
    return overlap >= 0.3


def run_scenario_monitoring(theme_id: UUID, db: Session, new_signal_ids: list | None = None) -> dict:
    """
    Update indicator match counts for all live scenarios of the theme.
    Returns a monitoring report dict with alerts.
    """
    scenarios = (
        db.query(Scenario)
        .filter(Scenario.theme_id == theme_id)
        .all()
    )
    if not scenarios:
        return {"alerts": [], "scenario_scores": {}}

    # Fetch new signals (if not passed, scan all active signals from last 24h)
    if new_signal_ids:
        new_signals = [db.get(Signal, sid) for sid in new_signal_ids if db.get(Signal, sid)]
    else:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        new_signals = (
            db.query(Signal)
            .filter(Signal.theme_id == theme_id, Signal.created_at >= cutoff)
            .all()
        )

    if not new_signals:
        return {"alerts": [], "scenario_scores": {s.id: s.support_score for s in scenarios}}

    # Previous scores for delta calculation
    prev_scores = {s.id: s.support_score for s in scenarios}

    # Match new signals against each scenario's indicators
    scenario_match_counts: dict[UUID, int] = {s.id: 0 for s in scenarios}

    for scenario in scenarios:
        indicators = (
            db.query(ScenarioIndicator)
            .filter(ScenarioIndicator.scenario_id == scenario.id)
            .all()
        )
        for indicator in indicators:
            for signal in new_signals:
                if _matches_query(signal, indicator.monitoring_query or indicator.description):
                    indicator.match_count += 1
                    indicator.last_match_at = datetime.now(timezone.utc)
                    indicator.last_signal_id = signal.id
                    scenario_match_counts[scenario.id] += 1

    db.flush()

    # support_score is owned by update_scenario_state (scoring.py Stage 11).
    # The monitor must NOT overwrite it — doing so creates a feedback loop where
    # the inflated link-based score becomes the decay base and locks at 1.0.
    # Here we only use support_score read-only to compute relative weights for alerts.

    # Compute relative probability weights from the link-based scores set by Stage 11
    total_score = sum(s.support_score for s in scenarios) or 1.0
    relative_weights = {s.id: s.support_score / total_score for s in scenarios}

    # Generate alerts
    alerts: list[dict] = []

    for scenario in scenarios:
        prev = prev_scores.get(scenario.id, 0.0)
        current = scenario.support_score
        weight = relative_weights[scenario.id]

        if prev > 0 and (current - prev) / prev >= YELLOW_ALERT_DELTA:
            alerts.append({
                "level": "yellow",
                "scenario_id": str(scenario.id),
                "scenario_name": scenario.name,
                "message": f"Scenario '{scenario.name}' gained {((current-prev)/prev*100):.0f}% support this run.",
            })

        if weight >= RED_ALERT_THRESHOLD:
            alerts.append({
                "level": "red",
                "scenario_id": str(scenario.id),
                "scenario_name": scenario.name,
                "message": f"Scenario '{scenario.name}' now dominates with {weight*100:.0f}% of signal support.",
            })

    # Divergence check: two scenarios neck-and-neck
    weights_sorted = sorted(relative_weights.values(), reverse=True)
    if len(weights_sorted) >= 2 and weights_sorted[0] >= DIVERGENCE_THRESHOLD and weights_sorted[1] >= DIVERGENCE_THRESHOLD:
        alerts.append({
            "level": "divergence",
            "scenario_id": None,
            "scenario_name": None,
            "message": "Signal evidence is splitting across two competing scenarios — high uncertainty moment.",
        })

    db.commit()

    report = {
        "alerts": alerts,
        "scenario_scores": {str(s.id): s.support_score for s in scenarios},
        "relative_weights": {str(sid): w for sid, w in relative_weights.items()},
        "signals_scanned": len(new_signals),
        "total_indicator_matches": sum(scenario_match_counts.values()),
    }

    if alerts:
        logger.info(
            "Monitoring alerts for theme %s: %s",
            theme_id,
            [a["level"] for a in alerts],
        )

    return report
