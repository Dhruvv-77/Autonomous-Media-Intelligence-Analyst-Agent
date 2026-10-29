"""Tests for citation integrity, exact slice verification, and unsupported claim rejection."""

import pytest
from src.claims.builder import ClaimBuilder
from src.claims.verifier import ClaimVerifier
from src.models import Article, BodyStatus, Claim, Cluster, ClusterAnalysis, Sentiment, VerificationStatus


def test_exact_slice_verification_success():
    body_text = "Global Logistics NV announced a major expansion in Rotterdam on Monday morning."
    article = Article(
        id="art_101",
        source="Logistics Weekly",
        title="Expansion in Rotterdam",
        body=body_text,
        url="https://example.com/news/101",
        body_status=BodyStatus.FULL
    )

    verifier = ClaimVerifier()
    start_char = body_text.find("major expansion in Rotterdam")
    evidence_text = "major expansion in Rotterdam"
    end_char = start_char + len(evidence_text)

    claim = Claim(
        claim_id="c1",
        cluster_id="cl1",
        language="nl",
        section="top_stories",
        claim_text="Global Logistics meldt een major expansion in Rotterdam.",
        article_id=article.id,
        source_url=article.url,
        start_char=start_char,
        end_char=end_char,
        evidence_text=evidence_text,
        verification_status=VerificationStatus.UNVERIFIED
    )

    is_valid, reason = verifier.verify_claim(claim, article)
    assert is_valid is True
    assert "Verified" in reason


def test_slice_out_of_bounds_rejected():
    body_text = "Short text."
    article = Article(
        id="art_102",
        source="News",
        title="Title",
        body=body_text,
        url="https://example.com/2",
        body_status=BodyStatus.FULL
    )
    verifier = ClaimVerifier()
    claim = Claim(
        claim_id="c2",
        cluster_id="cl1",
        language="nl",
        section="top_stories",
        claim_text="Some assertion",
        article_id=article.id,
        source_url=article.url,
        start_char=0,
        end_char=50,  # exceeds len(body_text)
        evidence_text="out of bounds",
        verification_status=VerificationStatus.UNVERIFIED
    )

    is_valid, reason = verifier.verify_claim(claim, article)
    assert is_valid is False
    assert "out of bounds" in reason


def test_slice_mismatch_rejected():
    body_text = "Revenue grew by ten percent last year."
    article = Article(
        id="art_103",
        source="News",
        title="Revenue",
        body=body_text,
        url="https://example.com/3",
        body_status=BodyStatus.FULL
    )
    verifier = ClaimVerifier()
    claim = Claim(
        claim_id="c3",
        cluster_id="cl1",
        language="de",
        section="top_stories",
        claim_text="Umsatz stieg um zehn Prozent",
        article_id=article.id,
        source_url=article.url,
        start_char=0,
        end_char=7,  # slice is "Revenue"
        evidence_text="grew by",  # deliberate mismatch
        verification_status=VerificationStatus.UNVERIFIED
    )

    is_valid, reason = verifier.verify_claim(claim, article)
    assert is_valid is False
    assert "Evidence mismatch" in reason


def test_metadata_only_article_cannot_support_body_claim():
    article = Article(
        id="art_104",
        source="News",
        title="Metadata Only",
        body="",
        url="https://example.com/4",
        body_status=BodyStatus.METADATA_ONLY
    )
    verifier = ClaimVerifier()
    claim = Claim(
        claim_id="c4",
        cluster_id="cl1",
        language="nl",
        section="top_stories",
        claim_text="Unverified claim",
        article_id=article.id,
        source_url=article.url,
        start_char=0,
        end_char=10,
        evidence_text="some text",
        verification_status=VerificationStatus.UNVERIFIED
    )

    is_valid, reason = verifier.verify_claim(claim, article)
    assert is_valid is False
    assert "metadata-only" in reason
