"""Cluster-level intelligence analysis: sentiment, tone, topics, competitor actions, and reputational risks."""

from __future__ import annotations

from typing import Dict, List, Optional
from src.analysis.gemini_client import GeminiClient
from src.config import ClientProfile
from src.models import Article, Cluster, ClusterAnalysis, ReputationalRisk, RiskSeverity, Sentiment


class ClusterAnalyst:
    def __init__(self, profile: ClientProfile, gemini_client: Optional[GeminiClient] = None) -> None:
        self.profile = profile
        self.gemini_client = gemini_client

    def analyze_cluster(self, cluster: Cluster, articles_by_id: Dict[str, Article]) -> ClusterAnalysis:
        """
        Classifies sentiment and tone towards the client per story cluster, not per article.
        Identifies main topics, competitor mentions, and potential reputational risks.
        """
        cluster_articles = [articles_by_id[aid] for aid in cluster.article_ids if aid in articles_by_id]
        if not cluster_articles:
            return ClusterAnalysis(
                cluster_id=cluster.cluster_id,
                sentiment=Sentiment.NEUTRAL,
                tone="neutral",
                topics=[],
                competitor_mentions=[],
                reputational_risks=[]
            )

        combined_text = "\n\n".join(
            f"Title: {a.title}\n{a.body[:600] if a.body else ''}"
            for a in cluster_articles
        )

        # Detect competitor mentions across the cluster
        competitor_mentions = set()
        for comp in self.profile.competitors:
            if comp.lower() in combined_text.lower():
                competitor_mentions.add(comp)

        # Detect topics
        topics = set()
        for topic in self.profile.topics_include:
            if topic.lower() in combined_text.lower():
                topics.add(topic)

        # LLM analysis or deterministic rule-based analysis
        sentiment = Sentiment.NEUTRAL
        tone = "factual reporting"
        reputational_risks: List[ReputationalRisk] = []

        if self.gemini_client and self.gemini_client.is_available():
            sys_inst = (
                "You are an objective corporate media analyst. Analyze the provided news cluster concerning "
                f"the client '{self.profile.client_name}'. Respond with a JSON object containing keys: "
                "'sentiment' ('positive', 'neutral', 'negative', 'mixed'), 'tone' (string), "
                "'reputational_risks' (list of objects with 'category', 'severity' ('low','medium','high'), 'description')."
            )
            data, _, _ = self.gemini_client.generate_structured_json(
                system_instruction=sys_inst,
                user_prompt="Analyze this news cluster about our client.",
                untrusted_content=combined_text[:4000]
            )
            raw_sent = str(data.get("sentiment", "neutral")).lower()
            if raw_sent in ("positive", "negative", "neutral", "mixed"):
                sentiment = Sentiment(raw_sent)
            tone = str(data.get("tone", "factual reporting"))
            
            for r in data.get("reputational_risks", []):
                sev_str = str(r.get("severity", "low")).lower()
                sev = RiskSeverity.HIGH if sev_str in ("high", "critical") else (
                    RiskSeverity.MEDIUM if sev_str == "medium" else RiskSeverity.LOW
                )
                reputational_risks.append(
                    ReputationalRisk(
                        category=r.get("category", "operational"),
                        severity=sev,
                        description=r.get("description", ""),
                        article_id=cluster.article_ids[0]
                    )
                )
        else:
            # Deterministic rule-based cluster analysis
            text_lower = combined_text.lower()
            negative_triggers = [
                "strike", "staking", "streik", "grève", "investigation", "onderzoek", "ermittlung",
                "fraud", "fraude", "court", "rechtbank", "gericht", "fine", "boete", "strafe",
                "lawsuit", "rechtszaak", "delay", "vertraging", "verzögerung", "breach", "crisis", "dispute", "protest"
            ]
            positive_triggers = [
                "expansion", "uitbreiding", "wachstum", "record profit", "recordwinst", "rekordgewinn",
                "growth", "award", "partnership", "sustainability prize", "innovation"
            ]

            found_neg = [w for w in negative_triggers if w in text_lower]
            found_pos = [w for w in positive_triggers if w in text_lower]

            if found_neg and found_pos:
                sentiment = Sentiment.MIXED
                tone = "mixed coverage"
            elif found_neg:
                sentiment = Sentiment.NEGATIVE
                tone = "critical scrutiny"
            elif found_pos:
                sentiment = Sentiment.POSITIVE
                tone = "favorable coverage"

            # Check for high-severity reputational risks
            for art in cluster_articles:
                art_lower = art.body.lower() if art.body else art.title.lower()
                if any(w in art_lower for w in ["strike", "staking", "streik", "grève", "port shutdown", "havensluiting"]):
                    reputational_risks.append(
                        ReputationalRisk(
                            category="operational",
                            severity=RiskSeverity.HIGH,
                            description=f"Operational supply chain disruption: {art.title}",
                            evidence_text=art.body[:150] if art.body else art.title,
                            article_id=art.id
                        )
                    )
                elif any(w in art_lower for w in ["fraud", "fraude", "criminal investigation", "strafrechtelijk onderzoek", "regulatory fine", "douaneboete", "tax evasion"]):
                    reputational_risks.append(
                        ReputationalRisk(
                            category="legal",
                            severity=RiskSeverity.HIGH,
                            description=f"Legal / regulatory compliance risk: {art.title}",
                            evidence_text=art.body[:150] if art.body else art.title,
                            article_id=art.id
                        )
                    )

        return ClusterAnalysis(
            cluster_id=cluster.cluster_id,
            sentiment=sentiment,
            tone=tone,
            topics=sorted(list(topics)),
            competitor_mentions=sorted(list(competitor_mentions)),
            reputational_risks=reputational_risks
        )
