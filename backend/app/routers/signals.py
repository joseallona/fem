from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.signal import Signal, UserFeedback
from app.models.theme import Theme
from app.schemas.signal import FeedbackCreate, FeedbackOut, SignalCreate, SignalOut, SignalUpdate

router = APIRouter(tags=["signals"])


def _get_theme_or_404(theme_id: UUID, db: Session) -> Theme:
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    return theme


@router.get("/themes/{theme_id}/signals", response_model=List[SignalOut])
def list_signals(
    theme_id: UUID,
    signal_type: Optional[str] = None,
    steep_category: Optional[str] = None,
    horizon: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    _get_theme_or_404(theme_id, db)
    q = db.query(Signal).filter(Signal.theme_id == theme_id)
    if signal_type:
        q = q.filter(Signal.signal_type == signal_type)
    if steep_category:
        q = q.filter(Signal.steep_category == steep_category)
    if horizon:
        q = q.filter(Signal.horizon == horizon)
    if status:
        q = q.filter(Signal.status == status)
    return q.order_by(Signal.importance_score.desc()).offset(offset).limit(limit).all()


@router.post("/themes/{theme_id}/signals", response_model=SignalOut, status_code=status.HTTP_201_CREATED)
def create_signal(theme_id: UUID, body: SignalCreate, db: Session = Depends(get_db)):
    _get_theme_or_404(theme_id, db)
    signal = Signal(theme_id=theme_id, **body.model_dump())
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


@router.get("/signals/{signal_id}", response_model=SignalOut)
def get_signal(signal_id: UUID, db: Session = Depends(get_db)):
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal


@router.patch("/signals/{signal_id}", response_model=SignalOut)
def update_signal(signal_id: UUID, body: SignalUpdate, db: Session = Depends(get_db)):
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(signal, field, value)
    db.commit()
    db.refresh(signal)
    return signal


@router.get("/signals/{signal_id}/explanation")
def get_signal_explanation(signal_id: UUID, db: Session = Depends(get_db)):
    """
    Return the score breakdown for a signal.
    If score_breakdown is missing (signal scored before this feature), compute it on-the-fly.
    """
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    breakdown = signal.score_breakdown
    if not breakdown:
        from app.services.scoring import compute_signal_score
        _, breakdown = compute_signal_score(signal)

    return {
        "signal_id": str(signal_id),
        "title": signal.title,
        "importance_score": signal.importance_score,
        "score_breakdown": breakdown,
    }


@router.post("/signals/{signal_id}/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def add_feedback(signal_id: UUID, body: FeedbackCreate, db: Session = Depends(get_db)):
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    feedback = UserFeedback(signal_id=signal_id, **body.model_dump())
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.post("/themes/{theme_id}/signal-clusters", response_model=Dict[str, List[str]])
def run_clustering(theme_id: UUID, db: Session = Depends(get_db)):
    """
    Trigger signal clustering for a theme. Returns {cluster_id: [signal_id, ...]}.
    Assigns cluster_id on each signal and persists the result.
    """
    _get_theme_or_404(theme_id, db)
    from app.services.clustering import run_clustering_for_theme
    return run_clustering_for_theme(theme_id, db)


@router.get("/themes/{theme_id}/signal-clusters", response_model=Dict[str, List[SignalOut]])
def get_clusters(theme_id: UUID, db: Session = Depends(get_db)):
    """
    Return current clusters for a theme — only multi-signal clusters.
    Signals without a cluster_id or in singleton clusters are excluded.
    """
    _get_theme_or_404(theme_id, db)
    signals = (
        db.query(Signal)
        .filter(
            Signal.theme_id == theme_id,
            Signal.status == "active",
            Signal.cluster_id.isnot(None),
            ~Signal.cluster_id.like("solo_%"),
        )
        .all()
    )
    clusters: Dict[str, List[Any]] = {}
    for s in signals:
        clusters.setdefault(s.cluster_id, []).append(s)
    return clusters
