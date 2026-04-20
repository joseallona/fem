"""
Notion API crawler — fetches entries from public Notion database pages.

Uses Notion's internal API (no auth required for public pages) to fetch
collection entries directly, bypassing the JS-rendered frontend entirely.

Content-type strategies
-----------------------
  full_text    — Article, Blog post, Essay, Post, Book Review, Interview,
                 Magazine, Guide
                 → fetch URL, extract full body text with trafilatura

  abstract     — Report, Trend Report, Research, Thesis, Policy Brief,
                 Academic Journal, Perspectives, Reports
                 → fetch URL, extract first ~800 chars (abstract / intro)

  media        — Video, Podcast, Online Event, Webinar, Seminar, Conference,
                 Masterclass, Talk, Online Classes
                 → Notion description only; no URL fetch (no readable body)

  metadata     — everything else (Book, Guide, Glossary, Repository, Survey,
                 Game, Artefact, Fellowship, Job, Press Release, Social Media
                 Post, …)
                 → Notion description only

Supported URL patterns:
  https://*.notion.site/<page-slug>-<page-id-no-dashes>
  https://notion.so/<page-id-with-dashes>
"""
import logging
import random
import re
import time
from typing import Iterator, Optional
from urllib.parse import urlparse

import requests
import trafilatura

logger = logging.getLogger(__name__)

NOTION_API = "https://www.notion.so/api/v3"
HEADERS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

# ── Content-type strategy groups (lowercase) ──────────────────────────────────

FULL_TEXT_TYPES = {
    "article", "blog post", "essay", "post",
    "book review", "interview", "magazine",
}

ABSTRACT_TYPES = {
    "report", "trend report", "research", "thesis",
    "policy brief", "academic journal", "perspectives", "reports",
}

MEDIA_TYPES = {
    "video", "podcast", "online event", "webinar", "seminar",
    "conference", "masterclass", "talk", "online classes",
}

# Everything else → metadata_only (no URL fetch)


def _strategy(content_type: str) -> str:
    ct = content_type.lower().strip()
    if ct in FULL_TEXT_TYPES:
        return "full_text"
    if ct in ABSTRACT_TYPES:
        return "abstract"
    if ct in MEDIA_TYPES:
        return "media"
    return "metadata"


# ── Notion database property names ───────────────────────────────────────────

_KNOWN_PROP_NAMES = {
    "link":         ["link", "url", "link url"],
    "topics":       ["topics", "tags", "topic"],
    "content_type": ["type of content", "type", "format", "content type"],
    "publisher":    ["publisher", "source", "publication"],
    "about":        ["about", "description", "excerpt", "summary"],
}


# ── URL helpers ───────────────────────────────────────────────────────────────

def is_notion_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "notion.site" in host or "notion.so" in host


def _extract_page_id(url: str) -> Optional[str]:
    """Extract and format the Notion page ID from a URL."""
    m = re.search(r"([0-9a-f]{32})$", urlparse(url).path.replace("-", "").replace("/", ""))
    if not m:
        m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", url)
        if m:
            return m.group(1)
        return None
    raw = m.group(1)
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


# ── Notion property extraction ────────────────────────────────────────────────

def _get_text(prop_value: list) -> str:
    parts = []
    for chunk in prop_value:
        if isinstance(chunk, list) and chunk:
            parts.append(chunk[0])
        elif isinstance(chunk, str):
            parts.append(chunk)
    return "".join(parts).strip()


def _get_link(prop_value: list) -> Optional[str]:
    for chunk in prop_value:
        if not isinstance(chunk, list):
            continue
        text = chunk[0] if chunk else ""
        if text.startswith("http"):
            return text
        if len(chunk) > 1:
            for ann in chunk[1]:
                if isinstance(ann, list) and ann and ann[0] == "a":
                    return ann[1]
    return None


def _build_prop_map(schema: dict) -> dict:
    prop_map = {}
    for prop_id, prop_def in schema.items():
        name_lower = prop_def.get("name", "").lower()
        for semantic, candidates in _KNOWN_PROP_NAMES.items():
            if name_lower in candidates and semantic not in prop_map:
                prop_map[semantic] = prop_id
    return prop_map


# ── Notion API calls ──────────────────────────────────────────────────────────

def _load_page_chunk(page_id: str) -> dict:
    resp = requests.post(
        f"{NOTION_API}/loadPageChunk",
        headers=HEADERS,
        json={
            "pageId": page_id,
            "limit": 50,
            "cursor": {"stack": []},
            "chunkNumber": 0,
            "verticalColumns": False,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def _query_collection(collection_id: str, view_id: str, space_id: str, limit: int = 500) -> dict:
    resp = requests.post(
        f"{NOTION_API}/queryCollection",
        headers=HEADERS,
        json={
            "collection": {"id": collection_id, "spaceId": space_id},
            "collectionView": {"id": view_id, "spaceId": space_id},
            "query": {"aggregations": [{"property": "title", "aggregator": "count"}]},
            "loader": {
                "type": "reducer",
                "reducers": {
                    "collection_group_results": {"type": "results", "limit": limit}
                },
                "searchQuery": "",
                "userTimeZone": "UTC",
            },
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ── URL enrichment ────────────────────────────────────────────────────────────

_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_text(url: str) -> Optional[str]:
    """Fetch URL and extract body text with trafilatura. Returns None on failure."""
    try:
        resp = requests.get(url, headers=_FETCH_HEADERS, timeout=(8, 20))
        resp.raise_for_status()
    except Exception as e:
        logger.debug("Notion enrich: fetch failed %s — %s", url, e)
        return None

    extracted = trafilatura.extract(
        resp.text,
        include_comments=False,
        include_tables=False,
        no_fallback=False,
        favor_recall=True,
    )
    return extracted if extracted and len(extracted.strip()) >= 100 else None


def _enrich(doc: dict) -> dict:
    """
    Augment doc['raw_text'] by fetching the entry URL according to its content-type
    strategy. Adds 'crawl_strategy' to metadata_json.
    """
    content_type = doc["metadata_json"].get("content_type") or ""
    strategy = _strategy(content_type)
    doc["metadata_json"]["crawl_strategy"] = strategy

    entry_url = doc.get("url", "")
    if not entry_url or not entry_url.startswith("http"):
        return doc

    if strategy == "media":
        # No readable body — keep Notion description
        return doc

    if strategy == "metadata":
        # Reference / misc — keep Notion description
        return doc

    # full_text or abstract: fetch the URL
    body = _fetch_text(entry_url)
    if not body:
        return doc

    if strategy == "full_text":
        doc["raw_text"] = doc["raw_text"] + "\n\n" + body
    elif strategy == "abstract":
        # First ~800 chars, trim to last complete word
        snippet = body[:800]
        last_space = snippet.rfind(" ")
        if last_space > 0:
            snippet = snippet[:last_space]
        doc["raw_text"] = doc["raw_text"] + "\n\n" + snippet

    return doc


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_notion(url: str) -> list[dict]:
    """
    Fetch all entries from a public Notion database page.
    Returns base document dicts (Notion metadata only, no URL enrichment).
    Use iter_notion() to get enriched docs with URL fetching.
    """
    page_id = _extract_page_id(url)
    if not page_id:
        logger.warning("Notion: could not extract page ID from %s", url)
        return []

    logger.info("Notion: fetching page %s", page_id)
    try:
        chunk = _load_page_chunk(page_id)
    except Exception as e:
        logger.warning("Notion: loadPageChunk failed for %s: %s", page_id, e)
        return []

    record_map = chunk.get("recordMap", {})
    blocks = record_map.get("block", {})

    collection_id = view_id = space_id = None
    for bid, bdata in blocks.items():
        value = bdata.get("value", {})
        if isinstance(value, dict) and "value" in value:
            value = value["value"]
        if value.get("type") in ("collection_view", "collection_view_page"):
            collection_id = value.get("collection_id")
            views = value.get("view_ids", [])
            view_id = views[0] if views else None
            space_id = bdata.get("spaceId") or value.get("space_id")
            break

    if not collection_id or not view_id:
        logger.warning("Notion: no collection found in page %s", page_id)
        return []

    logger.info("Notion: querying collection %s", collection_id)
    try:
        result = _query_collection(collection_id, view_id, space_id or "")
    except Exception as e:
        logger.warning("Notion: queryCollection failed: %s", e)
        return []

    rmap = result.get("recordMap", {})
    entries = rmap.get("block", {})

    collection_data = rmap.get("collection", {}).get(collection_id, {}).get("value", {})
    if isinstance(collection_data, dict) and "value" in collection_data:
        collection_data = collection_data["value"]
    schema = collection_data.get("schema", {})
    prop_map = _build_prop_map(schema)

    logger.info("Notion: schema props mapped — %s", dict(prop_map))

    docs = []
    for bid, bdata in entries.items():
        value = bdata.get("value", {})
        if isinstance(value, dict) and "value" in value:
            value = value["value"]
        props = value.get("properties", {})
        if not props:
            continue

        title = _get_text(props.get("title", []))
        if not title:
            continue

        link_raw = props.get(prop_map.get("link", "VVMi"), [])
        entry_url = _get_link(link_raw) or _get_text(link_raw) or None
        if entry_url and not entry_url.startswith("http"):
            entry_url = None

        topics_raw = _get_text(props.get(prop_map.get("topics", ""), []))
        topics = [t.strip() for t in topics_raw.split(",") if t.strip()] if topics_raw else []

        content_type = _get_text(props.get(prop_map.get("content_type", ""), []))
        publisher = _get_text(props.get(prop_map.get("publisher", ""), []))
        about = _get_text(props.get(prop_map.get("about", ""), []))

        parts = [title]
        if about:
            parts.append(about)
        if topics:
            parts.append("Topics: " + ", ".join(topics))
        if publisher:
            parts.append("Publisher: " + publisher)
        if content_type:
            parts.append("Type: " + content_type)
        raw_text = "\n".join(parts)

        docs.append({
            "url": entry_url or url,
            "canonical_url": entry_url or url,
            "title": title,
            "raw_text": raw_text,
            "published_at": None,
            "content_hash": f"notion-{bid}",
            "metadata_json": {
                "source": "notion_collection",
                "collection_url": url,
                "topics": topics,
                "content_type": content_type,
                "publisher": publisher,
            },
        })

    logger.info("Notion: %d entries from %s", len(docs), url)
    return docs


def iter_notion(url: str) -> Iterator[dict]:
    """
    Fetch all Notion entries then yield each one enriched according to its
    content-type strategy, with a short politeness delay between URL fetches.
    """
    docs = fetch_notion(url)
    if not docs:
        return

    # Log strategy breakdown
    from collections import Counter
    counts = Counter(_strategy(d["metadata_json"].get("content_type") or "") for d in docs)
    logger.info(
        "Notion strategy breakdown — full_text: %d, abstract: %d, media: %d, metadata: %d",
        counts["full_text"], counts["abstract"], counts["media"], counts["metadata"],
    )

    for doc in docs:
        strategy = _strategy(doc["metadata_json"].get("content_type") or "")
        if strategy in ("full_text", "abstract"):
            time.sleep(random.uniform(0.3, 0.8))  # politeness delay
        yield _enrich(doc)
