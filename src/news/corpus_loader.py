"""Loader for JSONL news corpora with malformed-record quarantine and deduplication."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
from src.models import Article, BodyStatus


class CorpusLoader:
    def __init__(self) -> None:
        pass

    def load_jsonl(self, file_path: str) -> Tuple[List[Article], List[str]]:
        """
        Loads articles from a JSONL file.
        Returns a tuple of (valid_articles, error_logs).
        Malformed rows or duplicates are quarantined and logged without crashing.
        """
        path = Path(file_path)
        if not path.exists():
            return [], [f"File not found: {file_path}"]

        valid_articles: List[Article] = []
        errors: List[str] = []
        seen_ids = set()

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        errors.append(f"Line {line_no}: Row is not a JSON object")
                        continue

                    art_id = str(data.get("id") or "")
                    title = str(data.get("title") or "").strip()
                    url = str(data.get("url") or data.get("source_url") or "")
                    body = data.get("body") or ""
                    source = str(data.get("source") or "Unknown")
                    language = str(data.get("language") or "en").lower()

                    if not title:
                        errors.append(f"Line {line_no}: Missing required 'title' field")
                        continue

                    # Parse published_at if present
                    pub_date = None
                    if data.get("published_at"):
                        try:
                            pub_date = datetime.fromisoformat(str(data["published_at"]).replace("Z", "+00:00"))
                        except Exception:
                            pub_date = None

                    body_status = BodyStatus.FULL if (body and len(body.strip()) > 50) else BodyStatus.METADATA_ONLY

                    article = Article(
                        id=art_id,
                        source=source,
                        url=url or f"urn:news:{art_id or line_no}",
                        title=title,
                        body=body,
                        language=language,
                        published_at=pub_date,
                        body_status=body_status,
                    )

                    if article.id in seen_ids:
                        errors.append(f"Line {line_no}: Duplicate article ID '{article.id}' encountered, skipping duplicate")
                        continue

                    seen_ids.add(article.id)
                    valid_articles.append(article)

                except Exception as e:
                    errors.append(f"Line {line_no}: Malformed JSON row: {str(e)}")

        return valid_articles, errors
