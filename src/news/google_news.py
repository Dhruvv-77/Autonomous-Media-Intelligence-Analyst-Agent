"""Google News RSS discovery adapter for real-time multilingual news with zero API keys."""

from __future__ import annotations

import concurrent.futures
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import quote_plus
import feedparser

try:
    from googlenewsdecoder import gnewsdecoder
except ImportError:
    gnewsdecoder = None

from src.models import Article, BodyStatus

logger = logging.getLogger(__name__)


def _decode_single_entry(entry: Any, lang: str) -> Optional[Article]:
    raw_title = getattr(entry, "title", "").strip()
    gnews_link = getattr(entry, "link", "").strip()
    source_dict = getattr(entry, "source", {})
    source_name = source_dict.get("title") if isinstance(source_dict, dict) else "Google News"

    if not raw_title or not gnews_link:
        return None

    resolved_url = gnews_link
    if gnewsdecoder:
        try:
            decoded_res = gnewsdecoder(gnews_link, timeout=4.0)
            if isinstance(decoded_res, dict) and decoded_res.get("success"):
                resolved_url = decoded_res.get("decoded_url") or gnews_link
        except Exception:
            resolved_url = gnews_link

    pub_date = None
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except Exception:
            pub_date = None

    art_id = hashlib.sha256(f"{resolved_url}::{raw_title}".encode("utf-8")).hexdigest()[:16]

    return Article(
        id=f"art_gn_{art_id}",
        source=source_name,
        url=resolved_url,
        title=raw_title,
        body="",
        language=lang,
        published_at=pub_date,
        body_status=BodyStatus.METADATA_ONLY
    )


class GoogleNewsAdapter:
    """Discovers real-time news articles via Google News RSS search across Dutch, German, and English."""

    LANG_PARAMS = {
        "nl": {"hl": "nl", "gl": "NL", "ceid": "NL:nl"},
        "de": {"hl": "de", "gl": "DE", "ceid": "DE:de"},
        "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
        "fr": {"hl": "fr", "gl": "FR", "ceid": "FR:fr"},
    }

    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds

    def discover_articles(
        self,
        query_terms: List[str],
        languages: List[str],
        limit: int = 30
    ) -> List[Article]:
        """Discovers articles from Google News RSS search matching query terms across languages in parallel."""
        if not query_terms:
            return []

        articles: List[Article] = []
        seen_urls = set()

        # Build clean query string
        query_str = " OR ".join(f'"{term}"' for term in query_terms[:4])
        encoded_query = quote_plus(query_str)

        target_languages = [lang.lower() for lang in languages if lang.lower() in self.LANG_PARAMS]
        if not target_languages:
            target_languages = ["nl", "de", "en"]

        per_lang_limit = max(5, limit // len(target_languages))
        tasks = []

        for lang in target_languages:
            params = self.LANG_PARAMS[lang]
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl={params['hl']}&gl={params['gl']}&ceid={params['ceid']}"

            try:
                feed = feedparser.parse(rss_url)
                entries = getattr(feed, "entries", [])[:per_lang_limit]
                for e in entries:
                    tasks.append((e, lang))
            except Exception as e:
                logger.error("Error fetching Google News RSS feed for %s: %s", lang, e)

        # Decode links concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_decode_single_entry, e, l) for e, l in tasks]
            for future in concurrent.futures.as_completed(futures):
                try:
                    art = future.result(timeout=10)
                    if art and art.url not in seen_urls:
                        seen_urls.add(art.url)
                        articles.append(art)
                except Exception as e:
                    logger.debug("Failed processing article: %s", e)

        logger.info("Total discovered live Google News articles: %d", len(articles))
        return articles[:limit]
