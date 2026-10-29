"""Tests for €4.00 budget enforcement, safety reserve margin, and degradation mode."""

import pytest
from src.config import BudgetConfig
from src.cost.ledger import BudgetExceededError, CostLedger
from src.storage.database import Database


def test_cost_ledger_calculation_and_tracking(tmp_path):
    db_file = tmp_path / "test_cost.db"
    db = Database(str(db_file))
    config = BudgetConfig(
        max_llm_eur=4.00,
        reserve_fraction=0.15,
        input_cost_per_million=0.10,
        output_cost_per_million=0.40
    )

    ledger = CostLedger(config, db, run_id="run_cost_test_01")
    assert ledger.is_degraded() is False
    assert ledger.can_spend(0.50) is True

    # Record 1M input tokens + 1M output tokens = €0.50
    event = ledger.record_usage("gemini", "gemini-2.5-flash", 1_000_000, 1_000_000)
    assert event.cost_eur == 0.50
    assert ledger.cumulative_cost_eur == 0.50
    assert ledger.is_degraded() is False


def test_safety_reserve_triggers_degradation(tmp_path):
    db_file = tmp_path / "test_cost2.db"
    db = Database(str(db_file))
    config = BudgetConfig(max_llm_eur=4.00, reserve_fraction=0.15)  # reserve threshold = 4.0 * 0.85 = 3.40 EUR
    ledger = CostLedger(config, db, run_id="run_cost_test_02")

    # Spend €3.50 (above €3.40 safety threshold, below €4.00 hard cap)
    ledger.record_usage("gemini", "gemini-2.5-flash", 0, 0, billed_cost_override=3.50)
    assert ledger.is_degraded() is True
    assert ledger.can_spend(0.40) is True  # 3.50 + 0.40 = 3.90 <= 4.00


def test_hard_cap_breach_raises_budget_exceeded(tmp_path):
    db_file = tmp_path / "test_cost3.db"
    db = Database(str(db_file))
    config = BudgetConfig(max_llm_eur=4.00, reserve_fraction=0.15)
    ledger = CostLedger(config, db, run_id="run_cost_test_03")

    ledger.record_usage("gemini", "gemini-2.5-flash", 0, 0, billed_cost_override=3.80)
    
    # Attempting to spend €0.30 more will cross €4.00 hard ceiling
    with pytest.raises(BudgetExceededError):
        ledger.record_usage("gemini", "gemini-2.5-flash", 0, 0, billed_cost_override=0.30)
