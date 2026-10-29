"""Real-time LLM cost tracking, budget enforcement, and degradation mode handling."""

from __future__ import annotations

from typing import Optional
from src.config import BudgetConfig
from src.models import CostEvent
from src.storage.database import Database


class BudgetExceededError(Exception):
    """Raised when hard budget limit is exceeded."""
    pass


class CostLedger:
    def __init__(self, config: BudgetConfig, db: Database, run_id: str) -> None:
        self.config = config
        self.db = db
        self.run_id = run_id
        self.cumulative_cost_eur: float = self.db.get_total_cost(run_id)
        # Safety threshold after reserving safety margin
        self.reserve_threshold_eur = self.config.max_llm_eur * (1.0 - self.config.reserve_fraction)

    def is_degraded(self) -> bool:
        """Returns True if spend is within the safety reserve margin near the limit."""
        return self.cumulative_cost_eur >= self.reserve_threshold_eur

    def can_spend(self, estimated_cost_eur: float = 0.0) -> bool:
        """Checks if an additional cost can be incurred without breaching the hard limit."""
        return (self.cumulative_cost_eur + estimated_cost_eur) <= self.config.max_llm_eur

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculates cost in EUR based on configured rates per million tokens."""
        input_cost = (input_tokens / 1_000_000.0) * self.config.input_cost_per_million
        output_cost = (output_tokens / 1_000_000.0) * self.config.output_cost_per_million
        return round(input_cost + output_cost, 6)

    def record_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        billed_cost_override: Optional[float] = None
    ) -> CostEvent:
        """Records token usage and cost, updating cumulative spend and persistence."""
        if billed_cost_override is not None:
            cost = billed_cost_override
        else:
            cost = self.calculate_cost(input_tokens, output_tokens)

        if not self.can_spend(cost):
            raise BudgetExceededError(
                f"LLM Spend limit reached: €{self.cumulative_cost_eur:.4f} + €{cost:.4f} > max budget €{self.config.max_llm_eur:.2f}"
            )

        self.cumulative_cost_eur += cost
        self.db.record_cost_entry(
            run_id=self.run_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_eur=cost,
            cumulative_cost_eur=self.cumulative_cost_eur
        )

        return CostEvent(
            run_id=self.run_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_eur=cost,
            cumulative_cost_eur=self.cumulative_cost_eur
        )
