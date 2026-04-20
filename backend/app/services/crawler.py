"""
Crawling service — Stage 3 + 4 of the pipeline.

Strategy per source, per mode:
  initial  — full historical crawl: RSS (30) → sitemap (150 articles) → HTML (1)
  monitor  — recent updates only:   RSS (30) → sitemap (50 recent)    → HTML (1)

Anti-blocking strategies (applied automatically):
  1. User-Agent rotation       — randomised pool of real browser UAs per request
  2. Browser-realistic headers — full Accept / Accept-Language / Referer set
  3. Retry with backoff        — 429/503 retried up to 2× with Retry-After delay
  4. Politeness delay          — 0.5–1.5 s random sleep between sitemap fetches
  5. Auto-block detection      — caller marks source blocked after 0 docs (pipeline)
"""
import hashlib
import logging
import random
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import feedparser
import requests
import trafilatura
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Strategy 1: User-Agent rotation pool
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
]

FETCH_TIMEOUT = (8, 20)  # (connect_timeout, read_timeout)


# Strategy 2: Browser-realistic headers per request
def _make_headers(url: str) -> dict:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",  # no brotli — brotli pkg not installed
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": origin + "/",
    }


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def _fetch_url(url: str, stream: bool = False) -> Optional[requests.Response]:
    """
    Fetch a URL with browser-realistic headers.
    Strategy 3: retries up to 2× on 429/503 with Retry-After backoff.
    """
    max_retries = 2
    for attempt in range(max_retries + 1):
        logger.info("  GET %s", url)
        try:
            resp = requests.get(url, headers=_make_headers(url), timeout=FETCH_TIMEOUT, stream=stream)
            if resp.status_code in (429, 503) and attempt < max_retries:
                wait = min(int(resp.headers.get("Retry-After", 5 * (attempt + 1))), 30)
                logger.warning("  RATE LIMITED %s — waiting %ds (attempt %d/%d)", url, wait, attempt + 1, max_retries + 1)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except requests.HTTPError as e:
            logger.warning("  FAILED %s — %s", url, e)
            return None
        except Exception as e:
            logger.warning("  FAILED %s — %s", url, e)
            return None
    return None


def _get_base_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


# ---------- URL validation ----------

def validate_url(url: str) -> str:
    """
    Normalize URL scheme and verify it is reachable.
    Returns the (possibly normalized) URL.
    Raises ValueError with a human-readable message on failure.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        headers = _make_headers(url)
        resp = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
        if resp.status_code == 405:
            resp = requests.get(url, headers=headers, timeout=10, stream=True)
            resp.close()
        if resp.status_code >= 400:
            raise ValueError(
                f"URL returned HTTP {resp.status_code}. "
                "Please check the address and try again."
            )
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not connect to URL: {e}")

    return url


# ---------- RSS ----------

def _is_feed_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(s) for s in (".rss", ".atom", ".xml", "/feed", "/rss", "/atom"))


def _discover_feed(url: str) -> Optional[str]:
    """Try to find an RSS/Atom feed link in the page HTML."""
    resp = _fetch_url(url)
    if not resp:
        return None
    soup = BeautifulSoup(resp.text, "lxml")
    for link in soup.find_all("link", type=lambda t: t and ("rss" in t or "atom" in t)):
        href = link.get("href", "")
        if href:
            return urljoin(url, href)
    return None


def _enrich_rss_entry(link: str, snippet: str) -> str:
    """
    Attempt to fetch full article text from the entry URL.
    Returns full text if successful (>= 200 chars), otherwise returns the original snippet.
    Skips academic journal domains that block automated fetching.
    """
    BLOCKED_DOMAINS = {
        "nejm.org", "thelancet.com", "science.org", "pnas.org",
        "acpjournals.org", "jamanetwork.com", "bmj.com", "cell.com",
        "nature.com", "sciencedirect.com", "springer.com", "wiley.com",
    }
    try:
        domain = urlparse(link).netloc.lower().lstrip("www.")
        if any(domain.endswith(d) for d in BLOCKED_DOMAINS):
            return snippet
        resp = _fetch_url(link)
        if not resp:
            return snippet
        full = trafilatura.extract(
            resp.text,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            favor_recall=False,  # strict mode to avoid noise on short pages
        )
        if full and len(full.strip()) >= 200:
            return full.strip()
    except Exception:
        pass
    return snippet


def _parse_feed(feed_url: str, since: Optional[datetime] = None) -> list[dict]:
    """Run feedparser on a URL and return document dicts. Empty list if not a feed."""
    logger.info("  RSS %s", feed_url)
    parsed = feedparser.parse(feed_url, request_headers=_make_headers(feed_url))
    if not parsed.entries:
        if parsed.bozo:
            logger.debug("RSS bozo for %s: %s", feed_url, parsed.bozo_exception)
        return []
    docs = []
    for entry in parsed.entries[:30]:
        published = None
        if entry.get("published_parsed"):
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass

        # In monitor mode, skip entries published before the last crawl
        if since and published and published <= since:
            continue

        text = entry.get("summary") or entry.get("content", [{}])[0].get("value", "")
        if text:
            text = BeautifulSoup(text, "lxml").get_text(separator=" ", strip=True)
        raw_title = entry.get("title", "")
        # Strip HTML only if the title actually contains tags
        title = BeautifulSoup(raw_title, "lxml").get_text(separator=" ", strip=True) if "<" in raw_title else raw_title.strip()
        link = entry.get("link", "")
        if not link or not title:
            continue

        # Enrich with full article text only when the RSS snippet is very short.
        # Short snippets (<= 300 chars) don't have enough text for relevance scoring.
        enriched_text = _enrich_rss_entry(link, text) if len(text) <= 300 else text
        if enriched_text != text:
            logger.warning("  RSS enriched (%d→%d chars): %s", len(text), len(enriched_text), title[:60])

        docs.append({
            "url": link,
            "canonical_url": link,
            "title": title,
            "raw_text": enriched_text or title,
            "published_at": published,
            "content_hash": _content_hash((title + (enriched_text or text))[:2000]),
            "metadata_json": {"source": "rss", "feed_url": feed_url},
        })
    return docs


def fetch_rss(url: str, since: Optional[datetime] = None) -> list[dict]:
    """
    Parse RSS/Atom feed. Returns list of document dicts.
    Strategy: always try feedparser on the URL first (handles /rss/xml, /feeds/news/, etc.
    that _is_feed_url misses). Only fall back to HTML discovery if feedparser finds nothing.
    """
    # Always try feedparser directly — it gracefully handles non-feeds
    docs = _parse_feed(url, since=since)
    if docs:
        return docs

    # Feedparser found nothing: if this looks like a page (not a feed URL), try
    # to discover a feed link in its HTML
    if not _is_feed_url(url):
        feed_url = _discover_feed(url)
        if feed_url and feed_url != url:
            return _parse_feed(feed_url, since=since)

    return []


# ---------- HTML ----------

def fetch_html(url: str) -> list[dict]:
    """Extract main content from a single web page using trafilatura."""
    resp = _fetch_url(url)
    if not resp:
        return []

    text = trafilatura.extract(
        resp.text,
        include_comments=False,
        include_tables=False,
        no_fallback=False,
        favor_recall=True,
    )
    if not text or len(text.strip()) < 100:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else url

    return [{
        "url": url,
        "canonical_url": url,
        "title": title,
        "raw_text": text,
        "published_at": None,
        "content_hash": _content_hash(text[:2000]),
        "metadata_json": {"source": "html"},
    }]


# ---------- Sitemap ----------

def _parse_sitemap_entries(xml_text: str) -> tuple[list[dict], list[str]]:
    """
    Parse sitemap XML.
    Returns (article_entries, sub_sitemap_urls).
    article_entries: [{"url": str, "lastmod": datetime|None}]
    """
    articles: list[dict] = []
    sub_sitemaps: list[str] = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.debug("Sitemap XML parse error: %s", e)
        return articles, sub_sitemaps

    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

    def child_text(elem: ET.Element, local_name: str) -> str:
        for child in elem:
            child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if child_tag == local_name:
                return (child.text or "").strip()
        return ""

    def parse_lastmod(s: str) -> Optional[datetime]:
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s[:19] if "T" in s else s[:10], fmt.split("%z")[0].split("Z")[0] if not "%z" in fmt else fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None

    if tag == "sitemapindex":
        for child in root:
            loc = child_text(child, "loc")
            if loc:
                sub_sitemaps.append(loc)
    elif tag == "urlset":
        for child in root:
            loc = child_text(child, "loc")
            if not loc:
                continue
            lastmod_str = child_text(child, "lastmod")
            lastmod = parse_lastmod(lastmod_str) if lastmod_str else None
            articles.append({"url": loc, "lastmod": lastmod})

    return articles, sub_sitemaps


def _collect_sitemap_urls(sitemap_url: str, depth: int = 0) -> list[dict]:
    """Recursively collect article entries from a sitemap, max depth 2."""
    if depth > 2:
        return []
    resp = _fetch_url(sitemap_url)
    if not resp:
        return []
    articles, sub_sitemaps = _parse_sitemap_entries(resp.text)
    if articles:
        return articles
    # It's a sitemap index — follow sub-sitemaps
    all_articles: list[dict] = []
    for sub_url in sub_sitemaps[:8]:
        all_articles.extend(_collect_sitemap_urls(sub_url, depth + 1))
        if len(all_articles) >= 1000:
            break
    return all_articles


def _find_sitemap_url(base_url: str) -> Optional[str]:
    """Locate the sitemap for a site."""
    # Check robots.txt for Sitemap: directive
    robots_resp = _fetch_url(base_url.rstrip("/") + "/robots.txt")
    if robots_resp:
        for line in robots_resp.text.splitlines():
            if line.lower().startswith("sitemap:"):
                candidate = line.split(":", 1)[1].strip()
                resp = _fetch_url(candidate)
                if resp:
                    return candidate

    for path in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap/sitemap.xml"):
        resp = _fetch_url(base_url.rstrip("/") + path)
        if resp:
            return base_url.rstrip("/") + path

    return None


def _iter_sitemap(base_url: str, limit: int, since: Optional[datetime]):
    """
    Generator: discover sitemap, then fetch and yield one article at a time.
    Bails out early if 5 consecutive fetches fail (paywall / blocking).
    """
    sitemap_url = _find_sitemap_url(_get_base_url(base_url))
    if not sitemap_url:
        logger.debug("No sitemap found for %s", base_url)
        return

    entries = _collect_sitemap_urls(sitemap_url)
    if not entries:
        return

    if since:
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        entries = [e for e in entries if e.get("lastmod") and e["lastmod"] > since]

    epoch = datetime.min.replace(tzinfo=timezone.utc)
    entries.sort(key=lambda e: e.get("lastmod") or epoch, reverse=True)
    entries = entries[:limit]

    logger.info("Sitemap: will fetch %d article(s) from %s", len(entries), base_url)

    consecutive_failures = 0
    for entry in entries:
        # Strategy 4: politeness delay — avoid triggering rate limits
        time.sleep(random.uniform(0.5, 1.5))
        article_docs = fetch_html(entry["url"])
        if not article_docs:
            consecutive_failures += 1
            if consecutive_failures >= 5:
                logger.warning(
                    "Sitemap: 5 consecutive failed fetches from %s — likely paywalled or blocking. Stopping early.",
                    base_url,
                )
                return
            continue
        consecutive_failures = 0
        for doc in article_docs:
            if entry.get("lastmod"):
                doc["published_at"] = entry["lastmod"]
            doc["metadata_json"]["source"] = "sitemap"
            doc["metadata_json"]["sitemap_url"] = sitemap_url
            yield doc


# ---------- Entry point ----------

def fetch_source(
    url: str,
    mode: str = "monitor",
    since: Optional[datetime] = None,
):
    """
    Generator: yield document dicts from a source URL one at a time.

    mode="initial"  — first-time full crawl: RSS → sitemap (150 articles) → HTML / JS
    mode="monitor"  — daily updates:         RSS → sitemap (50 recent)    → HTML / JS

    JS-rendered pages (Notion, Airtable, are.na, etc.) skip RSS/sitemap and go
    straight to Playwright. Link-collection pages yield one document per external
    link found; article pages yield the extracted text.

    Yields documents as they are fetched so the caller can process and discard
    each one without accumulating the full set in memory.
    """
    from app.services.crawler_notion import is_notion_url, iter_notion

    # Notion pages: use internal API + per-entry content-type strategy
    if is_notion_url(url):
        logger.info("Notion URL detected — using Notion API for %s", url)
        yielded = 0
        for doc in iter_notion(url):
            yield doc
            yielded += 1
        if yielded:
            logger.info("Notion: yielded %d enriched docs from %s", yielded, url)
        return

    # RSS: fast, small — collect eagerly then yield
    rss_since = since if mode == "monitor" else None
    rss_docs = fetch_rss(url, since=rss_since)
    if rss_docs:
        logger.info("RSS: %d docs from %s", len(rss_docs), url)
        yield from rss_docs
        return

    # Sitemap: stream one article at a time
    sitemap_limit = 150 if mode == "initial" else 50
    sitemap_since = since if mode == "monitor" else None
    yielded = 0
    for doc in _iter_sitemap(url, limit=sitemap_limit, since=sitemap_since):
        yield doc
        yielded += 1
    if yielded > 0:
        logger.info("Sitemap (%s): %d docs from %s", mode, yielded, url)
        return

    # Static HTML fallback
    html_docs = fetch_html(url)
    if html_docs:
        logger.info("HTML fallback: 1 doc from %s", url)
        yield from html_docs
        return

    logger.info("Static fetch yielded nothing for %s — no further fallback available", url)
