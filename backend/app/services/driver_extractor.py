"""
Driver Extractor — Pipeline Stage 14.

Extracts drivers of change from synthesized trends and scores each driver
on impact (1–10) and uncertainty (1–10).

Drivers with high impact + low uncertainty are flagged as 'predetermined elements'.
Drivers with high impact + high uncertainty become candidates for scenario axes.

Upserts drivers by trend_id so re-runs are idempotent.
"""
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.trend import Driver, Trend
from app.services.llm_gateway import extract_driver

logger = logging.getLogger(__name__)


def run_driver_extraction(theme_id: UUID, db: Session) -> list[Driver]:
    """
    Extract/update drivers for all trends of the given theme.
    Returns the list of upserted Driver records.
    """
    from app.models.theme import Theme
    theme = db.get(Theme, theme_id)
    if not theme:
        return []

    trends = db.query(Trend).filter(Trend.theme_id == theme_id).all()
    if not trends:
        return []

    drivers_upserted: list[Driver] = []

    for trend in trends:
        existing = db.query(Driver).filter(Driver.trend_id == trend.id).first()

        try:
            result = extract_driver(
                trend_name=trend.name,
                trend_description=trend.description or trend.name,
                theme_name=theme.name,
                time_horizon=theme.time_horizon or "10 years",
                direction=trend.direction or "",
                counterpole=trend.counterpole or "",
            )
        except Exception as e:
            logger.warning("Driver extraction failed for trend '%s': %s", trend.name, e)
            continue

        impact = float(result.get("impact_score", 5.0))
        uncertainty = float(result.get("uncertainty_score", 5.0))
        # Clamp to valid range
        impact = max(1.0, min(10.0, impact))
        uncertainty = max(1.0, min(10.0, uncertainty))
        is_predetermined = result.get("is_predetermined", impact >= 7 and uncertainty <= 3)

        if existing:
            existing.name = result.get("name", existing.name)
            existing.description = result.get("description", existing.description)
            existing.impact_score = impact
            existing.uncertainty_score = uncertainty
            existing.is_predetermined = is_predetermined
            existing.steep_domain = result.get("steep_domain", existing.steep_domain)
            existing.pole_high_direction = result.get("pole_high_direction", existing.pole_high_direction)
            existing.pole_low_direction = result.get("pole_low_direction", existing.pole_low_direction)
            driver = existing
        else:
            driver = Driver(
                theme_id=theme_id,
                trend_id=trend.id,
                name=result.get("name", trend.name),
                description=result.get("description"),
                impact_score=impact,
                uncertainty_score=uncertainty,
                is_predetermined=is_predetermined,
                steep_domain=result.get("steep_domain"),
                pole_high_direction=result.get("pole_high_direction"),
                pole_low_direction=result.get("pole_low_direction"),
            )
            db.add(driver)

        db.flush()
        drivers_upserted.append(driver)
        logger.info(
            "Driver upserted: '%s' (impact=%.1f, uncertainty=%.1f, predetermined=%s)",
            driver.name, driver.impact_score, driver.uncertainty_score, driver.is_predetermined,
        )

    db.commit()
    logger.info(
        "Driver extraction complete — theme: %s, drivers: %d",
        theme.name, len(drivers_upserted),
    )
    return drivers_upserted
