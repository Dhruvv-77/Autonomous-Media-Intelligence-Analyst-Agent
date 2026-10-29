"""Tests for CRM action safety: 5-task cap, idempotency, retry resilience, and audit logging."""

import pytest
from src.config import CRMConfig
from src.crm.client import CRMClient
from src.crm.policy import CRMPolicyGate
from src.models import ReputationalRisk, RiskSeverity
from src.storage.database import Database


def test_crm_five_task_cap(tmp_path):
    config = CRMConfig(enabled=True, max_tasks_per_run=5)
    gate = CRMPolicyGate(config, client_name="Global Logistics NV")

    # Generate 8 high severity risks
    proposals = []
    for i in range(8):
        risk = ReputationalRisk(
            category="operational",
            severity=RiskSeverity.HIGH,
            description=f"Critical port disruption #{i}"
        )
        prop = gate.evaluate_risk(f"cl_{i}", risk, has_verified_claims=True)
        if prop:
            proposals.append(prop)

    assert len(proposals) == 5, f"Expected strictly 5 proposals max, got {len(proposals)}"


def test_crm_idempotency_prevents_duplicate_tasks(tmp_path):
    db_file = tmp_path / "test_crm.db"
    db = Database(str(db_file))
    config = CRMConfig(enabled=True, max_tasks_per_run=5, simulated_failure_rate=0.0)
    gate = CRMPolicyGate(config, client_name="Global Logistics NV")
    client = CRMClient(config, db, run_id="run_crm_01")

    risk = ReputationalRisk(
        category="legal",
        severity=RiskSeverity.HIGH,
        description="Customs tax investigation launched"
    )

    prop = gate.evaluate_risk("cl_tax_01", risk, has_verified_claims=True)
    assert prop is not None

    # First execution: creates task
    ok1, msg1, task1 = client.execute_task_creation(prop)
    assert ok1 is True
    assert task1 is not None

    # Second execution (e.g. re-run or retry): idempotent, no duplicate task
    ok2, msg2, task2 = client.execute_task_creation(prop)
    assert ok2 is True
    assert "already exists" in msg2.lower()

    # Verify only 1 task in database
    tasks = db.get_crm_tasks("run_crm_01")
    assert len(tasks) == 1
    assert tasks[0]["idempotency_key"] == prop.idempotency_key

    # Verify audit logs record both calls
    audits = db.get_crm_audit_logs("run_crm_01")
    assert len(audits) >= 2


def test_crm_audit_trail_recorded(tmp_path):
    db_file = tmp_path / "test_crm_audit.db"
    db = Database(str(db_file))
    config = CRMConfig(enabled=True, max_tasks_per_run=5, simulated_failure_rate=0.0)
    gate = CRMPolicyGate(config, client_name="Global Logistics NV")
    client = CRMClient(config, db, run_id="run_crm_02")

    risk = ReputationalRisk(
        category="operational",
        severity=RiskSeverity.HIGH,
        description="Cargo vessel breakdown in Antwerp"
    )
    prop = gate.evaluate_risk("cl_antwerp", risk, has_verified_claims=True)
    client.execute_task_creation(prop)

    audits = db.get_crm_audit_logs("run_crm_02")
    assert len(audits) >= 1
    latest = audits[0]
    assert latest["action"] == "create_task_success"
    assert latest["status_code"] in (200, 201)
