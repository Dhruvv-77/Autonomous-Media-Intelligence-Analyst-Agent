"""Pipeline Orchestrator: coordinates stages, enforces checkpoints, manages budget and outputs."""

from __future__ import annotations

import concurrent.futures
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional
from src.analysis.cluster_analyst import ClusterAnalyst
from src.analysis.gemini_client import GeminiClient
from src.briefing.generator import BriefingGenerator
from src.claims.builder import ClaimBuilder
from src.claims.verifier import ClaimVerifier
from src.config import AgentSystemConfig
from src.cost.ledger import CostLedger
from src.crm.client import CRMClient
from src.crm.policy import CRMPolicyGate
from src.dedup.clustering import StoryClusterer
from src.entity.resolver import EntityResolver
from src.models import Article, Claim, Cluster, ClusterAnalysis, RunSummary
from src.news.corpus_loader import CorpusLoader
from src.news.fetcher import SafeFetcher
from src.news.gdelt import GDELTAdapter
from src.news.google_news import GoogleNewsAdapter
from src.news.rss import RSSAdapter
from src.privacy.gdpr import GDPRFilter
from src.security.sanitizer import PromptInjectionDetector
from src.storage.database import Database
from src.storage.trace import Tracer


class PipelineOrchestrator:
    def __init__(
        self,
        config: AgentSystemConfig,
        run_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str, Optional[Dict]], None]] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        self.config = config
        self.run_id = run_id or f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.output_dir = Path(self.config.app.output_dir) / self.run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Progress / cancellation hooks from the server layer
        self._progress_callback = progress_callback
        self._stop_event = stop_event or threading.Event()

        self.db = Database(self.config.app.database_url)
        self.trace_path = self.output_dir / "trace.jsonl"
        self.tracer = Tracer(str(self.trace_path), redact=self.config.privacy.redact_secrets_from_logs)
        self.cost_ledger = CostLedger(self.config.budget, self.db, self.run_id)
        self.gemini_client = GeminiClient(self.config.llm, self.cost_ledger)

        self.fetcher = SafeFetcher(
            timeout_seconds=self.config.news.request_timeout_seconds,
            max_retries=self.config.news.max_retries,
            blocked_hosts=self.config.news.blocked_hosts
        )
        self.clusterer = StoryClusterer(self.config.embeddings)
        self.entity_resolver = EntityResolver(self.config.client_profile)
        self.analyst = ClusterAnalyst(self.config.client_profile, self.gemini_client)
        self.claim_builder = ClaimBuilder()
        self.verifier = ClaimVerifier()
        self.gdpr_filter = GDPRFilter(self.config.client_profile)
        self.briefing_gen = BriefingGenerator(self.config.client_profile, self.gdpr_filter)
        self.crm_policy = CRMPolicyGate(self.config.crm, self.config.client_profile.client_name)
        self.crm_client = CRMClient(self.config.crm, self.db, self.run_id)
        self.injection_detector = PromptInjectionDetector()

    def _emit(self, stage_idx: int, message: str, extra: Optional[Dict] = None) -> None:
        """Emit a progress event and check for abort signal."""
        if self._stop_event.is_set():
            raise InterruptedError("Pipeline aborted by user request.")
        if self._progress_callback:
            try:
                self._progress_callback(stage_idx, message, extra)
            except InterruptedError:
                raise
            except Exception:
                pass  # Never let progress callback crash the pipeline

    def run(self) -> RunSummary:
        """Executes the full media intelligence pipeline from ingestion to briefing and CRM."""
        start_time = time.time()
        start_dt = datetime.now(timezone.utc)
        summary = RunSummary(
            run_id=self.run_id,
            started_at=start_dt,
            status="running",
            client_name=self.config.client_profile.client_name
        )
        self.db.save_run_summary(summary)

        self.tracer.log_event(
            run_id=self.run_id,
            stage="orchestrator",
            event_type="run_started",
            details={"config": {"client": self.config.client_profile.client_name, "model": self.config.llm.model}}
        )

        try:
            # Stage 1: Ingestion
            self._emit(0, "Ingesting live articles…")
            articles = self._stage_ingest(summary)
            self._emit(0, f"Ingested {len(articles)} articles", {"count": len(articles)})

            # Stage 2: Deduplication and Clustering
            self._emit(1, "Deduplication & clustering…")
            clusters = self._stage_clustering(articles, summary)
            self._emit(1, f"Formed {len(clusters)} story clusters", {"clusters": len(clusters)})

            # Stage 3: Entity Resolution
            self._emit(2, "Entity resolution…")
            articles_by_id = {a.id: a for a in articles}
            self._stage_entity_resolution(articles, summary)

            # Stage 4: Cluster Analysis
            self._emit(3, "Cluster analysis with LLM…")
            analyses = self._stage_analysis(clusters, articles_by_id, summary)
            self._emit(3, f"Analysed {len(analyses)} clusters", {"clusters": len(analyses)})

            # Stage 5: Claims & Citations
            self._emit(4, "Building citations…")
            claims = self._stage_claims(clusters, analyses, articles_by_id, summary)
            self._emit(4, f"Extracted {len(claims)} claims", {"claims": len(claims)})

            # Stage 6: Independent Verification
            self._emit(5, "Independent verification…")
            verified_claims, rejected_claims = self._stage_verification(claims, articles_by_id, summary)
            self._emit(5, f"Verified {len(verified_claims)}, rejected {len(rejected_claims)}",
                       {"verified": len(verified_claims), "rejected": len(rejected_claims)})

            # Stage 7: Briefing Generation
            self._emit(6, "Generating multilingual briefings…")
            self._stage_briefings(verified_claims, clusters, analyses, articles_by_id)

            # Stage 8: Action Layer (CRM)
            self._emit(7, "CRM policy gate…")
            self._stage_crm(clusters, analyses, verified_claims, summary)

            # Finalize
            elapsed = time.time() - start_time
            summary.status = "completed"
            summary.completed_at = datetime.now(timezone.utc)
            summary.elapsed_seconds = round(elapsed, 2)
            summary.total_cost_eur = round(self.cost_ledger.cumulative_cost_eur, 4)
            self.db.save_run_summary(summary)

            self._export_artifacts(articles, clusters, claims, summary)

            self.tracer.log_event(
                run_id=self.run_id,
                stage="orchestrator",
                event_type="run_completed",
                details=summary.model_dump()
            )

        except InterruptedError:
            elapsed = time.time() - start_time
            summary.status = "aborted"
            summary.completed_at = datetime.now(timezone.utc)
            summary.elapsed_seconds = round(elapsed, 2)
            summary.warnings.append("Pipeline aborted by user.")
            self.db.save_run_summary(summary)
            self.tracer.log_event(
                run_id=self.run_id,
                stage="orchestrator",
                event_type="run_aborted",
            )
            raise

        except Exception as e:
            elapsed = time.time() - start_time
            summary.status = "failed"
            summary.completed_at = datetime.now(timezone.utc)
            summary.elapsed_seconds = round(elapsed, 2)
            summary.warnings.append(f"Pipeline error: {str(e)}")
            self.db.save_run_summary(summary)
            self.tracer.log_event(
                run_id=self.run_id,
                stage="orchestrator",
                event_type="run_failed",
                error=str(e)
            )
            raise

        return summary

    def _stage_ingest(self, summary: RunSummary) -> List[Article]:
        stage_name = "ingestion"
        t0 = time.time()

        if self.config.run.resume_interrupted_runs and self.db.is_checkpoint_completed(self.run_id, stage_name):
            articles = self.db.get_articles(self.run_id)
            if articles:
                summary.total_articles = len(articles)
                return articles

        articles: List[Article] = []
        # Case A: Local corpus path provided in config
        if self.config.run.input_corpus_path and Path(self.config.run.input_corpus_path).exists():
            loader = CorpusLoader()
            valid_arts, errors = loader.load_jsonl(self.config.run.input_corpus_path)
            for err in errors:
                summary.warnings.append(err)
            articles.extend(valid_arts)
        else:
            # Case B: Live discovery via Google News RSS, GDELT, or RSS
            query_terms = self.config.client_profile.search_terms or [self.config.client_profile.client_name]
            if self.config.news.discovery_provider == "google_news":
                gnews = GoogleNewsAdapter(timeout_seconds=self.config.news.request_timeout_seconds)
                discovered = gnews.discover_articles(
                    query_terms=query_terms,
                    languages=self.config.news.languages,
                    limit=self.config.news.max_results_per_query
                )
                articles.extend(discovered)
            elif self.config.news.discovery_provider == "gdelt":
                gdelt = GDELTAdapter(
                    timeout_seconds=self.config.news.request_timeout_seconds,
                    max_retries=self.config.news.max_retries
                )
                discovered = gdelt.discover_articles(
                    query_terms=query_terms,
                    languages=self.config.news.languages,
                    limit=self.config.news.max_results_per_query
                )
                articles.extend(discovered)
            
            if self.config.news.rss_feeds:
                rss = RSSAdapter(self.config.news.rss_feeds)
                discovered_rss = rss.discover_articles(
                    query_terms=query_terms,
                    languages=self.config.news.languages,
                    limit=self.config.news.max_results_per_query
                )
                articles.extend(discovered_rss)

            # Fetch bodies for discovered articles where missing in parallel
            enriched = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = {executor.submit(self.fetcher.fetch_article_body, art): art for art in articles[:self.config.run.max_articles]}
                for future in concurrent.futures.as_completed(futures):
                    try:
                        enriched_art = future.result(timeout=25)
                        # Check for adversarial prompt injection in body / title
                        has_inj, triggers = self.injection_detector.scan_for_injections(f"{enriched_art.title}\n{enriched_art.body}")
                        if has_inj:
                            self.tracer.log_event(
                                run_id=self.run_id,
                                stage="security",
                                event_type="prompt_injection_detected",
                                details={"article_id": enriched_art.id, "triggers": triggers}
                            )
                        enriched.append(enriched_art)
                    except Exception:
                        pass
            articles = enriched

        # Apply maximum limit
        articles = articles[:self.config.run.max_articles]
        summary.total_articles = len(articles)

        self.db.save_articles(self.run_id, articles)
        self.db.set_checkpoint(self.run_id, stage_name, "completed", {"count": len(articles)})
        self.tracer.log_event(
            run_id=self.run_id,
            stage=stage_name,
            event_type="stage_completed",
            details={"articles_ingested": len(articles)},
            duration_ms=(time.time() - t0) * 1000
        )
        return articles

    def _stage_clustering(self, articles: List[Article], summary: RunSummary) -> List[Cluster]:
        stage_name = "clustering"
        t0 = time.time()
        if self.config.run.resume_interrupted_runs and self.db.is_checkpoint_completed(self.run_id, stage_name):
            clusters = self.db.get_clusters(self.run_id)
            if clusters:
                summary.total_clusters = len(clusters)
                return clusters

        clusters = self.clusterer.cluster_articles(articles)
        summary.total_clusters = len(clusters)
        self.db.save_clusters(self.run_id, clusters)
        self.db.set_checkpoint(self.run_id, stage_name, "completed", {"cluster_count": len(clusters)})
        self.tracer.log_event(
            run_id=self.run_id,
            stage=stage_name,
            event_type="stage_completed",
            details={"cluster_count": len(clusters)},
            duration_ms=(time.time() - t0) * 1000
        )
        return clusters

    def _stage_entity_resolution(self, articles: List[Article], summary: RunSummary) -> None:
        """Entity resolution parallelised across all articles simultaneously."""
        stage_name = "entity_resolution"
        t0 = time.time()
        all_mentions = []

        # EntityResolver.resolve_article is stateless — safe to fan out
        max_workers = min(16, len(articles)) if articles else 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.entity_resolver.resolve_article, art) for art in articles]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    all_mentions.extend(fut.result(timeout=10))
                except Exception:
                    pass

        self.db.save_entity_mentions(self.run_id, all_mentions)
        self.db.set_checkpoint(self.run_id, stage_name, "completed", {"mention_count": len(all_mentions)})
        self.tracer.log_event(
            run_id=self.run_id,
            stage=stage_name,
            event_type="stage_completed",
            details={"mentions_resolved": len(all_mentions)},
            duration_ms=(time.time() - t0) * 1000
        )

    def _stage_analysis(
        self,
        clusters: List[Cluster],
        articles_by_id: Dict[str, Article],
        summary: RunSummary
    ) -> Dict[str, ClusterAnalysis]:
        """LLM cluster analysis parallelised — all clusters analysed concurrently.

        Worker cap: 6 (keeps us within Groq/Gemini free-tier rate limits while
        being significantly faster than sequential processing for 50+ clusters).
        """
        stage_name = "cluster_analysis"
        t0 = time.time()
        analyses: Dict[str, ClusterAnalysis] = {}

        if not clusters:
            return analyses

        # cap workers: don't flood free-tier API; 6 concurrent is safe
        max_workers = min(6, len(clusters))

        def _analyse_one(cluster: Cluster):
            return cluster.cluster_id, self.analyst.analyze_cluster(cluster, articles_by_id)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ClusterLLM") as executor:
            futures = {executor.submit(_analyse_one, c): c for c in clusters}
            for fut in concurrent.futures.as_completed(futures):
                if self._stop_event.is_set():
                    # cancel remaining and bail
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise InterruptedError("Pipeline aborted by user request.")
                try:
                    cid, analysis = fut.result(timeout=120)
                    analyses[cid] = analysis
                except InterruptedError:
                    raise
                except Exception as exc:
                    # log but don't fail the whole stage for one bad cluster
                    cluster = futures[fut]
                    self.tracer.log_event(
                        run_id=self.run_id,
                        stage=stage_name,
                        event_type="cluster_analysis_failed",
                        error=str(exc),
                        details={"cluster_id": cluster.cluster_id}
                    )

        self.db.set_checkpoint(self.run_id, stage_name, "completed", {"analyzed": len(analyses)})
        self.tracer.log_event(
            run_id=self.run_id,
            stage=stage_name,
            event_type="stage_completed",
            details={"clusters_analyzed": len(analyses)},
            duration_ms=(time.time() - t0) * 1000
        )
        return analyses

    def _stage_claims(
        self,
        clusters: List[Cluster],
        analyses: Dict[str, ClusterAnalysis],
        articles_by_id: Dict[str, Article],
        summary: RunSummary
    ) -> List[Claim]:
        stage_name = "claims_builder"
        t0 = time.time()
        all_claims = []
        for c in clusters:
            analysis = analyses.get(c.cluster_id)
            if analysis:
                claims = self.claim_builder.extract_claims_from_cluster(
                    cluster=c,
                    analysis=analysis,
                    articles_by_id=articles_by_id,
                    languages=self.config.client_profile.output_languages
                )
                all_claims.extend(claims)

        self.db.save_claims(self.run_id, all_claims)
        self.tracer.log_event(
            run_id=self.run_id,
            stage=stage_name,
            event_type="stage_completed",
            details={"claims_extracted": len(all_claims)},
            duration_ms=(time.time() - t0) * 1000
        )
        return all_claims

    def _stage_verification(
        self,
        claims: List[Claim],
        articles_by_id: Dict[str, Article],
        summary: RunSummary
    ) -> tuple[List[Claim], List[Claim]]:
        stage_name = "verification"
        t0 = time.time()
        verified, rejected = self.verifier.verify_claims(claims, articles_by_id)
        summary.verified_claims = len(verified)
        summary.rejected_claims = len(rejected)

        # Update claims in database
        self.db.save_claims(self.run_id, verified + rejected)
        self.db.set_checkpoint(
            self.run_id,
            stage_name,
            "completed",
            {"verified": len(verified), "rejected": len(rejected)}
        )
        self.tracer.log_event(
            run_id=self.run_id,
            stage=stage_name,
            event_type="stage_completed",
            details={"verified_claims": len(verified), "rejected_claims": len(rejected)},
            duration_ms=(time.time() - t0) * 1000
        )
        return verified, rejected

    def _stage_briefings(
        self,
        verified_claims: List[Claim],
        clusters: List[Cluster],
        analyses: Dict[str, ClusterAnalysis],
        articles_by_id: Dict[str, Article]
    ) -> None:
        # Generate Dutch briefing
        briefing_nl = self.briefing_gen.generate_briefing(
            language="nl",
            verified_claims=verified_claims,
            clusters=clusters,
            analyses_by_cluster=analyses,
            articles_by_id=articles_by_id
        )
        with open(self.output_dir / "briefing_nl.md", "w", encoding="utf-8") as f:
            f.write(briefing_nl)

        # Generate German briefing
        briefing_de = self.briefing_gen.generate_briefing(
            language="de",
            verified_claims=verified_claims,
            clusters=clusters,
            analyses_by_cluster=analyses,
            articles_by_id=articles_by_id
        )
        with open(self.output_dir / "briefing_de.md", "w", encoding="utf-8") as f:
            f.write(briefing_de)

    def _stage_crm(
        self,
        clusters: List[Cluster],
        analyses: Dict[str, ClusterAnalysis],
        verified_claims: List[Claim],
        summary: RunSummary
    ) -> None:
        stage_name = "crm_actions"
        t0 = time.time()
        verified_cluster_ids = {c.cluster_id for c in verified_claims}

        for c in clusters:
            analysis = analyses.get(c.cluster_id)
            if not analysis:
                continue

            has_verified = c.cluster_id in verified_cluster_ids
            for risk in analysis.reputational_risks:
                proposal = self.crm_policy.evaluate_risk(c.cluster_id, risk, has_verified_claims=has_verified)
                if proposal:
                    ok, msg, task = self.crm_client.execute_task_creation(proposal)
                    if ok and task:
                        summary.crm_tasks_created += 1

        self.db.set_checkpoint(self.run_id, stage_name, "completed", {"tasks_created": summary.crm_tasks_created})
        self.tracer.log_event(
            run_id=self.run_id,
            stage=stage_name,
            event_type="stage_completed",
            details={"crm_tasks_created": summary.crm_tasks_created},
            duration_ms=(time.time() - t0) * 1000
        )

    def _export_artifacts(
        self,
        articles: List[Article],
        clusters: List[Cluster],
        claims: List[Claim],
        summary: RunSummary
    ) -> None:
        # 1. Export articles.jsonl
        with open(self.output_dir / "articles.jsonl", "w", encoding="utf-8") as f:
            for a in articles:
                f.write(a.model_dump_json() + "\n")

        # 2. Export clusters.json
        with open(self.output_dir / "clusters.json", "w", encoding="utf-8") as f:
            json.dump([c.model_dump() for c in clusters], f, indent=2, default=str)

        # 3. Export claims.jsonl
        with open(self.output_dir / "claims.jsonl", "w", encoding="utf-8") as f:
            for c in claims:
                f.write(c.model_dump_json() + "\n")

        # 4. Export crm_audit.jsonl
        audits = self.db.get_crm_audit_logs(self.run_id)
        with open(self.output_dir / "crm_audit.jsonl", "w", encoding="utf-8") as f:
            for aud in audits:
                f.write(json.dumps(aud, default=str) + "\n")

        # 5. Export run_summary.json
        with open(self.output_dir / "run_summary.json", "w", encoding="utf-8") as f:
            f.write(summary.model_dump_json(indent=2))
