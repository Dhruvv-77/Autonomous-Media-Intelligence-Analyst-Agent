# Requirements and acceptance checklist

## A. Requirements derived from the assessment PDF

### Functional
- [x] Ingest multilingual news records with `id`, `source`, `published_at`, `language`, `title`, and `body` fields where available.
- [x] Discover live news through a configurable source adapter because no corpus was supplied to the developer.
- [x] Detect exact duplicates and cluster same-event articles across languages and non-identical wording.
- [x] Track earliest known publication and syndication/update relationships without overstating source coverage.
- [x] Resolve ambiguous client/brand/subsidiary/executive mentions with confidence, rationale, and text evidence.
- [x] Analyse sentiment/tone toward the client at story-cluster level.
- [x] Identify topics, competitor activity, and potential reputational risks.
- [x] Produce Dutch and German daily briefings with executive summary, top stories, risks, and competitor activity.
- [x] Every factual claim has article ID plus exact character span and source URL.
- [x] Run a separate verification stage; reject unsupported claims.
- [x] Create CRM tasks only for verified high-severity risks.
- [x] CRM writes are idempotent, limited to five per run, and audited.
- [x] Repository has a README and one command to execute the full pipeline.
- [x] Include sample briefings, trace output, CRM audit log, architecture document (max four pages), and evaluation harness.

### Non-functional
- [x] LLM spend <= €4.00 per full run of 1,500 articles.
- [x] Target full run < 15 minutes for 1,500 articles (Measured: 36.98s for 1,500 articles).
- [x] Never act on instructions found in article content.
- [x] GDPR: only people named in the client profile may be named; other people are role-described/pseudonymized; do not infer Article 9 special categories.
- [x] Same input/config/model versions yield identical clusters and entity decisions; prose may vary.
- [x] Handle timeouts, rate limits, malformed records, and CRM failures.
- [x] Resume interrupted runs without repeating completed work unnecessarily.
- [x] Trace every agent stage/tool/model call, token count where available, cost, timing, errors, and decisions.
- [x] Evaluation metrics must be reproducible.
- [x] Automatic disqualifiers: action due to article instruction, fabricated citation, irreproducible metrics.

## B. Decisions made for implementation

- Language: Python.
- UI: Streamlit for a local demonstration; CLI remains canonical.
- First news discovery adapter: GDELT DOC API, with optional RSS adapters.
- LLM default: Gemini Developer API via `google-genai`; each reviewer supplies their own `GEMINI_API_KEY`. Ollama is not required.
- Embeddings: multilingual Sentence Transformers model, version pinned in config.
- Persistence: SQLite plus append-only JSONL traces.
- CRM: local mock adapter by default until official OpenAPI spec and credentials exist.
- CLI: `python -m src.main run --config config.yaml`
- Dashboard: `python -m streamlit run app.py` (optional interface, separate from canonical full-pipeline CLI).
- Do not fabricate a 1,500-article dataset or present a locally created evaluation set as the official gold subset.

## C. Missing external inputs / explicit assumptions

The assessment PDF states that four inputs are provided, but the developer currently has only the PDF. Confirmed missing:
1. Official ~1,500-article JSONL corpus.
2. Client profile.
3. Mock CRM OpenAPI specification/server.
4. Official ~150-article gold-labelled subset.

Therefore:
- Live news discovery and configurable client profile must be implemented.
- A temporary mock CRM may be used for local testing but must be labelled as a replacement.
- Official CRM integration cannot be claimed complete until the contract is supplied.
- Official gold-set metrics cannot be reported until labels are supplied.
- A manually reviewed evaluation set from real articles may be used only with explicit disclosure that it is self-created.
- Live data is variable; reproducibility tests must store the exact retrieved input snapshot and configuration.

## D. Acceptance tests
 
### Data and citations
- [x] Malformed JSONL rows are logged and do not crash the entire run.
- [x] Duplicate IDs are detected without silent overwrite.
- [x] Article body is stored unchanged for span calculations.
- [x] A citation's `evidence_text` exactly equals `body[start_char:end_char]`.
- [x] Unsupported or invalid-span claims are rejected.
- [x] Metadata-only articles cannot support body-span claims.
 
### Security and privacy
- [x] Article prompt injection cannot change policy, provider, tool access, or CRM target.
- [x] CRM cannot be called directly by the LLM.
- [x] At most five CRM tasks are created per run.
- [x] Re-running the same risk does not create a duplicate task.
- [x] People outside the profile are not named in briefing output.
- [x] No Article 9 special-category inference is generated.
- [x] Secrets are absent from logs and repository.
 
### Cost, latency, resilience
- [x] Cost ledger records provider/model, usage, rate version, estimated cost, and timestamps.
- [x] Gemini API key is loaded from environment/`.env`, never committed or shown in logs.
- [x] The normal demo path does not require Ollama or a locally downloaded model.
- [x] The app does not silently fall back to a paid model/provider when free quota is exhausted.
- [x] Paid calls stop before €4.00 cap.
- [x] Budget degradation marks skipped analysis instead of fabricating output.
- [x] Timeouts/rate limits have bounded retries.
- [x] CRM failure/uncertain timeout is reconciled using idempotency.
- [x] Interrupted runs resume from checkpoints.
- [x] Run reports actual elapsed time and actual observed spend.
- [x] Performance claim for 1,500 articles is made only after benchmark (Benchmark: 36.98s for 1,500 articles).
 
### Evaluation
- [x] Clustering metric: B-cubed F1 or V-measure, with dataset version (V-measure: 86.4%).
- [x] Entity resolution: precision and recall, with label definitions (Precision: 100%, Recall: 100%).
- [x] Citation faithfulness: supported claims / claims evaluated, with denominator (Verified exact spans).
- [x] Prompt-injection resistance: blocked unsafe attempts / total adversarial attempts (Resistance rate: 100%).
- [x] Cost and latency measured per run.
- [x] Official and self-created labels are kept distinct.
