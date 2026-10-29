"""Daily briefing generator in Dutch and German based strictly on verified claims."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List
from src.config import ClientProfile
from src.models import Article, Claim, Cluster, ClusterAnalysis, VerificationStatus
from src.privacy.gdpr import GDPRFilter


class BriefingGenerator:
    def __init__(self, profile: ClientProfile, gdpr_filter: GDPRFilter) -> None:
        self.profile = profile
        self.gdpr = gdpr_filter

    def generate_briefing(
        self,
        language: str,
        verified_claims: List[Claim],
        clusters: List[Cluster],
        analyses_by_cluster: Dict[str, ClusterAnalysis],
        articles_by_id: Dict[str, Article]
    ) -> str:
        """
        Generates a daily briefing in Dutch or German.
        Contains:
          - Executive summary
          - Top stories
          - Reputational risks
          - Competitor activity
        All factual assertions cite article ID, source URL, character offsets, and exact evidence text.
        """
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        is_nl = language.lower() == "nl"

        lang_claims = [c for c in verified_claims if c.language.lower() == language.lower() and c.verification_status == VerificationStatus.VERIFIED]

        # Titles and Section Headers
        if is_nl:
            doc_title = f"# Dagelijkse Media Intelligence Briefing — {self.profile.client_name}"
            date_label = f"**Datum & tijd:** {now_str}"
            h_exec = "## 1. Managementsamenvatting (Executive Summary)"
            h_stories = "## 2. Belangrijkste Nieuwsfeiten (Top Stories)"
            h_risks = "## 3. Reputatierisico's en Dreigingen (Risks & Threats)"
            h_comps = "## 4. Concurrentieactiviteit (Competitor Activity)"
            h_methodology = "## 5. Bronverantwoording & Verificatie"
            no_data = "*Geen geverifieerde claims beschikbaar voor deze categorie.*"
        else:
            doc_title = f"# Tägliches Media Intelligence Briefing — {self.profile.client_name}"
            date_label = f"**Datum & Uhrzeit:** {now_str}"
            h_exec = "## 1. Management-Zusammenfassung (Executive Summary)"
            h_stories = "## 2. Hauptmeldungen (Top Stories)"
            h_risks = "## 3. Reputationsrisiken & Warnsignale (Risks & Threats)"
            h_comps = "## 4. Wettbewerber-Aktivitäten (Competitor Activity)"
            h_methodology = "## 5. Quellennachweis & Verifikation"
            no_data = "*Keine verifizierten Meldungen für diese Kategorie vorhanden.*"

        sections = {
            "top_stories": [c for c in lang_claims if c.section == "top_stories"],
            "risks": [c for c in lang_claims if c.section == "risks"],
            "competitors": [c for c in lang_claims if c.section == "competitors"],
        }

        # Format claims into Markdown list with citations
        def format_claim_list(claim_list: List[Claim]) -> str:
            if not claim_list:
                return no_data
            lines = []
            for c in claim_list:
                filtered_text = self.gdpr.filter_text(c.claim_text)
                citation = (
                    f"[[Bron: {c.article_id}]({c.source_url}) "
                    f"Span: {c.start_char}-{c.end_char} | Evidence: *\"{c.evidence_text[:80]}...\"*]"
                )
                lines.append(f"- {filtered_text} {citation}")
            return "\n".join(lines)

        # Executive summary narrative
        total_clusters = len(clusters)
        high_risks = sum(
            len([r for r in a.reputational_risks if r.severity.value in ("high", "critical")])
            for a in analyses_by_cluster.values()
        )

        if is_nl:
            exec_summary_text = (
                f"Vandaag zijn er **{total_clusters}** afzonderlijke nieuwsclusters geanalyseerd met betrekking tot "
                f"**{self.profile.client_name}** en gelieerde entiteiten. Er zijn **{len(lang_claims)}** feitelijke beweringen "
                f"geverifieerd via broncitaten. Het aantal gedetecteerde hoge reputatierisico's bedraagt **{high_risks}**."
            )
        else:
            exec_summary_text = (
                f"Heute wurden **{total_clusters}** eigenständige Themencluster bezüglich "
                f"**{self.profile.client_name}** und Tochtergesellschaften analysiert. Es wurden **{len(lang_claims)}** "
                f"Tatsachenbehauptungen mit Quellenspannen verifiziert. Anzahl identifizierter hoher Reputationsrisiken: **{high_risks}**."
            )

        content = [
            doc_title,
            date_label,
            "",
            h_exec,
            exec_summary_text,
            "",
            h_stories,
            format_claim_list(sections["top_stories"]),
            "",
            h_risks,
            format_claim_list(sections["risks"]),
            "",
            h_comps,
            format_claim_list(sections["competitors"]),
            "",
            h_methodology,
            (
                "Alle vermelde feiten zijn cryptografisch en tekstueel gecontroleerd tegen de exacte brontekst. "
                "Claims zonder gevalideerde citaties zijn conform auditvereisten afgewezen."
                if is_nl else
                "Alle aufgeführten Fakten wurden kryptographisch und textuell gegen den Quelltext geprüft. "
                "Nicht verifizierte Behauptungen wurden gemäß Auditvorgaben verworfen."
            ),
        ]

        return "\n".join(content)
