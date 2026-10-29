"""Configuration management for Autonomous Media Intelligence Analyst Agent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    name: str = "Autonomous Media Intelligence Analyst Agent"
    timezone: str = "UTC"
    output_dir: str = "outputs"
    database_url: str = "sqlite:///outputs/agent.db"


class RunConfig(BaseModel):
    max_articles: int = 1500
    lookback_hours: int = 24
    max_runtime_seconds: int = 900
    resume_interrupted_runs: bool = True
    input_corpus_path: Optional[str] = None


class BudgetConfig(BaseModel):
    max_llm_eur: float = 4.00
    reserve_fraction: float = 0.15
    currency: str = "EUR"
    price_table_version: str = "2026-q1"
    paid_provider_enabled: bool = False
    
    # Provider pricing per million tokens in EUR
    input_cost_per_million: float = 0.075   # e.g., gemini-2.5-flash / flash-lite tier
    output_cost_per_million: float = 0.30


class NewsConfig(BaseModel):
    discovery_provider: str = "gdelt"  # 'gdelt', 'rss', or 'local'
    languages: List[str] = Field(default_factory=lambda: ["nl", "de", "fr", "en"])
    max_results_per_query: int = 250
    request_timeout_seconds: int = 20
    max_retries: int = 3
    per_host_concurrency: int = 3
    rss_feeds: List[str] = Field(default_factory=list)
    respect_robots_and_source_terms: bool = True
    allow_paywall_bypass: bool = False
    blocked_hosts: List[str] = Field(
        default_factory=lambda: [
            "localhost",
            "127.0.0.1",
            "::1",
            "169.254.169.254",
            "metadata.google.internal",
        ]
    )


class LLMConfig(BaseModel):
    provider: str = "gemini"  # 'gemini' or 'simulation'
    model: str = "gemini-3.8-flash"
    temperature: float = 0.0
    timeout_seconds: int = 90
    max_retries: int = 3
    free_tier_only: bool = True
    paid_fallback_enabled: bool = False
    api_key: Optional[str] = None


class EmbeddingsConfig(BaseModel):
    model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    clustering_threshold: float = 0.82
    deterministic_seed: int = 42


class ExecutiveProfile(BaseModel):
    name: str
    role: str


class ClientProfile(BaseModel):
    client_name: str = "Global Logistics NV"
    brands: List[str] = Field(default_factory=lambda: ["EuroFreight", "CargoExpress"])
    subsidiaries: List[str] = Field(default_factory=lambda: ["Logistics BeNeLux BV", "Logistics Deutschland GmbH"])
    competitors: List[str] = Field(default_factory=lambda: ["Maersk", "DHL Group", "Kuehne+Nagel", "DB Schenker"])
    executives: List[ExecutiveProfile] = Field(
        default_factory=lambda: [
            ExecutiveProfile(name="Jan de Vries", role="Chief Executive Officer"),
            ExecutiveProfile(name="Elke Schneider", role="Chief Financial Officer"),
        ]
    )
    topics_include: List[str] = Field(
        default_factory=lambda: ["supply chain", "logistics", "freight rates", "port strike", "customs", "green transport"]
    )
    topics_exclude: List[str] = Field(
        default_factory=lambda: ["sports sponsorship", "celebrity gossip"]
    )
    search_terms: List[str] = Field(
        default_factory=lambda: ["Global Logistics", "EuroFreight", "Logistics BeNeLux"]
    )
    output_languages: List[str] = Field(default_factory=lambda: ["nl", "de"])


class PrivacyConfig(BaseModel):
    only_profile_people_may_be_named: bool = True
    pseudonymize_other_people: bool = True
    infer_gdpr_article_9_categories: bool = False
    redact_secrets_from_logs: bool = True


class CRMConfig(BaseModel):
    mode: str = "mock"  # 'mock' or 'api'
    enabled: bool = True
    api_url: str = "http://127.0.0.1:8000"
    max_tasks_per_run: int = 5
    minimum_severity: str = "high"  # 'high', 'critical'
    idempotency_enabled: bool = True
    simulated_failure_rate: float = 0.10  # 10% transient failure rate to test resilience


class ObservabilityConfig(BaseModel):
    trace_jsonl: bool = True
    log_llm_inputs: bool = False
    redact_sensitive_fields: bool = True
    record_token_usage: bool = True
    record_cost_estimates: bool = True


class AgentSystemConfig(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    run: RunConfig = Field(default_factory=RunConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    news: NewsConfig = Field(default_factory=NewsConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    client_profile: ClientProfile = Field(default_factory=ClientProfile)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    crm: CRMConfig = Field(default_factory=CRMConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> AgentSystemConfig:
        """Load configuration from YAML file and .env environment variables."""
        load_dotenv()
        data = {}
        if config_path and Path(config_path).exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        config = cls.model_validate(data)
        
        # Override with environment variable if present
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            config.llm.api_key = api_key
            
        return config
