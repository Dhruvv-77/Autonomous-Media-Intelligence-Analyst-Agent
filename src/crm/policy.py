"""Deterministic policy gate for CRM actions."""

from __future__ import annotations

import hashlib
from typing import List, Optional
from pydantic import BaseModel
from src.config import CRMConfig
from src.models import ReputationalRisk, RiskSeverity


class CRMTaskProposal(BaseModel):
    idempotency_key: str
    client_name: str
    cluster_id: str
    title: str
    description: str
    severity: RiskSeverity


class CRMPolicyGate:
    def __init__(self, config: CRMConfig, client_name: str) -> None:
        self.config = config
        self.client_name = client_name
        self.tasks_created_this_run = 0

    def evaluate_risk(
        self,
        cluster_id: str,
        risk: ReputationalRisk,
        has_verified_claims: bool
    ) -> Optional[CRMTaskProposal]:
        """
        Deterministically evaluates whether a reputational risk qualifies for a CRM task.
        Rules:
        1. Only high or critical severity risks qualify.
        2. Must be backed by verified factual evidence in the cluster.
        3. Maximum 5 tasks per run cap must not be exceeded.
        4. Derives deterministic idempotency key.
        """
        if not self.config.enabled:
            return None

        # Rule 1: High severity requirement
        if risk.severity not in (RiskSeverity.HIGH, RiskSeverity.CRITICAL):
            return None

        # Rule 2: Evidence check
        if not has_verified_claims:
            return None

        # Rule 3: 5 tasks per run cap
        if self.tasks_created_this_run >= self.config.max_tasks_per_run:
            return None

        # Rule 4: Deterministic idempotency key
        seed = f"{self.client_name}:{cluster_id}:{risk.category}:{risk.description}".encode("utf-8")
        idempotency_key = hashlib.sha256(seed).hexdigest()

        title = f"High Reputational Risk Alert [{risk.category.upper()}]: {self.client_name}"
        proposal = CRMTaskProposal(
            idempotency_key=idempotency_key,
            client_name=self.client_name,
            cluster_id=cluster_id,
            title=title,
            description=risk.description,
            severity=risk.severity
        )

        self.tasks_created_this_run += 1
        return proposal
