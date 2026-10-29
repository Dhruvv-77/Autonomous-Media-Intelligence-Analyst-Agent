"""GDELT DOC 2.0 API discovery adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import List
from urllib.parse import quote_plus
import httpx
from src.models import Article, BodyStatus


class GDELTAdapter:
    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    def __init__(self, timeout_seconds: int = 25, max_retries: int = 3) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def discover_articles(
        self,
        query_terms: List[str],
        languages: List[str],
        limit: int = 100
    ) -> List[Article]:
        """Discovers articles from GDELT DOC API matching keywords and languages."""
        if not query_terms:
            return []

        # Construct GDELT query
        terms_clause = " OR ".join(f'"{term}"' for term in query_terms)
        lang_clause = " OR ".join(f"sourcelang:{lang}" for lang in languages) if languages else ""
        
        full_query = f"({terms_clause})"
        if lang_clause:
            full_query += f" AND ({lang_clause})"

        params = {
            "query": full_query,
            "mode": "ArtList",
            "maxrecords": str(min(limit, 250)),
            "format": "json",
            "sort": "DateDesc",
        }

        articles: List[Article] = []
        try:
            transport = httpx.HTTPTransport(retries=self.max_retries)
            with httpx.Client(timeout=self.timeout_seconds, transport=transport) as client:
                resp = client.get(self.BASE_URL, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_articles = data.get("articles", [])
                    for item in raw_articles:
                        url = item.get("url", "")
                        title = item.get("title", "").strip()
                        source = item.get("domain", item.get("sourcecountry", "GDELT"))
                        lang = item.get("language", "en").lower()
                        seendate = item.get("seendate")

                        pub_date = None
                        if seendate:
                            try:
                                pub_date = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                            except Exception:
                                pub_date = None

                        if url and title:
                            art_id = hashlib.sha256(f"{url}::{title}".encode("utf-8")).hexdigest()[:16]
                            articles.append(Article(
                                id=art_id,
                                source=source,
                                url=url,
                                title=title,
                                body="",
                                language=lang,
                                published_at=pub_date,
                                body_status=BodyStatus.METADATA_ONLY,
                                source_query=full_query
                            ))
        except Exception:
            # Bounded failure: return whatever was retrieved or empty list
            pass

        return articles
