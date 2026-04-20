"""
Scenario Generator — triggered after Gate 1 (axis confirmation).

Generates 4 scenario drafts (one per quadrant of the 2×2 axis matrix)
using LLM and saves them as ScenarioDraft records with status='draft'.

Quadrant mapping:
  Q1: axis1=high, axis2=high
  Q2: axis1=low,  axis2=high
  Q3: axis1=low,  axis2=low
  Q4: axis1=high, axis2=low
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.scenario_pipeline import ScenarioDraft, ScenarioAxis
from app.models.signal import Signal
from app.models.trend import Driver
from app.services.llm_gateway import generate_scenario_draft

logger = logging.getLogger(__name__)

QUADRANTS = [
    ("Q1", "high", "high"),
    ("Q2", "low",  "high"),
    ("Q3", "low",  "low"),
    ("Q4", "high", "low"),
]

# Diagonal opposites: each quadrant maps to the quadrant across the matrix
DIAGONAL = {"Q1": "Q3", "Q2": "Q4", "Q3": "Q1", "Q4": "Q2"}

def _opposite_pole(pole: str) -> str:
    return "low" if pole == "high" else "high"


def run_scenario_generation(theme_id: str, db: Session | None = None) -> list[ScenarioDraft]:
    """
    Generate 4 scenario drafts for the theme.
    Can be called directly (pass db) or as an RQ background job (db=None creates its own session).
    """
    from app.core.database import SessionLocal

    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        return _generate(theme_id, db)
    except Exception as e:
        logger.exception("Scenario generation failed for theme %s: %s", theme_id, e)
        if own_session:
            db.rollback()
        raise
    finally:
        if own_session:
            db.close()


def _generate(theme_id: str, db: Session) -> list[ScenarioDraft]:
    from app.models.theme import Theme

    theme = db.get(Theme, theme_id)
    if not theme:
        raise ValueError(f"Theme not found: {theme_id}")

    # Get confirmed axes
    axes = (
        db.query(ScenarioAxis)
        .filter(
            ScenarioAxis.theme_id == theme_id,
            ScenarioAxis.user_confirmed == True,  # noqa: E712
        )
        .order_by(ScenarioAxis.axis_number)
        .all()
    )
    if len(axes) < 2:
        raise ValueError("Cannot generate scenarios — axes not confirmed (Gate 1 not passed)")

    axis1, axis2 = axes[0], axes[1]

    # Delete any existing drafts (allow regeneration)
    db.query(ScenarioDraft).filter(
        ScenarioDraft.theme_id == theme_id,
        ScenarioDraft.status == "draft",
    ).delete()
    db.flush()

    # Build context: top signals by importance
    top_signals = (
        db.query(Signal)
        .filter(Signal.theme_id == theme_id, Signal.status == "active")
        .order_by(Signal.importance_score.desc())
        .limit(30)
        .all()
    )
    signals_text = "\n".join(
        f"- [{s.steep_category}|{s.horizon}] {s.title} — {(s.summary or '')[:100]}"
        for s in top_signals
    )

    # Collect predetermined elements
    predetermined = (
        db.query(Driver)
        .filter(Driver.theme_id == theme_id, Driver.is_predetermined == True)  # noqa: E712
        .all()
    )
    predetermined_labels = [f"{d.name}: {(d.description or '')[:80]}" for d in predetermined]

    drafts: list[ScenarioDraft] = []

    for quadrant, pole1, pole2 in QUADRANTS:
        axis1_label = axis1.pole_high if pole1 == "high" else axis1.pole_low
        axis2_label = axis2.pole_high if pole2 == "high" else axis2.pole_low

        # Diagonal opposite poles (for divergence instruction)
        diag_axis1_label = axis1.pole_low if pole1 == "high" else axis1.pole_high
        diag_axis2_label = axis2.pole_low if pole2 == "high" else axis2.pole_high

        logger.info(
            "Generating %s: %s=%s | %s=%s (diagonal: %s | %s)",
            quadrant, axis1.driver_name, pole1, axis2.driver_name, pole2,
            diag_axis1_label[:30], diag_axis2_label[:30],
        )

        try:
            result = generate_scenario_draft(
                theme_name=theme.name,
                focal_question=theme.focal_question or theme.name,
                time_horizon=theme.time_horizon or "10 years",
                axis1_name=axis1.driver_name or "Axis 1",
                axis1_pole=axis1_label,
                axis2_name=axis2.driver_name or "Axis 2",
                axis2_pole=axis2_label,
                signals_text=signals_text,
                predetermined_elements=predetermined_labels,
                diagonal_axis1_pole=diag_axis1_label,
                diagonal_axis2_pole=diag_axis2_label,
            )
            logger.info("LLM result for %s — keys: %s, name: %r", quadrant, list(result.keys()), result.get("name") or result.get("title") or result.get("scenario_name"))
        except Exception as e:
            logger.warning("LLM generation failed for %s: %s — using placeholder", quadrant, e)
            result = {
                "name": f"Scenario {quadrant}",
                "narrative": f"A world where {axis1_label} and {axis2_label}.",
                "key_characteristics": [],
                "stakeholder_implications": "",
                "early_indicators": [],
                "opportunities": [],
                "threats": [],
            }

        # Resolve name — LLM models vary in which key they use
        scenario_name = (
            result.get("name")
            or result.get("title")
            or result.get("scenario_name")
            or result.get("scenario_title")
            or f"Scenario {quadrant}"
        )

        draft = ScenarioDraft(
            theme_id=theme_id,
            quadrant=quadrant,
            axis1_pole=pole1,
            axis2_pole=pole2,
            name=scenario_name,
            narrative=result.get("narrative"),
            key_characteristics=result.get("key_characteristics", []),
            stakeholder_implications=result.get("stakeholder_implications"),
            early_indicators=result.get("early_indicators", []),
            opportunities=result.get("opportunities", []),
            threats=result.get("threats", []),
            status="draft",
        )
        db.add(draft)
        db.flush()
        drafts.append(draft)

    db.commit()
    logger.info("Scenario generation complete — theme: %s, drafts: %d", theme.name, len(drafts))
    return drafts
