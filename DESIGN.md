# Product Design — Autonomous Media Intelligence Analyst Agent

## 1. Purpose

Build a practical, auditable system that discovers relevant real-world news, groups duplicate and related stories, resolves client entities, analyses reputational implications, and produces citation-backed daily briefings in Dutch and German. The system may create a CRM follow-up task only when a verified high-severity risk passes a deterministic safety policy.

This design is based on the assessment PDF dated 23 October 2026 and the implementation decisions agreed during planning. The assessment specifies an expected input corpus of about 1,500 articles, a client profile, a mock CRM API/OpenAPI specification, and about 150 gold-labelled articles. These inputs have not been supplied to the developer beyond the PDF. The implementation must therefore support live news ingestion and configurable client data, while documenting that official gold-set evaluation and official CRM integration remain blocked until the missing materials or an approved replacement contract are available.

## 2. Product goals

1. Run the full pipeline from one CLI command.
2. Discover and process real news from configured public sources; do not fabricate a 1,500-article corpus.
3. Provide a usable web interface for a stakeholder demonstration.
4. Generate Dutch and German briefings with every factual claim linked to an article ID and exact character span.
5. Keep LLM spend below €4.00 per full run and target completion in under 15 minutes for 1,500 articles.
6. Resist prompt injection in article text, enforce GDPR constraints, and prevent duplicate or excessive CRM writes.
7. Persist progress, traces, costs, decisions, outputs, and CRM audit records so a run can be inspected and resumed.
8. Report limitations honestly. Do not claim performance metrics that have not been measured.

## 3. Non-goals for the first version

- A continuously running real-time news terminal or streaming service.
- A guarantee that every publisher's full article text can be fetched; paywalls, robots restrictions, and publisher controls must be respected.
- An automatic truth/fake-news oracle. The system assesses evidence and reputational risk; it must not label an allegation as true solely because an article says so.
- Production CRM integration without the company's real OpenAPI contract and credentials.
- Claiming official gold-label scores without the official labelled subset.
- Unrestricted autonomous actions, arbitrary browser actions, or letting an LLM directly call CRM write endpoints.

## 4. Target users and workflow

### Primary user
An analyst or company stakeholder who wants a daily, multilingual overview of news about a client, its brands, subsidiaries, competitors, and in-scope executives.

### Main workflow
1. Configure the client profile and permitted sources.
2. Start a run from CLI; optionally use the Streamlit dashboard to launch and inspect runs.
3. Discover recent articles for the configured keywords/languages.
4. Fetch article text where permitted and store metadata/body with retrieval status.
5. Validate, normalize, deduplicate, and cluster articles.
6. Resolve entity mentions and classify each story cluster.
7. Produce claims with exact evidence spans.
8. Run a separate verification step; discard unsupported claims.
9. Generate Dutch and German briefings from verified claims only.
10. Evaluate high-severity risks against a deterministic CRM action policy.
11. Write CRM tasks only through a controlled adapter; persist an audit record.
12. Display/export reports, traces, cost, latency, warnings, and CRM audit log.

## 5. Data sources and acquisition

### Primary discovery adapter
Implement a GDELT DOC API adapter as the initial live-news discovery source, with query construction driven by the client profile. Treat this as a configurable adapter, not a guarantee of complete coverage.

### Optional adapters
Support RSS feeds and additional permitted news APIs through the same `NewsSource` interface. Do not add scraping workarounds that bypass access controls. Follow publisher terms, robots policies, rate limits, and applicable law. Do not attempt to bypass paywalls.

### Article record
Store at minimum:
- `id`: stable internal identifier (source identifier when available, otherwise deterministic hash of canonical URL + published timestamp).
- `source`
- `published_at` (UTC ISO 8601 where known)
- `language` (BCP-47 or normalized language code)
- `title`
- `body` (exact retrieved text, if available)
- `url`
- `retrieved_at`
- `body_status` (`full`, `partial`, `metadata_only`, `blocked`, `failed`)
- `content_hash`
- `source_query`
- `retrieval_error` (nullable, sanitized)

Never silently fabricate article bodies. A metadata-only record must be clearly marked and excluded from span-based claims that require body text.

## 6. User interface

### First version
Use Streamlit for a local stakeholder dashboard. The CLI remains the canonical automation entry point.

Dashboard pages/sections:
- Run controls: run date/window, client profile, source/language filters.
- Run status: stage, progress, warnings, elapsed time, current estimated LLM spend.
- Metrics: discovered articles, successfully fetched bodies, clusters, verified claims, high-severity risks, CRM tasks.
- Briefings: Dutch and German, with citations linking to source URL and displaying exact cited text.
- Story explorer: cluster members, earliest known publication, updates/syndication, entity confidence and justification.
- Audit: trace events, LLM usage/cost, retries, checkpoint/resume status, CRM write attempts and outcomes.
- Export: Markdown/JSON/CSV as appropriate.

The dashboard must show live values from persisted run data, not illustrative hard-coded counts. Do not expose secrets or unnecessary personal data.

## 7. LLM strategy and budget

### Default
Use the Google Gemini Developer API through the official `google-genai` Python SDK. Each developer/reviewer obtains their own API key from Google AI Studio and supplies it through the `GEMINI_API_KEY` environment variable or local `.env` file. No Ollama installation or model download should be required for the normal demo path.

Use a configurable model name. Check the currently available models and free-tier eligibility when setting up the project; do not assume that a particular model or quota remains free forever.

### Optional provider
Keep a small provider interface so an approved alternative API can be added later. Ollama may be retained only as an optional developer fallback if useful, but it must not be the default or a required dependency. Never silently switch to a paid provider or model.

External API use must be approved for the company's data classification. The Gemini free tier's current terms may permit submitted content to be used to improve Google products; do not send confidential or sensitive company data without company approval.

### Cost policy
- Hard ceiling: €4.00 estimated/billed LLM spend per full run of 1,500 articles.
- Track each model call, provider, model, input/output token counts when available, rate source/version, estimated cost, and timestamp.
- Treat API usage as €0 provider-billed only while the active account/model/usage genuinely qualifies for free-tier treatment; still track quota, rate limits, and usage.
- Reserve a configurable safety margin (default 15%) and stop new paid calls before the ceiling is crossed.
- Prefer rules, cached outputs, deterministic code, and embeddings for suitable tasks.
- When budget is nearly exhausted, degrade gracefully: skip optional LLM enrichment, preserve deterministic results, mark affected fields as `not_assessed_due_to_budget`, and never fabricate an answer.
- Do not claim €4 compliance until measured usage/cost is reported for a representative full run.

## 8. Security and privacy

- Treat every title, body, metadata field, URL, and retrieved page as untrusted data.
- Article text must never modify system instructions, tool permissions, policy, provider configuration, or CRM destinations.
- No LLM has direct CRM write credentials. Only the deterministic action policy and CRM adapter may create tasks.
- Every claim must pass a source-span verification step before inclusion in a briefing.
- Only people explicitly present in the configured client profile may be named in outputs. Other natural persons must be referred to by role or pseudonymized.
- Do not infer or classify GDPR Article 9 special-category data.
- Minimize stored personal data; sanitize logs; do not log API keys or full sensitive payloads.
- Keep secrets in environment variables, never in source control.
- CRM writes are disabled by default unless an explicitly configured mock or approved real endpoint is selected.
- Enforce at most five CRM tasks per run and deterministic idempotency keys.
- Use safe HTTP timeouts, bounded retries, request limits, and URL validation to reduce SSRF risk. Only fetch HTTP(S) URLs from approved discovery/source results; block localhost, private IP ranges, and unsafe redirects.
- A prompt-injection test must confirm that article instructions cannot cause tool calls or task creation.

## 9. Failure and recovery behavior

- Malformed article: record a validation error and continue.
- Missing body: retain metadata but do not make unsupported claims.
- Timeout/rate limit: bounded exponential backoff with jitter; honor `Retry-After` when provided.
- Provider unavailable: use configured fallback only if explicitly enabled; otherwise mark LLM-dependent stage degraded.
- Cost limit reached: stop paid calls and continue only with deterministic work that remains valid.
- CRM failure: record attempt and error; retry only under bounded policy; use idempotency key so a retry cannot duplicate the task.
- Interrupted run: resume from persisted stage checkpoints; completed deterministic work is not repeated unnecessarily.
- Citation verification failure: reject the claim; never silently remove its citation and keep the claim.
- Missing official corpus, gold labels, client profile, or CRM OpenAPI spec: clearly state this limitation in README and run report.

## 10. Acceptance criteria

The product is ready for an initial stakeholder demonstration when:
- One CLI command runs a complete end-to-end pipeline on currently available live results.
- The dashboard displays actual run outputs and execution metrics.
- Each published factual claim has an article ID, URL, exact character offsets, and quoted evidence span.
- Unsupported claims are rejected by a separate verifier.
- Article prompt injections cannot trigger actions.
- GDPR name/pseudonymization rules are tested.
- CRM mock tasks obey the five-per-run cap and idempotency.
- Run state, errors, model usage, cost, and decisions are persisted.
- Tests cover malformed records, timeouts, rate limits, restart/resume, citation failures, and simulated CRM failures.
- The README documents setup, source limitations, configuration, single-command execution, and known gaps.
- Full 1,500-article performance, €4 cost compliance, and official gold-set metrics are described as verified only after actual measurements.
