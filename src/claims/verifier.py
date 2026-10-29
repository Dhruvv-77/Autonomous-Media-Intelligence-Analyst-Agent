"""Independent claim and citation verification stage."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple
from src.models import Article, BodyStatus, Claim, VerificationStatus


class ClaimVerifier:
    def __init__(self) -> None:
        pass

    def verify_claim(self, claim: Claim, article: Article) -> Tuple[bool, str]:
        """
        Independently checks that the cited slice equals the stored source slice
        and supports the claim. Rejects unsupported claims.
        """
        # Check 1: Article body must not be metadata-only if body span is cited
        if article.body_status == BodyStatus.METADATA_ONLY:
            return False, "Article is metadata-only; body spans cannot be verified"

        # Check 2: Bounds checking
        body = article.body or ""
        if claim.start_char < 0 or claim.end_char > len(body) or claim.start_char >= claim.end_char:
            return False, f"Character offsets [{claim.start_char}:{claim.end_char}] out of bounds for article length {len(body)}"

        # Check 3: Exact slice equality: body[start:end] == evidence_text
        actual_slice = body[claim.start_char:claim.end_char]
        if actual_slice != claim.evidence_text:
            return False, f"Evidence mismatch: expected '{claim.evidence_text[:40]}...', found '{actual_slice[:40]}...'"

        # Check 4: Semantic support verification
        # The evidence text must contain core content related to the claim text
        clean_evidence_words = set(re.findall(r"\w+", claim.evidence_text.lower()))
        clean_claim_words = set(re.findall(r"\w+", claim.claim_text.lower()))
        # Remove common functional stopwords
        stopwords = {"volgens", "berichtgeving", "laut", "berichterstattung", "de", "het", "een", "der", "die", "das", "und", "en", "in", "van", "von", "op", "auf"}
        significant_claim_words = clean_claim_words - stopwords
        
        overlap = significant_claim_words.intersection(clean_evidence_words)
        if len(significant_claim_words) > 0 and len(overlap) == 0:
            return False, "Semantic failure: cited span does not contain key terms of the factual claim"

        return True, "Verified exact slice match and semantic support"

    def verify_claims(
        self,
        claims: List[Claim],
        articles_by_id: Dict[str, Article]
    ) -> Tuple[List[Claim], List[Claim]]:
        """
        Verifies a list of claims against stored articles.
        Returns (verified_claims, rejected_claims).
        """
        verified: List[Claim] = []
        rejected: List[Claim] = []

        for claim in claims:
            article = articles_by_id.get(claim.article_id)
            if not article:
                claim.verification_status = VerificationStatus.REJECTED
                claim.rejection_reason = f"Referenced article '{claim.article_id}' not found in database"
                rejected.append(claim)
                continue

            is_valid, reason = self.verify_claim(claim, article)
            if is_valid:
                claim.verification_status = VerificationStatus.VERIFIED
                claim.rejection_reason = None
                verified.append(claim)
            else:
                claim.verification_status = VerificationStatus.REJECTED
                claim.rejection_reason = reason
                rejected.append(claim)

        return verified, rejected
