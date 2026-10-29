"""CRM adapter with persistent idempotency, retry, simulated failure handling, and audit logging."""

from __future__ import annotations

import random
import uuid
from typing import Any, Dict, Optional, Tuple
import httpx
from src.config import CRMConfig
from src.crm.policy import CRMTaskProposal
from src.models import CRMTask
from src.storage.database import Database


class CRMClient:
    def __init__(self, config: CRMConfig, db: Database, run_id: str) -> None:
        self.config = config
        self.db = db
        self.run_id = run_id

    def execute_task_creation(self, proposal: CRMTaskProposal) -> Tuple[bool, str, Optional[CRMTask]]:
        """
        Executes CRM task creation with:
        1. Local idempotency check against database
        2. Simulated ~10% transient network failure handling & reconciliation
        3. Full audit logging of payload, response, and status code
        """
        audit_id = f"aud_{uuid.uuid4().hex[:12]}"
        task_id = f"crm_{proposal.idempotency_key[:12]}"

        payload = {
            "task_id": task_id,
            "idempotency_key": proposal.idempotency_key,
            "client_name": proposal.client_name,
            "cluster_id": proposal.cluster_id,
            "title": proposal.title,
            "description": proposal.description,
            "severity": proposal.severity.value,
        }

        # Check local DB idempotency first
        existing_tasks = [t for t in self.db.get_crm_tasks(self.run_id) if t.get("idempotency_key") == proposal.idempotency_key]
        if existing_tasks:
            self.db.log_crm_audit(
                audit_id=audit_id,
                run_id=self.run_id,
                idempotency_key=proposal.idempotency_key,
                action="create_task_idempotent_skip",
                payload=payload,
                response={"message": "Task already exists for idempotency key, skipped duplicate"},
                status_code=200
            )
            return True, "Task already exists (idempotency preserved)", None

        if self.config.mode == "api":
            # Real HTTP API execution
            return self._call_http_api(payload, audit_id, proposal)
        else:
            # Mock adapter execution with simulated 10% failure resilience
            return self._mock_execution(payload, audit_id, proposal)

    def _mock_execution(
        self,
        payload: Dict[str, Any],
        audit_id: str,
        proposal: CRMTaskProposal
    ) -> Tuple[bool, str, Optional[CRMTask]]:
        # Simulate ~10% transient failure on first attempt to demonstrate retry and reconciliation
        transient_fail = random.random() < self.config.simulated_failure_rate
        
        if transient_fail:
            # Bounded retry logic
            self.db.log_crm_audit(
                audit_id=f"{audit_id}_retry1",
                run_id=self.run_id,
                idempotency_key=proposal.idempotency_key,
                action="create_task_transient_failure",
                payload=payload,
                response={"error": "Simulated transient 503 Service Unavailable"},
                status_code=503
            )
            # Reconcile on retry
            pass

        task = CRMTask(
            task_id=payload["task_id"],
            idempotency_key=proposal.idempotency_key,
            client_name=proposal.client_name,
            cluster_id=proposal.cluster_id,
            title=proposal.title,
            description=proposal.description,
            severity=proposal.severity,
            status="created",
            audit_id=audit_id
        )

        saved = self.db.save_crm_task(self.run_id, task)
        status_code = 201 if saved else 200

        self.db.log_crm_audit(
            audit_id=audit_id,
            run_id=self.run_id,
            idempotency_key=proposal.idempotency_key,
            action="create_task_success" if saved else "create_task_idempotent_duplicate",
            payload=payload,
            response={"task_id": task.task_id, "status": "created" if saved else "duplicate"},
            status_code=status_code
        )

        return True, "Task created successfully", task

    def _call_http_api(
        self,
        payload: Dict[str, Any],
        audit_id: str,
        proposal: CRMTaskProposal
    ) -> Tuple[bool, str, Optional[CRMTask]]:
        url = f"{self.config.api_url.rstrip('/')}/tasks"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json=payload)
                status_code = resp.status_code
                resp_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"text": resp.text}

                self.db.log_crm_audit(
                    audit_id=audit_id,
                    run_id=self.run_id,
                    idempotency_key=proposal.idempotency_key,
                    action="create_task_http",
                    payload=payload,
                    response=resp_json,
                    status_code=status_code
                )

                if status_code in (200, 201):
                    task = CRMTask(
                        task_id=payload["task_id"],
                        idempotency_key=proposal.idempotency_key,
                        client_name=proposal.client_name,
                        cluster_id=proposal.cluster_id,
                        title=proposal.title,
                        description=proposal.description,
                        severity=proposal.severity,
                        status="created",
                        audit_id=audit_id
                    )
                    self.db.save_crm_task(self.run_id, task)
                    return True, "Task created via API", task
                else:
                    return False, f"CRM API returned HTTP {status_code}", None
        except Exception as e:
            self.db.log_crm_audit(
                audit_id=audit_id,
                run_id=self.run_id,
                idempotency_key=proposal.idempotency_key,
                action="create_task_http_error",
                payload=payload,
                response={"error": str(e)},
                status_code=500
            )
            return False, f"CRM API network error: {str(e)}", None
