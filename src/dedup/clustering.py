"""Deduplication, multilingual semantic clustering, and syndication tracking."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from src.config import EmbeddingsConfig
from src.models import Article, Cluster


class StoryClusterer:
    def __init__(self, config: EmbeddingsConfig) -> None:
        self.config = config
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.config.model)
        return self._model

    @staticmethod
    def canonicalize_url(url: str) -> str:
        """Strips tracking query parameters and standardizes the URL."""
        try:
            parsed = urlparse(url)
            query_params = parse_qsl(parsed.query)
            clean_params = [
                (k, v) for k, v in query_params
                if not k.lower().startswith("utm_")
                and k.lower() not in ("ref", "fbclid", "gclid", "mc_cid", "mc_eid")
            ]
            clean_query = urlencode(clean_params)
            return urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                parsed.params,
                clean_query,
                ""
            ))
        except Exception:
            return url

    def cluster_articles(self, articles: List[Article]) -> List[Cluster]:
        """
        Clusters articles reporting the same event across Dutch, German, French, and English.
        Tracks origin, syndication spread, and story updates.
        Ensures strict determinism for identical input.
        """
        if not articles:
            return []

        # Sort deterministically by (published_at, id)
        sorted_articles = sorted(
            articles,
            key=lambda a: (
                a.published_at.isoformat() if a.published_at else "",
                a.id
            )
        )

        # Step 1: Exact deduplication by canonical URL and content hash
        canonical_map: Dict[str, List[Article]] = {}
        hash_map: Dict[str, List[Article]] = {}
        unique_representatives: List[Article] = []
        rep_to_duplicates: Dict[str, List[Article]] = {}

        for art in sorted_articles:
            c_url = self.canonicalize_url(art.url)
            c_hash = art.content_hash

            matched_rep = None
            if c_url in canonical_map:
                matched_rep = canonical_map[c_url][0]
            elif c_hash and c_hash in hash_map:
                matched_rep = hash_map[c_hash][0]

            if matched_rep:
                rep_to_duplicates.setdefault(matched_rep.id, []).append(art)
            else:
                canonical_map.setdefault(c_url, []).append(art)
                if c_hash:
                    hash_map.setdefault(c_hash, []).append(art)
                unique_representatives.append(art)
                rep_to_duplicates[art.id] = [art]

        if not unique_representatives:
            return []

        # Step 2: Semantic multilingual clustering
        if len(unique_representatives) == 1:
            labels = [0]
        else:
            texts = [
                f"{a.title}\n{a.body[:300]}" if a.body else a.title
                for a in unique_representatives
            ]
            model = self._get_model()
            embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

            # Cosine distance = 1 - cosine similarity
            # Distance threshold = 1.0 - clustering_threshold (e.g. 1.0 - 0.82 = 0.18)
            dist_threshold = max(0.01, 1.0 - self.config.clustering_threshold)
            clustering = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=dist_threshold,
                metric="cosine",
                linkage="average"
            )
            labels = clustering.fit_predict(embeddings).tolist()

        # Step 3: Group representatives and all their exact duplicates into clusters
        clusters_by_label: Dict[int, List[Article]] = {}
        for idx, label in enumerate(labels):
            rep = unique_representatives[idx]
            all_arts = rep_to_duplicates.get(rep.id, [rep])
            clusters_by_label.setdefault(label, []).extend(all_arts)

        result_clusters: List[Cluster] = []
        update_markers = ("update:", "bijgewerkt:", "aktualisiert:", "mise à jour:", "[update]")

        for label in sorted(clusters_by_label.keys()):
            cluster_arts = clusters_by_label[label]
            # Deterministic sorting within cluster
            cluster_arts.sort(
                key=lambda a: (
                    a.published_at.isoformat() if a.published_at else "9999",
                    a.id
                )
            )

            canonical_art = cluster_arts[0]
            earliest_pub = canonical_art.published_at
            first_source = canonical_art.source
            syndication = list({a.source for a in cluster_arts if a.source != first_source})
            syndication.sort()

            # Check update pattern
            is_update = False
            for art in cluster_arts:
                title_lower = art.title.lower()
                if any(m in title_lower for m in update_markers):
                    is_update = True
                    break

            cluster_id = f"cl_{label:04d}_{canonical_art.id[:8]}"
            result_clusters.append(
                Cluster(
                    cluster_id=cluster_id,
                    article_ids=[a.id for a in cluster_arts],
                    canonical_title=canonical_art.title,
                    earliest_published_at=earliest_pub,
                    first_source=first_source,
                    syndication_sources=syndication,
                    is_update=is_update,
                    update_of_cluster_id=None
                )
            )

        return result_clusters
