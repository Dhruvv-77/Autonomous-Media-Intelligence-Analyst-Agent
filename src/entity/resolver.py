"""Entity resolution for ambiguous mentions, homonyms, subsidiaries, and executives."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple
from src.config import ClientProfile
from src.models import Article, EntityMention


class EntityResolver:
    def __init__(self, profile: ClientProfile) -> None:
        self.profile = profile
        self.common_words = {
            "cargo", "express", "logistics", "freight", "target", "apple", "orange",
            "global", "standard", "general", "national", "continental", "swift"
        }

    def resolve_article(self, article: Article) -> List[EntityMention]:
        """
        Scans an article for entity mentions and disambiguates whether each refers
        to the client entity, subsidiary, brand, executive, competitor, or a homonym/other.
        Returns a list of deterministic EntityMention records with exact spans.
        """
        text = article.body or article.title
        if not text:
            return []

        mentions: List[EntityMention] = []
        mention_counter = 0

        # 1. Search for Client Name
        client_matches = list(re.finditer(re.escape(self.profile.client_name), text, re.IGNORECASE))
        for m in client_matches:
            mention_counter += 1
            start, end = m.span()
            snippet = text[start:end]
            mentions.append(
                EntityMention(
                    mention_id=f"{article.id}_ent_{mention_counter:03d}",
                    article_id=article.id,
                    entity_name=self.profile.client_name,
                    entity_type="organization",
                    is_client=True,
                    confidence=0.98,
                    justification=f"Exact match for primary client name '{self.profile.client_name}' in business context",
                    evidence_text=snippet,
                    start_char=start,
                    end_char=end,
                )
            )

        # 2. Search for Subsidiaries
        for sub in self.profile.subsidiaries:
            for m in re.finditer(re.escape(sub), text, re.IGNORECASE):
                mention_counter += 1
                start, end = m.span()
                snippet = text[start:end]
                mentions.append(
                    EntityMention(
                        mention_id=f"{article.id}_ent_{mention_counter:03d}",
                        article_id=article.id,
                        entity_name=sub,
                        entity_type="subsidiary",
                        is_client=True,
                        confidence=0.95,
                        justification=f"Matches approved subsidiary entity '{sub}'",
                        evidence_text=snippet,
                        start_char=start,
                        end_char=end,
                    )
                )

        # 3. Search for Brands (handling ambiguous common words)
        for brand in self.profile.brands:
            for m in re.finditer(r"\b" + re.escape(brand) + r"\b", text, re.IGNORECASE):
                mention_counter += 1
                start, end = m.span()
                snippet = text[start:end]
                
                # Context window around mention
                ctx_start = max(0, start - 150)
                ctx_end = min(len(text), end + 150)
                context_window = text[ctx_start:ctx_end].lower()

                # Check if brand is a common word / homonym
                is_common = brand.lower() in self.common_words
                has_topic_context = any(topic.lower() in context_window for topic in self.profile.topics_include)
                has_client_co_occurrence = self.profile.client_name.lower() in text.lower()

                if is_common and not (has_topic_context or has_client_co_occurrence):
                    # Ambiguous common word used generically
                    mentions.append(
                        EntityMention(
                            mention_id=f"{article.id}_ent_{mention_counter:03d}",
                            article_id=article.id,
                            entity_name=brand,
                            entity_type="brand",
                            is_client=False,
                            confidence=0.35,
                            justification=f"'{brand}' treated as generic common noun/phrase; lacks client or sector context signals",
                            evidence_text=snippet,
                            start_char=start,
                            end_char=end,
                        )
                    )
                else:
                    conf = 0.90 if has_client_co_occurrence else 0.75
                    mentions.append(
                        EntityMention(
                            mention_id=f"{article.id}_ent_{mention_counter:03d}",
                            article_id=article.id,
                            entity_name=brand,
                            entity_type="brand",
                            is_client=True,
                            confidence=conf,
                            justification=f"Brand '{brand}' corroborated by domain context in surrounding text",
                            evidence_text=snippet,
                            start_char=start,
                            end_char=end,
                        )
                    )

        # 4. Search for Approved Executives (handling former vs active)
        for exec_prof in self.profile.executives:
            for m in re.finditer(re.escape(exec_prof.name), text, re.IGNORECASE):
                mention_counter += 1
                start, end = m.span()
                snippet = text[start:end]

                ctx_start = max(0, start - 100)
                ctx_end = min(len(text), end + 100)
                window = text[ctx_start:ctx_end].lower()

                is_former = any(former_kw in window for former_kw in ["former", "voormalig", "ehemalig", "ex-", "ex "])
                if is_former:
                    mentions.append(
                        EntityMention(
                            mention_id=f"{article.id}_ent_{mention_counter:03d}",
                            article_id=article.id,
                            entity_name=exec_prof.name,
                            entity_type="executive",
                            is_client=False,
                            confidence=0.88,
                            justification=f"'{exec_prof.name}' identified as former executive in surrounding text",
                            evidence_text=snippet,
                            start_char=start,
                            end_char=end,
                        )
                    )
                else:
                    mentions.append(
                        EntityMention(
                            mention_id=f"{article.id}_ent_{mention_counter:03d}",
                            article_id=article.id,
                            entity_name=exec_prof.name,
                            entity_type="executive",
                            is_client=True,
                            confidence=0.96,
                            justification=f"Approved executive '{exec_prof.name}' ({exec_prof.role}) actively represented",
                            evidence_text=snippet,
                            start_char=start,
                            end_char=end,
                        )
                    )

        # 5. Search for Competitors
        for comp in self.profile.competitors:
            for m in re.finditer(r"\b" + re.escape(comp) + r"\b", text, re.IGNORECASE):
                mention_counter += 1
                start, end = m.span()
                snippet = text[start:end]
                mentions.append(
                    EntityMention(
                        mention_id=f"{article.id}_ent_{mention_counter:03d}",
                        article_id=article.id,
                        entity_name=comp,
                        entity_type="competitor",
                        is_client=False,
                        confidence=0.95,
                        justification=f"Known competitor '{comp}' identified",
                        evidence_text=snippet,
                        start_char=start,
                        end_char=end,
                    )
                )

        return mentions
