"""
Signal Clustering — Phase 4, Stage 2.

Groups signals by shared entities/keywords + time proximity.
Fully deterministic — no LLM involvement.

Algorithm:
  1. Tokenize each signal's title + summary into keyword sets
  2. Build adjacency: two signals are "related" if Jaccard similarity >= JACCARD_THRESHOLD
     AND their created_at are within TIME_WINDOW_DAYS of each other
  3. Union-Find to assign cluster IDs
  4. Clusters of size 1 receive a singleton cluster_id (no grouping)

Cluster IDs are stable: sorted list of signal IDs hashed to a short string.
Re-running clustering is idempotent — cluster_id on each Signal is updated in-place.
"""
import hashlib
import logging
import re
from datetime import timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.signal import Signal

logger = logging.getLogger(__name__)

JACCARD_THRESHOLD = 0.20   # minimum keyword overlap to consider signals related
TIME_WINDOW_DAYS = 90       # signals within 90 days (backfill signals share same created_at)
MIN_CLUSTER_SIZE = 3        # minimum for a trend-worthy cluster
MAX_CLUSTER_SIZE = 40       # cap to avoid one mega-cluster dominating trend synthesis

# Stop-words to exclude from keyword extraction
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "this", "that", "these",
    "those", "it", "its", "not", "no", "new", "more", "also", "over",
    "after", "before", "up", "down", "into", "out", "about", "between",
    # Theme-common tokens: present in almost every energy signal → useless for differentiation
    "energy", "sustainable", "sustainability", "renewable", "renewables",
    "transition", "power", "climate", "carbon", "clean", "green",
    "fossil", "fuel", "fuels", "emissions", "electricity", "electric",
}


def _tokenize(text: str) -> set[str]:
    """Extract meaningful keywords from text."""
    tokens = re.findall(r"[a-z]{3,}", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class _UnionFind:
    def __init__(self):
        self._parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self._parent.setdefault(x, x)
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])
        return self._parent[x]

    def union(self, x: str, y: str):
        self._parent[self.find(x)] = self.find(y)


def _stable_cluster_id(signal_ids: list[str]) -> str:
    """Deterministic cluster ID from sorted member IDs."""
    key = ",".join(sorted(signal_ids))
    return "c_" + hashlib.sha1(key.encode()).hexdigest()[:12]


def cluster_signals(signals: list[Signal]) -> dict[str, list[str]]:
    """
    Cluster signals deterministically. Returns {cluster_id: [signal_id, ...]}.
    Also assigns cluster_id back onto each Signal object (caller must commit).
    """
    if not signals:
        return {}

    # Build keyword sets per signal
    keywords: dict[str, set[str]] = {}
    for s in signals:
        text = f"{s.title or ''} {s.summary or ''}"
        keywords[str(s.id)] = _tokenize(text)

    uf = _UnionFind()

    # Compare all pairs
    for i, si in enumerate(signals):
        for sj in signals[i + 1:]:
            # Time proximity check
            if si.created_at and sj.created_at:
                delta = abs((si.created_at - sj.created_at).days)
                if delta > TIME_WINDOW_DAYS:
                    continue

            j_score = _jaccard(keywords[str(si.id)], keywords[str(sj.id)])
            if j_score >= JACCARD_THRESHOLD:
                uf.union(str(si.id), str(sj.id))

    # Group by root
    groups: dict[str, list[str]] = {}
    for s in signals:
        root = uf.find(str(s.id))
        groups.setdefault(root, []).append(str(s.id))

    # Assign cluster_ids; split oversized clusters by STEEP category
    result: dict[str, list[str]] = {}
    id_to_signal = {str(s.id): s for s in signals}

    for root, members in groups.items():
        if len(members) < MIN_CLUSTER_SIZE:
            cid = f"solo_{members[0][:8]}"
            result[cid] = members
        elif len(members) > MAX_CLUSTER_SIZE:
            # Split oversized cluster by STEEP category to get more focused trends
            by_steep: dict[str, list[str]] = {}
            for sid in members:
                steep = getattr(id_to_signal[sid], "steep_category", None) or "unknown"
                by_steep.setdefault(steep, []).append(sid)
            for steep, steep_members in by_steep.items():
                if len(steep_members) >= MIN_CLUSTER_SIZE:
                    cid = _stable_cluster_id(steep_members)
                    result[cid] = steep_members
                else:
                    # Too small after split — keep as singletons
                    for sid in steep_members:
                        result[f"solo_{sid[:8]}"] = [sid]
        else:
            cid = _stable_cluster_id(members)
            result[cid] = members

    # Write cluster_id back to signal objects
    for cid, members in result.items():
        for sid in members:
            id_to_signal[sid].cluster_id = cid

    logger.info(
        "Clustering: %d signals → %d clusters (%d multi-member)",
        len(signals),
        len(result),
        sum(1 for m in result.values() if len(m) >= MIN_CLUSTER_SIZE),
    )
    return result


def run_clustering_for_theme(theme_id: UUID, db: Session) -> dict[str, list[str]]:
    """Cluster all active signals for a theme and persist cluster_id."""
    signals = (
        db.query(Signal)
        .filter(Signal.theme_id == theme_id, Signal.status == "active")
        .all()
    )
    clusters = cluster_signals(signals)
    db.commit()
    return clusters
