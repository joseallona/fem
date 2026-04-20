"""
Trend Synthesizer — Pipeline Stage 13.

Two-pass approach:
  Pass 1 — keyword clusters (from Stage 11b clustering): precise groupings
            based on token overlap. Any multi-member cluster becomes a trend.
  Pass 2 — STEEP+horizon fallback: for signals not covered by a keyword cluster,
            group by (steep_category, horizon) and synthesize additional trends.
            This handles the common case where signals are semantically related
            but lexically diverse (different vocabulary for same topic).

Upserts trends by cluster_id / group key so re-runs are idempotent.
"""
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.signal import Signal
from app.models.trend import Trend
from app.services.llm_gateway import synthesize_trend

logger = logging.getLogger(__name__)

MIN_CLUSTER_SIZE = 3        # minimum signals per group to synthesize a trend
MIN_STEEP_GROUP_SIZE = 3    # same threshold for STEEP+horizon fallback groups


def run_trend_synthesis(theme_id: UUID, db: Session) -> list[Trend]:
    """
    Synthesize trends using keyword clusters (Pass 1) and STEEP+horizon
    grouping for remaining signals (Pass 2).
    Returns the list of upserted Trend records.
    """
    from app.models.theme import Theme
    theme = db.get(Theme, theme_id)
    if not theme:
        return []

    signals = (
        db.query(Signal)
        .filter(Signal.theme_id == theme_id, Signal.status == "active")
        .all()
    )
    if not signals:
        return []

    trends_upserted: list[Trend] = []
    covered_signal_ids: set[str] = set()

    # ── Pass 1: keyword clusters ───────────────────────────────────────────
    keyword_clusters: dict[str, list[Signal]] = {}
    for sig in signals:
        cid = sig.cluster_id
        if cid and not cid.startswith("solo_"):
            keyword_clusters.setdefault(cid, []).append(sig)

    for cluster_id, members in keyword_clusters.items():
        if len(members) < MIN_CLUSTER_SIZE:
            continue
        trend = _upsert_trend(cluster_id, members, theme, db)
        if trend:
            trends_upserted.append(trend)
            covered_signal_ids.update(str(s.id) for s in members)

    # ── Pass 2: STEEP+horizon fallback for uncovered signals ───────────────
    uncovered = [s for s in signals if str(s.id) not in covered_signal_ids]
    steep_groups = _group_by_steep_horizon(uncovered)

    for group_key, members in steep_groups.items():
        # Skip if a trend for this group already exists (idempotent on re-run)
        trend = _upsert_trend(group_key, members, theme, db)
        if trend:
            trends_upserted.append(trend)

    db.commit()
    logger.info(
        "Trend synthesis complete — theme: %s, trends: %d "
        "(pass1 keyword: %d, pass2 steep: %d)",
        theme.name,
        len(trends_upserted),
        sum(1 for t in trends_upserted if not t.cluster_id.startswith("steep_")),
        sum(1 for t in trends_upserted if t.cluster_id.startswith("steep_")),
    )
    return trends_upserted


def _upsert_trend(group_key: str, members: list[Signal], theme, db: Session) -> Trend | None:
    existing = db.query(Trend).filter(
        Trend.theme_id == theme.id,
        Trend.cluster_id == group_key,
    ).first()

    signal_dicts = [
        {
            "title": s.title,
            "summary": s.summary or "",
            "steep_category": s.steep_category or "unknown",
            "horizon": s.horizon or "H2",
        }
        for s in members
    ]

    avg_momentum = sum(s.importance_score or 0.5 for s in members) / len(members)
    avg_alignment = sum(s.relevance_score or 0.5 for s in members) / len(members)

    try:
        result = synthesize_trend(
            signals=signal_dicts,
            theme_name=theme.name,
            focal_question=theme.focal_question or theme.name,
        )
    except Exception as e:
        logger.warning("Trend synthesis LLM failed for group %s: %s", group_key, e)
        return None

    if existing:
        existing.name = result.get("name", existing.name)
        existing.description = result.get("description", existing.description)
        existing.direction = result.get("direction", existing.direction)
        existing.counterpole = result.get("counterpole", existing.counterpole)
        existing.steep_domains = result.get("steep_domains", existing.steep_domains)
        existing.s_curve_position = result.get("s_curve_position", existing.s_curve_position)
        existing.horizon = result.get("horizon", existing.horizon)
        existing.signal_count = len(members)
        existing.momentum = avg_momentum
        existing.ontology_alignment = avg_alignment
        existing.supporting_signal_ids = [str(s.id) for s in members]
        trend = existing
    else:
        trend = Trend(
            theme_id=theme.id,
            cluster_id=group_key,
            name=result.get("name", f"Trend {group_key}"),
            description=result.get("description"),
            direction=result.get("direction"),
            counterpole=result.get("counterpole"),
            steep_domains=result.get("steep_domains", []),
            s_curve_position=result.get("s_curve_position", "emerging"),
            horizon=result.get("horizon", "H2"),
            signal_count=len(members),
            momentum=avg_momentum,
            ontology_alignment=avg_alignment,
            supporting_signal_ids=[str(s.id) for s in members],
        )
        db.add(trend)

    db.flush()
    logger.info("Trend upserted: '%s' (%d signals, group=%s)", trend.name, len(members), group_key)
    return trend


def _group_by_steep_horizon(signals: list[Signal]) -> dict[str, list[Signal]]:
    """
    Group signals by (steep_category, horizon).
    Key format: 'steep_{category}_{horizon}' — stable across re-runs.
    Returns only groups with >= MIN_STEEP_GROUP_SIZE members.
    """
    groups: dict[str, list[Signal]] = {}
    for sig in signals:
        cat = (sig.steep_category or "unknown").lower()
        horizon = (sig.horizon or "H2").upper()
        key = f"steep_{cat}_{horizon}"
        groups.setdefault(key, []).append(sig)
    return {k: v for k, v in groups.items() if len(v) >= MIN_STEEP_GROUP_SIZE}
