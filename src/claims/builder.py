"""Factual claim generation with exact character spans over source bodies."""

from __future__ import annotations

import re
from typing import Dict, List
from src.models import Article, BodyStatus, Claim, Cluster, ClusterAnalysis, VerificationStatus


class ClaimBuilder:
    def __init__(self) -> None:
        pass

    def extract_claims_from_cluster(
        self,
        cluster: Cluster,
        analysis: ClusterAnalysis,
        articles_by_id: Dict[str, Article],
        languages: List[str] = ["nl", "de"]
    ) -> List[Claim]:
        """
        Extracts structured factual claims from cluster articles.
        Every factual claim is strictly bound to an article ID, URL, exact start_char,
        end_char, and verbatim evidence text from the un-altered article body.
        """
        claims: List[Claim] = []
        claim_counter = 0

        cluster_arts = [articles_by_id[aid] for aid in cluster.article_ids if aid in articles_by_id]
        if not cluster_arts:
            return []

        from src.security.sanitizer import PromptInjectionDetector
        injection_detector = PromptInjectionDetector()

        # Find best article with full body that does not contain adversarial instructions
        clean_arts = [
            a for a in cluster_arts
            if not injection_detector.scan_for_injections(f"{a.title}\n{a.body}")[0]
        ]
        if not clean_arts:
            return []  # Quarantined adversarial cluster

        primary_art = next((a for a in clean_arts if a.body_status == BodyStatus.FULL and len(a.body) > 50), clean_arts[0])

        # If primary article has body, extract grounded claims from sentences
        if primary_art.body and len(primary_art.body.strip()) > 50:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", primary_art.body) if len(s.strip()) > 25]
            for sentence in sentences[:5]:  # Top factual sentences
                # Discard sentences containing adversarial instructions
                has_inj, _ = injection_detector.scan_for_injections(sentence)
                if has_inj:
                    continue

                start_idx = primary_art.body.find(sentence)
                if start_idx == -1:
                    continue
                end_idx = start_idx + len(sentence)
                evidence = primary_art.body[start_idx:end_idx]

                claim_counter += 1
                for lang in languages:
                    section = "top_stories"
                    sent_lower = sentence.lower()
                    if any(w in sent_lower for w in [
                        "risk", "strike", "court", "investigation", "delay", "fine",
                        "staking", "boete", "onderzoek", "vertraging",
                        "streik", "verzögerung", "strafe", "ermittlung", "grève"
                    ]):
                        section = "risks"
                    elif any(w in sent_lower for w in [
                        "competitor", "market share", "rival", "dhl", "kuehne", "maersk",
                        "concurrent", "wettbewerber", "rivalen"
                    ]):
                        section = "competitors"

                    prefix_nl = "Volgens berichtgeving: " if lang == "nl" else "Laut Berichterstattung: "
                    claims.append(
                        Claim(
                            claim_id=f"clm_{cluster.cluster_id}_{lang}_{claim_counter:03d}",
                            cluster_id=cluster.cluster_id,
                            language=lang,
                            section=section,
                            claim_text=f"{prefix_nl}{sentence}",
                            article_id=primary_art.id,
                            source_url=primary_art.url,
                            start_char=start_idx,
                            end_char=end_idx,
                            evidence_text=evidence,
                            confidence=0.95,
                            verification_status=VerificationStatus.UNVERIFIED
                        )
                    )
        else:
            # Metadata-only article fallback: cannot make body span claims!
            # The PDF and REQUIREMENTS.md state: "Metadata-only articles cannot support body-span claims."
            pass

        return claims
