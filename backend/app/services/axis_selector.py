"""
Axis Selector — Pipeline Stage 15.

Selects the two highest-scoring critical uncertainty drivers as scenario axes
and proposes pole labels for each via LLM.

Normal run (force=False):
  - Skips if any axes already exist for the theme (idempotency guard)

Rebuild run (force=True):
  - Caller has already deleted non-locked axes
  - Locked axes are preserved and count toward the two slots
  - Only fills the remaining unlocked slots

Signal gate:
  - Candidates must have trend.signal_count >= matrix_signal_gate (DB setting, default 10)
  - Gate applies per selected axis post-ranking; if no candidates meet it, gate is relaxed

Opposition threshold:
  - Each candidate's pole directions are LLM-scored for genuine opposition
  - Candidates scoring below matrix_opposition_threshold (default 0.6) are excluded
  - If no candidates pass, threshold is relaxed
"""
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.scenario_pipeline import ScenarioAxis
from app.models.trend import Driver
from app.services.llm_gateway import (
    check_axis_independence,
    check_pole_opposition,
    propose_axis_poles,
    score_axis_pair_divergence,
)

logger = logging.getLogger(__name__)

MIN_IMPACT = 4.0
MIN_UNCERTAINTY = 4.0
MIN_DRIVERS = 2


def _get_driver_signal_count(driver: Driver) -> int:
    return driver.trend.signal_count if driver.trend else 0


def _select_best_pair(candidates: list, theme_name: str, pinned: Driver | None = None) -> list:
    """
    Select the best axis pair from candidates.

    If `pinned` is provided (locked axis driver), find the best partner for it
    from the candidates list.

    Otherwise, test all pairs from the top-4 candidates and pick the highest-divergence
    independent pair.
    """
    if pinned is not None:
        if not candidates:
            return [pinned]
        best_partner = None
        best_divergence = -1.0
        for candidate in candidates[:min(4, len(candidates))]:
            try:
                indep = check_axis_independence(
                    driver1_name=pinned.name,
                    driver1_description=pinned.description or pinned.name,
                    driver2_name=candidate.name,
                    driver2_description=candidate.description or candidate.name,
                )
                if not indep.get("independent", True):
                    logger.info(
                        "Pair ('%s', '%s') skipped — correlated: %s",
                        pinned.name, candidate.name, indep.get("correlation_reason", ""),
                    )
                    continue
            except Exception as e:
                logger.warning("Independence check failed for ('%s', '%s'): %s", pinned.name, candidate.name, e)

            try:
                div = score_axis_pair_divergence(
                    driver1_name=pinned.name,
                    driver1_pole_high=pinned.pole_high_direction or f"High {pinned.name}",
                    driver1_pole_low=pinned.pole_low_direction or f"Low {pinned.name}",
                    driver2_name=candidate.name,
                    driver2_pole_high=candidate.pole_high_direction or f"High {candidate.name}",
                    driver2_pole_low=candidate.pole_low_direction or f"Low {candidate.name}",
                    theme_name=theme_name,
                )
                divergence = float(div.get("divergence_score", 5.0))
            except Exception as e:
                logger.warning("Divergence scoring failed for ('%s', '%s'): %s", pinned.name, candidate.name, e)
                divergence = 5.0

            if divergence > best_divergence:
                best_divergence = divergence
                best_partner = candidate

        if best_partner:
            logger.info("Selected partner '%s' for locked axis '%s' (divergence=%.1f)", best_partner.name, pinned.name, best_divergence)
            return [pinned, best_partner]
        logger.warning("No independent partner found for '%s' — falling back to top candidate", pinned.name)
        return [pinned, candidates[0]]

    # No pinned axis — test all pairs in the top-4
    if len(candidates) < 2:
        return candidates[:2]

    pool = candidates[:min(4, len(candidates))]
    best_pair = None
    best_divergence = -1.0

    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            d1, d2 = pool[i], pool[j]

            try:
                indep = check_axis_independence(
                    driver1_name=d1.name,
                    driver1_description=d1.description or d1.name,
                    driver2_name=d2.name,
                    driver2_description=d2.description or d2.name,
                )
                if not indep.get("independent", True):
                    logger.info(
                        "Pair ('%s', '%s') skipped — correlated: %s",
                        d1.name, d2.name, indep.get("correlation_reason", ""),
                    )
                    continue
            except Exception as e:
                logger.warning("Independence check failed for ('%s', '%s'): %s", d1.name, d2.name, e)

            try:
                div = score_axis_pair_divergence(
                    driver1_name=d1.name,
                    driver1_pole_high=d1.pole_high_direction or f"High {d1.name}",
                    driver1_pole_low=d1.pole_low_direction or f"Low {d1.name}",
                    driver2_name=d2.name,
                    driver2_pole_high=d2.pole_high_direction or f"High {d2.name}",
                    driver2_pole_low=d2.pole_low_direction or f"Low {d2.name}",
                    theme_name=theme_name,
                )
                divergence = float(div.get("divergence_score", 5.0))
                logger.info("Pair ('%s', '%s') divergence=%.1f", d1.name, d2.name, divergence)
            except Exception as e:
                logger.warning("Divergence scoring failed for ('%s', '%s'): %s", d1.name, d2.name, e)
                divergence = 5.0

            if divergence > best_divergence:
                best_divergence = divergence
                best_pair = [d1, d2]

    if best_pair:
        logger.info("Selected pair: '%s' + '%s' (divergence=%.1f)", best_pair[0].name, best_pair[1].name, best_divergence)
        return best_pair

    logger.warning("Pair scoring inconclusive — falling back to top-2 by impact×uncertainty")
    return candidates[:2]


def run_axis_selection(theme_id: UUID, db: Session, force: bool = False) -> list[ScenarioAxis] | None:
    """
    Propose scenario axes for the theme.

    force=False: returns None if any axes already exist (pipeline idempotency).
    force=True:  assumes non-locked axes have already been deleted; fills remaining slots.
    """
    from app.core.config import get_runtime_setting
    from app.models.theme import Theme

    theme = db.get(Theme, theme_id)
    if not theme:
        return None

    existing_axes = db.query(ScenarioAxis).filter(ScenarioAxis.theme_id == theme_id).all()
    locked_axes = [a for a in existing_axes if a.axis_locked]

    if not force and existing_axes:
        logger.info("Axis selection skipped — axes already exist for theme '%s'", theme.name)
        return None

    slots_needed = 2 - len(locked_axes)

    if slots_needed == 0:
        logger.info("Both axes locked for theme '%s' — no selection needed", theme.name)
        return locked_axes

    # Read configurable thresholds
    gate_threshold = int(float(get_runtime_setting("matrix_signal_gate", "10")))
    opposition_threshold = float(get_runtime_setting("matrix_opposition_threshold", "0.6"))

    locked_driver_ids = {a.driver_id for a in locked_axes if a.driver_id}

    # Get all non-predetermined candidates not already locked
    all_candidates = (
        db.query(Driver)
        .filter(
            Driver.theme_id == theme_id,
            Driver.is_predetermined == False,  # noqa: E712
        )
        .all()
    )
    all_candidates = [d for d in all_candidates if d.id not in locked_driver_ids]

    # Apply signal gate
    eligible = [d for d in all_candidates if _get_driver_signal_count(d) >= gate_threshold]
    if not eligible:
        logger.info(
            "Signal gate=%d relaxed for theme '%s' — %d candidates below threshold",
            gate_threshold, theme.name, len(all_candidates),
        )
        eligible = all_candidates

    if not eligible:
        logger.info(
            "Axis selection skipped — no eligible drivers for theme '%s' (need %d slots)",
            theme.name, slots_needed,
        )
        return locked_axes or None

    # Apply opposition threshold (LLM per-driver check)
    qualified = []
    for driver in eligible:
        if driver.pole_high_direction and driver.pole_low_direction:
            try:
                result = check_pole_opposition(
                    pole_low=driver.pole_low_direction,
                    pole_high=driver.pole_high_direction,
                    driver_name=driver.name,
                )
                score = float(result.get("opposition_score", 1.0))
                if score < opposition_threshold:
                    logger.info(
                        "Driver '%s' excluded — opposition_score=%.2f < threshold %.2f",
                        driver.name, score, opposition_threshold,
                    )
                    continue
            except Exception as e:
                logger.warning("Opposition check failed for '%s': %s — including anyway", driver.name, e)
        qualified.append(driver)

    if not qualified:
        logger.info("Opposition threshold relaxed for theme '%s' — using all eligible candidates", theme.name)
        qualified = eligible

    if len(qualified) < slots_needed:
        logger.warning(
            "Only %d qualified driver(s) for %d needed slot(s) in theme '%s'",
            len(qualified), slots_needed, theme.name,
        )
        if not qualified:
            return locked_axes or None

    # Rank by impact × uncertainty
    qualified.sort(key=lambda d: d.impact_score * d.uncertainty_score, reverse=True)

    # Select drivers for open slots
    if slots_needed == 2:
        selected_drivers = _select_best_pair(qualified, theme.name)
    else:
        # One locked axis — find the best partner for it
        locked_driver = None
        if locked_axes and locked_axes[0].driver_id:
            locked_driver = db.get(Driver, locked_axes[0].driver_id)
        pair = _select_best_pair(qualified, theme.name, pinned=locked_driver)
        # Take only the unlocked driver (not the pinned one)
        selected_drivers = [d for d in pair if d.id not in locked_driver_ids][:1]

    # Determine which axis_number slots are open
    used_numbers = {a.axis_number for a in locked_axes}
    open_numbers = [n for n in [1, 2] if n not in used_numbers]

    new_axes: list[ScenarioAxis] = []
    for driver, axis_number in zip(selected_drivers, open_numbers):
        try:
            poles = propose_axis_poles(
                driver_name=driver.name,
                driver_description=driver.description or driver.name,
                theme_name=theme.name,
            )
        except Exception as e:
            logger.warning("Pole proposal failed for driver '%s': %s", driver.name, e)
            poles = {
                "pole_low": driver.pole_low_direction or f"Low {driver.name}",
                "pole_high": driver.pole_high_direction or f"High {driver.name}",
                "rationale": (
                    f"Driver selected with impact={driver.impact_score:.1f}, "
                    f"uncertainty={driver.uncertainty_score:.1f}"
                ),
            }

        axis = ScenarioAxis(
            theme_id=theme_id,
            axis_number=axis_number,
            driver_id=driver.id,
            driver_name=driver.name,
            pole_low=poles.get("pole_low", f"Low {driver.name}"),
            pole_high=poles.get("pole_high", f"High {driver.name}"),
            rationale=poles.get("rationale"),
            user_confirmed=False,
            axis_locked=False,
        )
        db.add(axis)
        db.flush()
        new_axes.append(axis)
        logger.info(
            "Axis %d proposed: '%s' | '%s' ↔ '%s'",
            axis_number, driver.name, axis.pole_low[:40], axis.pole_high[:40],
        )

    db.commit()
    logger.info(
        "Axis selection complete — theme: %s, new axes: %d, locked axes: %d",
        theme.name, len(new_axes), len(locked_axes),
    )
    return locked_axes + new_axes
