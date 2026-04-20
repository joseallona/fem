"""
Relevance filtering — Stage 6.

Deterministic scoring (per Decision Logic Specification):
  relevance_score = w1 * keyword_match + w2 * entity_overlap + w3 * subject_alignment

Thresholds:
  RELEVANT_THRESHOLD (0.7)   → clearly on-topic
  BORDERLINE_THRESHOLD (0.07) → very permissive intentionally — LLM signal extraction
                                is the real quality gate in Phase 2. Only near-zero
                                scores (documents with no theme vocabulary whatsoever)
                                are hard-filtered here.
"""
import re
from typing import Optional

RELEVANT_THRESHOLD = 0.7
BORDERLINE_THRESHOLD = 0.07  # very permissive — LLM is the real quality gate

W_KEYWORD = 0.5
W_ENTITY = 0.3
W_SUBJECT = 0.2


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b[a-z]{3,}\b", text.lower()))


def _keyword_match(text_tokens: set[str], theme_tokens: set[str]) -> float:
    if not theme_tokens:
        return 0.0
    overlap = len(text_tokens & theme_tokens)
    return min(overlap / len(theme_tokens), 1.0)


def _subject_alignment(text: str, subjects: list[str]) -> float:
    if not subjects:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for s in subjects if s.lower() in text_lower)
    return min(hits / len(subjects), 1.0)


def score_relevance(
    raw_text: str,
    title: str,
    theme_name: str,
    primary_subject: Optional[str],
    related_subjects: list[str],
    focal_question: Optional[str],
) -> float:
    """
    Returns a relevance score 0.0–1.0.
    """
    combined = f"{title} {raw_text[:3000]}"

    # Build theme vocabulary from name, subject, related subjects, and focal question
    theme_vocab = _tokenize(theme_name)
    if primary_subject:
        theme_vocab |= _tokenize(primary_subject)
    for subject in related_subjects:
        theme_vocab |= _tokenize(subject)
    if focal_question:
        theme_vocab |= _tokenize(focal_question)
    # Remove stop words — includes function/question words that add noise
    stopwords = {
        "the", "and", "for", "that", "this", "with", "are", "was", "has", "have",
        "will", "from", "how", "why", "what", "when", "where", "who", "which",
        "might", "could", "would", "should", "may", "can", "does", "did", "into",
        "about", "over", "also", "more", "its", "than", "their", "they", "been",
        "but", "not", "all", "any", "new", "our",
    }
    theme_vocab -= stopwords

    text_tokens = _tokenize(combined)

    kw_score = _keyword_match(text_tokens, theme_vocab)

    all_subjects = ([primary_subject] if primary_subject else []) + related_subjects
    subj_score = _subject_alignment(combined, all_subjects)

    # Entity overlap: presence of subjects as exact phrases
    entity_score = _subject_alignment(combined, [theme_name] + ([primary_subject] if primary_subject else []))

    score = W_KEYWORD * kw_score + W_ENTITY * entity_score + W_SUBJECT * subj_score
    return round(min(score, 1.0), 4)


def is_relevant(score: float) -> bool:
    from app.core.config import get_runtime_setting
    threshold = float(get_runtime_setting("relevance_threshold", BORDERLINE_THRESHOLD))
    return score >= threshold
