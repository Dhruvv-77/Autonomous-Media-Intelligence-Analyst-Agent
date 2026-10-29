# Implementation Plan — Five Working Days

## Execution principles

1. Build a small, working end-to-end vertical slice before adding advanced features.
2. Use real live news as the primary input; do not create a fake 1,500-article corpus.
3. Use synthetic/adversarial examples only for targeted tests such as prompt injection and malformed data.
4. Keep the official-data, self-collected live-data, and self-labelled evaluation paths explicitly separate.
5. The CLI is the canonical pipeline entry point. Streamlit is a UI over the same application services.
6. No stage may claim success if its required evidence is missing.
7. If the deadline is fixed, prioritize safety, citations, reproducibility, and documentation over decorative UI.

## Day 1 — Repository, ingestion, live source, and run command

### Tasks
- Create the Python package and `src/main.py`.
- Add typed configuration and `.env.example`.
- Implement client profile schema with configurable names, aliases, competitors, executives/roles, included/excluded topics, languages, and query terms.
- Implement GDELT discovery adapter and optional RSS adapter interface.
- Implement safe article retrieval: timeouts, URL validation, rate limits, retrieval status, and body extraction where permitted.
- Normalize article metadata; preserve exact body text.
- Add SQLite schema for runs, articles, stage checkpoints, cost events, and trace events.
- Create stable article IDs/content hashes and malformed-record handling.
- Add the single-command CLI.
- Ask the company/assessor for official client profile, CRM OpenAPI contract, and evaluation data in parallel.

### Exit criteria
- One command starts a run and fetches real results for a configured client profile.
- Articles include source URL and body retrieval status.
- Failures are logged; no fake successful result is shown.
- Unit tests cover malformed records, duplicate IDs, and exact body preservation.

## Day 2 — Deduplication, multilingual clustering, and entities

### Tasks
- Exact duplicate detection by canonical URL and content hash.
- Add a pinned multilingual embedding model and deterministic clustering configuration.
- Track cluster members, earliest known retrieved publication, likely syndicated copies, and likely updates.
- Add entity aliases and context rules.
- Add LLM-assisted disambiguation only for unresolved cases; validate structured outputs.
- Record entity confidence, rationale, evidence span, model/prompt version, and deterministic tie-breaking.
- Cache embeddings and LLM decisions using content/config/model hashes.

### Exit criteria
- Same stored input and versions produce identical cluster assignments and entity decisions.
- Tests cover common-word brand names, same-name subsidiaries, former executives, and cross-language near-duplicates.
- Clustering thresholds are configurable and documented; no metric is claimed without labels.

## Day 3 — Cluster analysis, claim schema, verification, and briefings

### Tasks
- Analyze sentiment/tone toward the client at cluster level.
- Extract topics, competitors, and potential reputational risks.
- Define a typed claim schema with article ID, URL, start/end character offsets, exact evidence text, confidence, and verification state.
- Verify source-span equality and semantic support in a separate step.
- Reject claims with missing or invalid citations.
- Apply GDPR privacy filter before output.
- Generate Dutch and German briefing sections from verified claims only.
- Provide citation links and evidence text in Markdown and dashboard output.

### Exit criteria
- A briefing can be produced from real retrieved articles.
- Every factual claim is linked to an exact source span.
- Invalid or unsupported claims are rejected.
- People outside the configured client profile are not named.
- Outputs distinguish allegations/risks from established facts.

## Day 4 — Budget, resilience, prompt injection, CRM policy, dashboard

### Tasks
- Implement the Gemini API adapter using `google-genai`; load each user's `GEMINI_API_KEY` from environment/`.env`. Make model selection configurable and add explicit quota/rate-limit handling. Do not require Ollama. Do not silently switch to paid usage.
- Track token usage and estimated cost; add €4 hard cap with reserve.
- Add degradation mode near budget ceiling.
- Add bounded retries/backoff for provider, source, and CRM failures.
- Add checkpoints and restart/resume behavior.
- Implement deterministic CRM action policy: verified high severity, max five tasks/run, idempotency, audit.
- Implement mock CRM adapter; do not pretend it is the missing official API.
- Build Streamlit dashboard that reads persisted state and launches the same orchestrator.
- Add direct/indirect and multilingual prompt-injection tests.

### Exit criteria
- An article's embedded instructions cannot trigger CRM actions.
- CRM writes are idempotent, capped, and audited.
- Simulated ~10% CRM failures do not create duplicates.
- Cost stops paid calls before the hard limit.
- Dashboard displays actual run data, not hard-coded metrics.

## Day 5 — Evaluation, benchmarking, documentation, and defence

### Tasks
- Run tests on stored real-news snapshots.
- Benchmark the largest available realistic run; target 1,500 articles and <15 minutes, but report actual result honestly.
- Measure observed model cost; report local inference separately from provider-billed cost.
- Create a manually reviewed evaluation set only if time permits; label it as self-created and distinct from the official gold subset.
- Implement evaluation harness: clustering, entity precision/recall, citation faithfulness, injection resistance, cost, latency.
- Export sample Dutch/German briefings, JSONL trace, and CRM audit log.
- Finish README, architecture document (max four pages), limitations, setup, configuration, and command documentation.
- Rehearse 45-minute defence with unseen adversarial articles.

### Exit criteria
- Fresh clone setup and documented command are reproducible.
- Tests and evaluation can be rerun.
- No unsupported claims about official data or metrics.
- Known limitations and missing external dependencies are explicit.

## Prioritization if time runs out

**P0 — Must have:** live ingestion, one-command run, exact citations, verification, prompt-injection safety, GDPR filter, €4 guard, five-task cap, idempotency, trace/audit, honest README.

**P1 — Important:** deterministic multilingual clustering, entity resolution, checkpoints/resume, evaluation harness, Dutch/German briefings.

**P2 — Only after P0/P1:** polished dashboard, extra news adapters, sophisticated story-update detection, optional hosted LLM fallback.

## Risks and mitigation

- **No client profile:** provide a schema and example with clearly marked placeholders; do not silently choose the internship company or names.
- **No official CRM contract:** mock adapter only; integration remains pending.
- **No official gold labels:** self-created reviewed labels may support provisional metrics, but never call them official scores.
- **News full text unavailable:** record metadata-only status and exclude unsupported body citations.
- **Ollama too slow/weak:** benchmark small multilingual models; use embeddings/rules to reduce LLM calls; optionally test an approved free-tier API.
- **Budget estimate inaccurate:** report provider usage metadata and configured rates; stop early with reserve.
- **15-minute target missed:** profile stage timings and optimize; report the measured result instead of claiming compliance.
