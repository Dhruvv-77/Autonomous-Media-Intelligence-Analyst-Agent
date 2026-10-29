# Architecture Decision Records (Initial)

## ADR-001: Python orchestrator over a multi-agent framework
**Decision:** Use a deterministic Python pipeline with typed stage contracts.  
**Reason:** The assessment is time-boxed to five working days; explicit control improves testability, cost enforcement, reproducibility, and action safety. Components may be described as agents, but must not have uncontrolled tool access.

## ADR-002: Live news discovery, not a fabricated corpus
**Decision:** Implement a configurable live source adapter, starting with GDELT DOC API and optional RSS.  
**Reason:** The developer has only the assessment PDF and wants a practical company-facing product. Real source coverage and retrieval limitations must be reported. Synthetic data is reserved for tests.

## ADR-003: Gemini Developer API with offline simulation fallback
**Decision:** Default to Gemini Developer API via `google-genai` SDK using BYO `GEMINI_API_KEY`, backed by an offline deterministic simulation mode for environments without API keys or during test execution.  
**Reason:** Avoids bulky local model server downloads (Ollama not required for normal usage); adheres strictly to the €4.00 hard spend limit; tracks real-time token usage and degradation reserve; and enables reproducible offline testing.

## ADR-004: Streamlit UI plus canonical CLI
**Decision:** Provide a Streamlit dashboard, but keep `python -m src.main run --config config.yaml` as the canonical full-pipeline command.  
**Reason:** A dashboard improves stakeholder demonstration; the CLI is easier to reproduce, automate, and use in CI.

## ADR-005: Mock CRM until the official contract exists
**Decision:** Implement a local mock CRM adapter and typed interface.  
**Reason:** The assessment PDF mentions a mock CRM API, but its OpenAPI specification/server were not provided. Do not invent or misrepresent an official API.

## ADR-006: Separate evidence verification from generation
**Decision:** LLM-generated claims are structured and independently checked against stored source spans before publication.  
**Reason:** Citation faithfulness is heavily weighted, and fabricated citations are an automatic disqualifier.

## ADR-007: Explicitly separate official and self-created evaluation data
**Decision:** Do not claim official gold-set metrics until the official labels are supplied.  
**Reason:** Metrics must be reproducible and evaluation methodology must be honest. A manually labelled real-news set can provide provisional evidence only when clearly labelled self-created.
