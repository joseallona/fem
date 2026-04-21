"""
Signal Linker — Pipeline Stage 11c.

Builds a knowledge graph of signal relationships using three layers:

  Layer 1 — Cluster links (free, synchronous)
    Signals sharing a cluster_id are linked with strength 1.0.
    This formalises what clustering already implies.

  Layer 2 — Embedding similarity (semantic)
    Embeddings are computed for any signal missing one, then cosine similarity
    is measured pairwise within the theme. Pairs above EMBEDDING_THRESHOLD
    are linked with strength = cosine score.

  Layer 3 — LLM reasoning (selective)
    High-similarity pairs (>= LLM_TRIGGER_THRESHOLD) that are NOT already
    cluster-linked get an LLM call to confirm the connection and classify it
    as reinforcing or tensioning. Unrelated pairs are not stored.
    Capped at MAX_LLM_PAIRS per run to bound cost.

All layers are idempotent — re-running on the same theme updates existing links
and adds new ones without duplicating.
"""
import json
import logging
import math
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.signal import Signal, SignalLink
from app.services.llm_gateway import get_embedding, reason_signal_link

logger = logging.getLogger(__name__)

EMBEDDING_THRESHOLD = 0.78   # cosine similarity to create an embedding link
LLM_TRIGGER_THRESHOLD = 0.82 # cosine similarity to also run LLM reasoning
MAX_LLM_PAIRS = 30           # max LLM calls per theme per run


def run_signal_linking(theme_id: UUID, db: Session) -> int:
    """
    Run all three linking layers for the given theme.
    Returns total number of links created or updated.
    """
    signals = (
        db.query(Signal)
        .filter(Signal.theme_id == theme_id, Signal.status == "active")
        .all()
    )
    if len(signals) < 2:
        return 0

    from app.models.theme import Theme
    theme = db.get(Theme, theme_id)
    theme_name = theme.name if theme else ""

    total = 0
    total += _layer1_cluster_links(signals, db)
    total += _layer2_embedding_links(signals, theme_name, db)
    db.commit()

    logger.info("Signal linking complete — theme: %s, links created/updated: %d", theme_name, total)
    return total


def _upsert_link(
    db: Session,
    id_a: UUID,
    id_b: UUID,
    link_type: str,
    strength: float,
    relationship_type: str | None = None,
) -> bool:
    """
    Insert or update a signal link. Always stores with the smaller UUID as signal_a_id.
    Returns True if a new link was created.
    """
    a, b = (id_a, id_b) if str(id_a) < str(id_b) else (id_b, id_a)
    existing = db.get(SignalLink, (a, b))
    if existing:
        if strength > existing.strength:
            existing.strength = strength
            existing.link_type = link_type
        if relationship_type and not existing.relationship_type:
            existing.relationship_type = relationship_type
        return False
    link = SignalLink(
        signal_a_id=a,
        signal_b_id=b,
        link_type=link_type,
        strength=strength,
        relationship_type=relationship_type,
    )
    db.add(link)
    return True


def _cluster_linked(db: Session, id_a: UUID, id_b: UUID) -> bool:
    a, b = (id_a, id_b) if str(id_a) < str(id_b) else (id_b, id_a)
    existing = db.get(SignalLink, (a, b))
    return existing is not None and existing.link_type == "cluster"


def _layer1_cluster_links(signals: list[Signal], db: Session) -> int:
    groups: dict[str, list[Signal]] = {}
    for sig in signals:
        cid = sig.cluster_id
        if cid and not cid.startswith("solo_"):
            groups.setdefault(cid, []).append(sig)

    created = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                if _upsert_link(db, members[i].id, members[j].id, "cluster", 1.0):
                    created += 1
    logger.debug("Layer 1 (cluster): %d links", created)
    return created


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _ensure_embeddings(signals: list[Signal], db: Session) -> dict[UUID, list[float]]:
    embeddings: dict[UUID, list[float]] = {}
    for sig in signals:
        if sig.embedding:
            embeddings[sig.id] = json.loads(sig.embedding)
        else:
            try:
                text = f"{sig.title}. {sig.summary or ''}"
                vec = get_embedding(text)
                sig.embedding = json.dumps(vec)
                embeddings[sig.id] = vec
            except Exception as e:
                logger.warning("Embedding failed for signal %s: %s", sig.id, e)
    db.flush()
    return embeddings


def _layer2_embedding_links(signals: list[Signal], theme_name: str, db: Session) -> int:
    embeddings = _ensure_embeddings(signals, db)
    ids = [s.id for s in signals if s.id in embeddings]
    vecs = [embeddings[sid] for sid in ids]

    created = 0
    llm_candidates: list[tuple[UUID, UUID, float, Signal, Signal]] = []
    sig_by_id = {s.id: s for s in signals}

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            score = _cosine(vecs[i], vecs[j])
            if score < EMBEDDING_THRESHOLD:
                continue
            id_a, id_b = ids[i], ids[j]
            if not _cluster_linked(db, id_a, id_b):
                if _upsert_link(db, id_a, id_b, "embedding", round(score, 4)):
                    created += 1
                if score >= LLM_TRIGGER_THRESHOLD:
                    llm_candidates.append((id_a, id_b, score, sig_by_id[id_a], sig_by_id[id_b]))

    logger.debug("Layer 2 (embedding): %d links, %d LLM candidates", created, len(llm_candidates))

    # Layer 3: LLM reasoning on top candidates
    llm_candidates.sort(key=lambda x: x[2], reverse=True)
    llm_calls = 0
    for id_a, id_b, score, sig_a, sig_b in llm_candidates[:MAX_LLM_PAIRS]:
        try:
            result = reason_signal_link(
                title_a=sig_a.title,
                summary_a=sig_a.summary or "",
                title_b=sig_b.title,
                summary_b=sig_b.summary or "",
                theme_name=theme_name,
            )
            if result.get("connected"):
                _upsert_link(db, id_a, id_b, "llm", round(score, 4), result.get("relationship"))
            llm_calls += 1
        except Exception as e:
            logger.warning("LLM link reasoning failed for %s<->%s: %s", id_a, id_b, e)

    logger.debug("Layer 3 (llm): %d calls", llm_calls)
    return created


def get_linked_signals(signal_id: UUID, db: Session, limit: int = 5) -> list[dict]:
    """
    Return the top linked signals for a given signal, ordered by strength desc.
    Used by trend synthesizer to enrich signal context.
    """
    from sqlalchemy import or_
    links = (
        db.query(SignalLink)
        .filter(
            or_(SignalLink.signal_a_id == signal_id, SignalLink.signal_b_id == signal_id)
        )
        .order_by(SignalLink.strength.desc())
        .limit(limit)
        .all()
    )
    results = []
    for link in links:
        other_id = link.signal_b_id if link.signal_a_id == signal_id else link.signal_a_id
        other = db.get(Signal, other_id)
        if other:
            results.append({
                "id": str(other.id),
                "title": other.title,
                "summary": other.summary or "",
                "relationship": link.relationship_type,
                "strength": link.strength,
                "link_type": link.link_type,
            })
    return results
