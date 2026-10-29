"""GDPR compliance filter: natural person pseudonymization and Article 9 restriction."""

from __future__ import annotations

import re
from typing import List, Set
from src.config import ClientProfile


class GDPRFilter:
    def __init__(self, profile: ClientProfile) -> None:
        self.profile = profile
        self.approved_names: Set[str] = {
            exec_p.name.strip().lower() for exec_p in profile.executives if exec_p.name
        }
        
        # Article 9 special category patterns that must never be inferred
        self.article_9_triggers = [
            re.compile(r"\b(racial|ethnic origin|political opinions|religious beliefs|philosophical beliefs)\b", re.IGNORECASE),
            re.compile(r"\b(trade union membership|genetic data|biometric data|health condition|medical diagnosis)\b", re.IGNORECASE),
            re.compile(r"\b(sexual orientation|sex life|gesundheitszustand|gewerkschaftsmitgliedschaft)\b", re.IGNORECASE),
        ]

    def filter_text(self, text: str) -> str:
        """
        Applies GDPR privacy constraints:
        1. Only people named in the client profile may be explicitly named.
        2. All other persons are referred to by role or pseudonymized.
        3. Redacts / removes any GDPR Article 9 special-category inferences.
        """
        if not text:
            return text

        result = text

        # 1. Block Article 9 inferences
        for pat in self.article_9_triggers:
            result = pat.sub("[REDACTED_GDPR_ARTICLE_9]", result)

        # 2. Known common non-approved executive/minister/person patterns in Dutch and German news
        # Examples: "Minister Peter Schmidt", "woordvoerder Jan Klaassen", "Herr Klaus Meier", "Dr. Hans Weber"
        role_person_patterns = [
            (re.compile(r"\b(woordvoerder|spokesperson|pressesprecher)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", re.IGNORECASE), r"een \1"),
            (re.compile(r"\b(minister|rechter|judge|richter|direktor|director)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", re.IGNORECASE), r"de \1"),
            (re.compile(r"\b(de heer|mevrouw|herr|frau|mr\.|mrs\.|dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", re.IGNORECASE), r"[Betrokken persoon]"),
        ]

        for pat, replacement in role_person_patterns:
            matches = list(pat.finditer(result))
            for m in reversed(matches):
                full_matched = m.group(0)
                # Check if this matched person is an approved executive
                matched_lower = full_matched.lower()
                if any(approved in matched_lower for approved in self.approved_names):
                    continue  # Approved executive, keep named
                # Otherwise replace with role or pseudonym
                subbed = pat.sub(replacement, full_matched)
                start, end = m.span()
                result = result[:start] + subbed + result[end:]

        return result
