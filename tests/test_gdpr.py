"""Tests for GDPR compliance: natural person pseudonymization and Article 9 restriction."""

import pytest
from src.config import ClientProfile, ExecutiveProfile
from src.privacy.gdpr import GDPRFilter


def test_approved_profile_executives_remain_named():
    profile = ClientProfile(
        client_name="Global Logistics NV",
        executives=[
            ExecutiveProfile(name="Jan de Vries", role="CEO"),
            ExecutiveProfile(name="Elke Schneider", role="CFO")
        ]
    )
    gdpr = GDPRFilter(profile)
    text = "CEO Jan de Vries gaf toelichting op de jaarcijfers van Global Logistics NV."
    filtered = gdpr.filter_text(text)
    assert "Jan de Vries" in filtered


def test_unapproved_natural_persons_are_pseudonymized():
    profile = ClientProfile(
        client_name="Global Logistics NV",
        executives=[
            ExecutiveProfile(name="Jan de Vries", role="CEO")
        ]
    )
    gdpr = GDPRFilter(profile)
    # "woordvoerder Peter Bakker" is not in the profile
    text = "Volgens woordvoerder Peter Bakker is er geen sprake van vertraging."
    filtered = gdpr.filter_text(text)
    assert "Peter Bakker" not in filtered
    assert "woordvoerder" in filtered.lower()


def test_article_9_special_category_inferences_blocked():
    profile = ClientProfile(client_name="Global Logistics NV")
    gdpr = GDPRFilter(profile)
    text = "Berichtgeving over political opinions en health condition van het personeel."
    filtered = gdpr.filter_text(text)
    assert "political opinions" not in filtered
    assert "health condition" not in filtered
    assert "[REDACTED_GDPR_ARTICLE_9]" in filtered
