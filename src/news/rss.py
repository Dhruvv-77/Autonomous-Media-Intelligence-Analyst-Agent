"""RSS feed discovery adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import List
import feedparser
from src.models import Article, BodyStatus


class RSSAdapter:
    def __init__(self, feed_urls: List[str]) -> None:
        self.feed_urls = feed_urls

    def discover_articles(
        self,
        query_terms: List[str],
        languages: List[str],
        limit: int = 100
    ) -> List[Article]:
        """Fetches and filters RSS feed entries matching query terms."""
        articles: List[Article] = []
        lower_terms = [t.lower() for t in query_terms]

        for feed_url in self.feed_urls:
            try:
                parsed = feedparser.parse(feed_url)
                for entry in parsed.entries:
                    title = getattr(entry, "title", "").strip()
                    summary = getattr(entry, "summary", "").strip()
                    link = getattr(entry, "link", "").strip()
                    text_to_search = f"{title} {summary}".lower()

                    # Match keyword if provided
                    if lower_terms and not any(term in text_to_search for term in lower_terms):
                        continue

                    pub_date = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        except Exception:
                            pub_date = None

                    art_id = hashlib.sha256(f"{link}::{title}".encode("utf-8")).hexdigest()[:16]
                    articles.append(Article(
                        id=art_id,
                        source=parsed.feed.get("title", "RSS"),
                        url=link,
                        title=title,
                        body=summary,
                        language="en",
                        published_at=pub_date,
                        body_status=BodyStatus.FULL if len(summary) > 50 else BodyStatus.METADATA_ONLY
                    ))
                    if len(articles) >= limit:
                        return articles
            except Exception:
                continue

        return articles
