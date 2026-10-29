"""Tests verifying strict determinism: identical inputs yield identical clusters and entity decisions."""

import pytest
from src.config import ClientProfile, EmbeddingsConfig, ExecutiveProfile
from src.dedup.clustering import StoryClusterer
from src.entity.resolver import EntityResolver
from src.models import Article


def test_clustering_determinism():
    config = EmbeddingsConfig(deterministic_seed=42, clustering_threshold=0.82)
    clusterer1 = StoryClusterer(config)
    clusterer2 = StoryClusterer(config)

    articles = [
        Article(id="art_a", source="S1", title="Port strike blocks Rotterdam cargo", body="Dock workers strike in Rotterdam.", url="https://a.com"),
        Article(id="art_b", source="S2", title="Hafenstreik legt Rotterdam lahm", body="Hafenarbeiter in Rotterdam streiken.", url="https://b.com"),
        Article(id="art_c", source="S3", title="Global Logistics expands fleet", body="Global Logistics NV buys 50 electric trucks.", url="https://c.com"),
    ]

    clusters_run1 = clusterer1.cluster_articles(articles)
    clusters_run2 = clusterer2.cluster_articles(articles)

    assert len(clusters_run1) == len(clusters_run2)
    for c1, c2 in zip(clusters_run1, clusters_run2):
        assert c1.cluster_id == c2.cluster_id
        assert c1.canonical_title == c2.canonical_title
        assert sorted(c1.article_ids) == sorted(c2.article_ids)


def test_entity_resolution_determinism():
    profile = ClientProfile(
        client_name="Global Logistics NV",
        brands=["EuroFreight"],
        executives=[ExecutiveProfile(name="Jan de Vries", role="CEO")]
    )
    resolver = EntityResolver(profile)

    article = Article(
        id="art_ent_1",
        source="News",
        title="EuroFreight expanding operations",
        body="Global Logistics NV brand EuroFreight announced new routes under CEO Jan de Vries.",
        url="https://example.com/ent"
    )

    mentions_run1 = resolver.resolve_article(article)
    mentions_run2 = resolver.resolve_article(article)

    assert len(mentions_run1) == len(mentions_run2)
    for m1, m2 in zip(mentions_run1, mentions_run2):
        assert m1.mention_id == m2.mention_id
        assert m1.entity_name == m2.entity_name
        assert m1.is_client == m2.is_client
        assert m1.confidence == m2.confidence
        assert m1.start_char == m2.start_char
        assert m1.end_char == m2.end_char
