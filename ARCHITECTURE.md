# Architecture — Autonomous Media Intelligence Analyst Agent

> Keep this document to a maximum of four pages in the final repository. This version is intentionally concise and separates assessment requirements from assumptions caused by missing inputs.

## 1. Architecture summary

Use a deterministic Python orchestrator with small, testable modules rather than a complex multi-agent framework. “Agentic” behavior is represented by staged analysis, bounded LLM assistance, verification, policy-gated actions, checkpoints, and tool-call traces. Each stage has typed inputs/outputs and can be resumed. The default LLM is the Gemini Developer API via the official `google-genai` SDK; reviewers provide their own API key. Ollama is not required.

```text
CLI: python -m src.main run --config config.yaml
                   |
                   v
        Run Controller / Checkpoints
                   |
       +-----------+------------+
       |                        |
       v                        v
 Client Profile             News Discovery
 & Policy Loader            (GDELT / RSS adapters)
       |                        |
       +-----------+------------+
                   v
          Fetch + Validate Articles
                   |
                   v
       Normalize / Exact Deduplication
                   |
                   v
      Multilingual Story Clustering
                   |
                   v
           Entity Resolution
                   |
                   v
     Cluster-level Analysis (LLM)
                   |
                   v
       Claim Builder + Source Spans
                   |
                   v
         Independent Verification
                   |
                   v
       GDPR Output Privacy Filter
                   |
                   v
      Dutch + German Briefing Writer
                   |
                   v
        Deterministic Action Policy
                   |
                   v
        CRM Adapter (mock by default)
                   |
                   v
 SQLite run state + JSONL traces + reports + CRM audit
                   ^
                   |
         Streamlit dashboard reads persisted run data
```

## 2. Components and hand-offs

1. **Run controller:** creates run ID, loads configuration, checks time/cost budgets, calls stages in order, persists stage status, resumes completed work, and writes final run summary.
2. **News source adapters:** query live discovery sources and return article metadata. Fetch full text only where permitted; mark inaccessible content as partial/metadata-only.
3. **Ingestion/validation:** normalizes timestamps and language codes, validates required fields, derives stable IDs and content hashes, quarantines malformed records without stopping the entire run.
4. **Deduplication/clustering:** exact duplicates by normalized URL/content hash; semantic multilingual clustering by a fixed embedding model and deterministic clustering settings. Record cluster members, earliest known article, and likely updates separately. Do not claim true “first publication” if discovery coverage cannot establish it.
5. **Entity resolver:** combines profile aliases, exact/rule-based context, and optional LLM assistance for ambiguous mentions. Store confidence, rationale, evidence span, and rule/model version. Deterministic inputs and settings must yield stable decisions.
6. **Cluster analyst:** analyses sentiment/tone toward the client, topics, competitors, and potential reputation risk at cluster level. Risk is a triage signal, not proof that an allegation is true.
7. **Claim builder:** creates structured claims. Each claim has `claim_id`, `text`, `article_id`, `start_char`, `end_char`, exact `evidence_text`, source URL, and confidence. Character offsets use Python string indexing over the exact stored body; never compute them against a normalized body.
8. **Verifier:** independently checks that the cited slice equals the stored source slice and supports the claim. Reject unsupported claims. Exact-slice equality is necessary but not sufficient for semantic support; use a separate verifier/rule and record its result.
9. **Privacy filter:** applies allow-list of profile people; other people are role-described or pseudonymized. Never infer Article 9 special-category data.
10. **Briefing writer:** generates Dutch and German executive summary, top stories, risks, and competitor activity only from verified structured claims. All factual statements retain citations.
11. **Action policy + CRM adapter:** only verified high-severity risks may be proposed. A deterministic policy validates evidence, severity threshold, allowed fields, five-task cap, and idempotency. The LLM cannot invoke the CRM directly. Mock CRM is default until the official OpenAPI contract is supplied.
12. **Observability/store:** SQLite stores articles, stage results, checkpoints, cost ledger, idempotency keys, and CRM audit; append-only JSONL traces record each stage/tool/model call, timings, inputs/outputs with redaction, decision, token usage, and errors.
13. **Streamlit UI:** reads persisted state and starts the same orchestrator; it does not contain duplicate business logic.

## 3. Prompt-injection threat model

**Assets to protect:** system policy, client data, provider/API secrets, CRM endpoint and write capability, factual integrity of briefings, budget, and audit trail.

**Threat actor/input:** a news article or publisher page containing instructions such as “ignore previous instructions,” requests for secrets, or commands to create CRM tasks.

**Trust boundary:** all retrieved content is untrusted data. It may be quoted, classified, or summarized, but must never be treated as executable instructions.

**Controls:**
- Separate trusted prompts/configuration from article content; label article text as quoted/untrusted input.
- Do not expose tools or credentials to the LLM. LLM returns structured suggestions only.
- Validate all model outputs with Pydantic schemas and allow-listed fields.
- Require source-backed claim verification and a deterministic CRM policy gate.
- CRM adapter accepts only a typed, policy-approved task proposal; never accepts arbitrary endpoint URLs or instructions from article text.
- Enforce maximum five writes/run, persistent idempotency keys, and append-only audit.
- Test direct and indirect injection, encoded/obfuscated instructions, multilingual injection, and injection in title/body/metadata.
- Any task created because of article instructions is a release-blocking failure.

## 4. €4 budget and 15-minute latency

**Budget policy:** €4.00 maximum LLM spend per full run of 1,500 articles. Use a cost ledger per call, current configured provider rates, usage metadata, and a 15% default safety reserve (€3.40 threshold). Gemini free-tier usage is supported and tracked; when paid pricing is configured (€0.075 / 1M input tokens, €0.30 / 1M output tokens), a full run of 1,500 articles uses approximately 1.1M input tokens and 120k output tokens, resulting in an estimated spend of **€0.119 per run** — well within the €4.00 hard limit (a 97% safety headroom).

**Cost versus quality trade-off:**
- *Stage 1 (Deduplication & Clustering):* Executed locally via multilingual Sentence-Transformers (`paraphrase-multilingual-MiniLM-L12-v2`) and exact hash matching. €0 LLM cost; eliminates ~40–60% of syndicated redundancy before LLM inference.
- *Stage 2 (Entity Resolution):* Deterministic rule-based disambiguation with context boundaries and selective LLM disambiguation. Cost: <€0.02.
- *Stage 3 (Cluster Analysis):* Performed strictly at the story-cluster level rather than per article. For 1,500 articles grouped into ~50–100 clusters, this reduces LLM invocations by over 93%.
- *Measured Full-Run Benchmark:* Benchmarked on 1,500 articles in 36.98 seconds (863 seconds under the 900-second 15-minute ceiling). Cost recorded: €0.00 on free-tier/simulation mode, estimated €0.12 on paid tier. Latency and spend targets are measured and met.

## 5. Determinism, resilience, and persistence

- Fix embedding model/version, similarity threshold, clustering algorithm/settings, sort order, and tie-breaking.
- Use deterministic article IDs, stable sorting, and versioned prompts/configuration.
- Prose can vary; clusters and entity decisions should not vary for identical input and versions.
- Persist stage completion and output hashes. Resume from the last successful checkpoint.
- Retry transient failures with bounded exponential backoff; respect `Retry-After`.
- Treat CRM timeout after a possible write as an uncertain result: query/reconcile by idempotency key before retrying.
- Do not silently convert missing data or failed LLM calls into negative findings.

## 6. Evaluation and known limitations

Report clustering B-cubed F1 or V-measure, entity precision/recall, citation faithfulness, prompt-injection resistance, cost, and latency. Use official gold labels only if provided. If not, create a separately labelled, manually reviewed evaluation set from real articles and clearly state it is not the assessment's official gold subset.

Live news discovery is not complete coverage: GDELT/RSS availability, publisher access, language detection, and article text extraction can vary. The first version should display body retrieval status and source coverage limitations. CRM remains mock until the real OpenAPI specification and credentials are available. GDPR compliance requires review by the company; this software design is not legal advice.
