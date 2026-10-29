# Instructions for AI Coding Agent

## Mission
Implement the Autonomous Media Intelligence Analyst Agent according to `DESIGN.md`, `ARCHITECTURE.md`, `REQUIREMENTS.md`, and `IMPLEMENTATION_PLAN.md`. The assessment PDF requirements take precedence over optional product ideas. Build a working, testable system, not just documentation or a mock UI.

## Before coding
1. Read all project docs and extract a checklist from `REQUIREMENTS.md`.
2. Inspect the repository and preserve any existing useful code.
3. Do not assume official data, client profile, CRM API, or gold labels exist. The developer currently has only the assessment PDF.
4. Identify missing configuration explicitly. Use placeholders rather than guessing the company's identity or secrets.
5. Create a small task plan and then implement the first end-to-end vertical slice.

## Mandatory engineering rules
- Python implementation, typed schemas, clear module boundaries, minimal unnecessary framework complexity.
- Canonical CLI command: `python -m src.main run --config config.yaml`.
- Streamlit is an optional UI that calls the same service layer; do not duplicate pipeline logic in the UI.
- Live news is the primary data source. Do not fabricate a 1,500-article dataset or present generated records as real news.
- Synthetic/adversarial examples may be used for unit/security tests only and must be clearly labelled.
- Every factual briefing claim must carry article ID, source URL, start/end character offsets, and exact evidence text.
- Store source body unchanged and verify `body[start_char:end_char] == evidence_text`.
- A separate verification stage must reject unsupported claims.
- Never allow article content to change system policy or trigger tools.
- LLM must not directly invoke CRM writes. CRM writes require deterministic policy validation.
- Enforce €4.00 maximum LLM spend per full 1,500-article run with a safety reserve, and record actual/estimated cost. Never silently enable paid billing or fall back to a paid model when free quota is exhausted.
- Enforce <15-minute target by measurement; do not claim it is met without benchmark results.
- Maximum five CRM tasks per run; persistent idempotency; audit every attempt/outcome.
- Apply GDPR rule: only people in the client profile may be named; other people must be role-described or pseudonymized; do not infer Article 9 special-category data.
- Deterministic clustering/entity decisions for identical input and pinned versions.
- Implement timeouts, bounded retries, rate-limit handling, malformed-row handling, checkpoints and resume.
- Never commit secrets. Use `.env.example` with placeholders. Do not log the Gemini API key. Document that each reviewer must obtain their own key and that free-tier eligibility, quotas, and data terms may vary.
- Do not invent the missing official CRM OpenAPI contract. Keep mock CRM clearly labelled.
- Do not report official gold-set metrics without official labels. Mark self-created evaluation labels as such.
- Use safe URL validation and block localhost/private IP ranges to reduce SSRF risks.
- Avoid storing/logging unnecessary personal data; redact secrets and sensitive payloads from traces.

## Development process
1. Work in small increments.
2. Add tests with every module.
3. Run relevant tests after each change and the full suite before declaring completion.
4. Keep dependency versions reasonably constrained and document setup.
5. When tests fail, diagnose and fix the cause; do not weaken or delete tests merely to get a green result.
6. Keep documentation synchronized with implemented behavior.
7. Record limitations and unmet requirements explicitly.
8. Never claim a command, feature, test, benchmark, or integration succeeded unless it actually ran successfully.

## Definition of done
- Fresh environment can install dependencies using `requirements.txt`.
- CLI command runs the end-to-end pipeline and writes outputs, traces, cost report, and CRM audit.
- Streamlit dashboard (if implemented) shows persisted real run data.
- Tests cover citation integrity, injection resistance, privacy filtering, cost guard, idempotency, malformed input, retry/resume, and CRM failure handling.
- README explains setup, configuration, live source behavior, commands, limitations, and missing official inputs.
