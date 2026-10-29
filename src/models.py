"""Data schemas and domain models for Autonomous Media Intelligence Analyst Agent."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BodyStatus(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    METADATA_ONLY = "metadata_only"
    BLOCKED = "blocked"
    FAILED = "failed"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class RiskSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class Article(BaseModel):
    id: str
    source: str
    published_at: Optional[datetime] = None
    language: str = "en"
    title: str
    body: str = ""
    url: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    body_status: BodyStatus = BodyStatus.FULL
    content_hash: str = ""
    source_query: Optional[str] = None
    retrieval_error: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if not self.content_hash:
            payload = f"{self.title}\n{self.body}".encode("utf-8")
            self.content_hash = hashlib.sha256(payload).hexdigest()
        if not self.id:
            raw_id = f"{self.url}::{self.published_at}".encode("utf-8")
            self.id = hashlib.sha256(raw_id).hexdigest()[:16]


class Cluster(BaseModel):
    cluster_id: str
    article_ids: List[str] = Field(default_factory=list)
    canonical_title: str
    earliest_published_at: Optional[datetime] = None
    first_source: Optional[str] = None
    syndication_sources: List[str] = Field(default_factory=list)
    is_update: bool = False
    update_of_cluster_id: Optional[str] = None


class EntityMention(BaseModel):
    mention_id: str
    article_id: str
    entity_name: str
    entity_type: str = "organization"  # 'organization', 'brand', 'subsidiary', 'executive', 'other'
    is_client: bool
    confidence: float
    justification: str
    evidence_text: str
    start_char: int
    end_char: int


class ReputationalRisk(BaseModel):
    category: str  # 'financial', 'legal', 'operational', 'environmental', 'ethical'
    severity: RiskSeverity
    description: str
    evidence_text: Optional[str] = None
    article_id: Optional[str] = None


class ClusterAnalysis(BaseModel):
    cluster_id: str
    sentiment: Sentiment
    tone: str
    topics: List[str] = Field(default_factory=list)
    competitor_mentions: List[str] = Field(default_factory=list)
    reputational_risks: List[ReputationalRisk] = Field(default_factory=list)


class Claim(BaseModel):
    claim_id: str
    cluster_id: str
    language: str  # 'nl' or 'de'
    section: str  # 'executive_summary', 'top_stories', 'risks', 'competitors'
    claim_text: str
    article_id: str
    source_url: str
    start_char: int
    end_char: int
    evidence_text: str
    confidence: float = 1.0
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    rejection_reason: Optional[str] = None


class CRMTask(BaseModel):
    task_id: str
    idempotency_key: str
    client_name: str
    cluster_id: str
    title: str
    description: str
    severity: RiskSeverity
    status: str = "created"  # 'created', 'already_exists', 'failed'
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    audit_id: str


class TraceEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str
    stage: str
    event_type: str
    details: Dict[str, Any] = Field(default_factory=dict)
    tokens: Optional[int] = None
    cost_eur: Optional[float] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None


class CostEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_eur: float
    cumulative_cost_eur: float


class RunSummary(BaseModel):
    run_id: str
    client_name: str = "Global Logistics NV"
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"
    total_articles: int = 0
    total_clusters: int = 0
    verified_claims: int = 0
    rejected_claims: int = 0
    crm_tasks_created: int = 0
    total_cost_eur: float = 0.0
    elapsed_seconds: float = 0.0
    warnings: List[str] = Field(default_factory=list)
