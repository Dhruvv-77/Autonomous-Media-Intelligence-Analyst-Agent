"""SQLite persistence for runs, articles, clusters, claims, CRM audits, and checkpoints."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.models import Article, Claim, Cluster, CRMTask, EntityMention, RunSummary


class Database:
    def __init__(self, db_path: str = "outputs/agent.db") -> None:
        clean_path = db_path.replace("sqlite:///", "") if db_path.startswith("sqlite:///") else db_path
        self.db_path = Path(clean_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    summary_json TEXT
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT,
                    run_id TEXT,
                    source TEXT,
                    url TEXT,
                    title TEXT,
                    body TEXT,
                    language TEXT,
                    published_at TEXT,
                    retrieved_at TEXT,
                    body_status TEXT,
                    content_hash TEXT,
                    PRIMARY KEY (id, run_id)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS clusters (
                    cluster_id TEXT,
                    run_id TEXT,
                    canonical_title TEXT,
                    earliest_published_at TEXT,
                    first_source TEXT,
                    article_ids_json TEXT,
                    is_update INTEGER,
                    update_of TEXT,
                    PRIMARY KEY (cluster_id, run_id)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS entity_mentions (
                    mention_id TEXT,
                    run_id TEXT,
                    article_id TEXT,
                    entity_name TEXT,
                    entity_type TEXT,
                    is_client INTEGER,
                    confidence REAL,
                    justification TEXT,
                    evidence_text TEXT,
                    start_char INTEGER,
                    end_char INTEGER,
                    PRIMARY KEY (mention_id, run_id)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT,
                    run_id TEXT,
                    cluster_id TEXT,
                    language TEXT,
                    section TEXT,
                    claim_text TEXT,
                    article_id TEXT,
                    source_url TEXT,
                    start_char INTEGER,
                    end_char INTEGER,
                    evidence_text TEXT,
                    verification_status TEXT,
                    rejection_reason TEXT,
                    PRIMARY KEY (claim_id, run_id)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS crm_tasks (
                    task_id TEXT,
                    run_id TEXT,
                    idempotency_key TEXT UNIQUE,
                    client_name TEXT,
                    cluster_id TEXT,
                    title TEXT,
                    description TEXT,
                    severity TEXT,
                    status TEXT,
                    created_at TEXT,
                    audit_id TEXT,
                    PRIMARY KEY (task_id)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS crm_audit (
                    audit_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    idempotency_key TEXT,
                    action TEXT,
                    payload_json TEXT,
                    response_json TEXT,
                    status_code INTEGER,
                    timestamp TEXT
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS cost_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    timestamp TEXT,
                    provider TEXT,
                    model TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    cost_eur REAL,
                    cumulative_cost_eur REAL
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    run_id TEXT,
                    stage TEXT,
                    status TEXT,
                    completed_at TEXT,
                    metadata_json TEXT,
                    PRIMARY KEY (run_id, stage)
                )
            """)

    def save_run_summary(self, summary: RunSummary) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO runs (run_id, status, started_at, completed_at, summary_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    summary.run_id,
                    summary.status,
                    summary.started_at.isoformat(),
                    summary.completed_at.isoformat() if summary.completed_at else None,
                    summary.model_dump_json(),
                ),
            )

    def get_run_summary(self, run_id: str) -> Optional[RunSummary]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT summary_json FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if row and row[0]:
            return RunSummary.model_validate_json(row[0])
        return None

    def list_runs(self) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT run_id, status, started_at, completed_at, summary_json FROM runs ORDER BY started_at DESC")
        runs = []
        for row in cursor.fetchall():
            summary_dict = json.loads(row[4]) if row[4] else {}
            client_name = summary_dict.get("client_name") or "Global Logistics NV"
            runs.append({
                "run_id": row[0],
                "status": row[1],
                "started_at": row[2],
                "completed_at": row[3],
                "client_name": client_name,
                "total_articles": summary_dict.get("total_articles", 0),
                "total_clusters": summary_dict.get("total_clusters", 0),
                "verified_claims": summary_dict.get("verified_claims", 0),
                "summary": summary_dict
            })
        return runs

    def save_articles(self, run_id: str, articles: List[Article]) -> None:
        with self.conn:
            for art in articles:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO articles (
                        id, run_id, source, url, title, body, language, published_at,
                        retrieved_at, body_status, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        art.id,
                        run_id,
                        art.source,
                        art.url,
                        art.title,
                        art.body,
                        art.language,
                        art.published_at.isoformat() if art.published_at else None,
                        art.retrieved_at.isoformat(),
                        art.body_status.value,
                        art.content_hash,
                    ),
                )

    def get_articles(self, run_id: str) -> List[Article]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM articles WHERE run_id = ?", (run_id,))
        articles = []
        for row in cursor.fetchall():
            articles.append(Article(
                id=row["id"],
                source=row["source"],
                url=row["url"],
                title=row["title"],
                body=row["body"],
                language=row["language"],
                published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
                retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
                body_status=row["body_status"],
                content_hash=row["content_hash"]
            ))
        return articles

    def save_clusters(self, run_id: str, clusters: List[Cluster]) -> None:
        with self.conn:
            for c in clusters:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO clusters (
                        cluster_id, run_id, canonical_title, earliest_published_at,
                        first_source, article_ids_json, is_update, update_of
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c.cluster_id,
                        run_id,
                        c.canonical_title,
                        c.earliest_published_at.isoformat() if c.earliest_published_at else None,
                        c.first_source,
                        json.dumps(c.article_ids),
                        1 if c.is_update else 0,
                        c.update_of_cluster_id
                    )
                )

    def get_clusters(self, run_id: str) -> List[Cluster]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM clusters WHERE run_id = ?", (run_id,))
        clusters = []
        for row in cursor.fetchall():
            clusters.append(Cluster(
                cluster_id=row["cluster_id"],
                canonical_title=row["canonical_title"],
                earliest_published_at=datetime.fromisoformat(row["earliest_published_at"]) if row["earliest_published_at"] else None,
                first_source=row["first_source"],
                article_ids=json.loads(row["article_ids_json"]),
                is_update=bool(row["is_update"]),
                update_of_cluster_id=row["update_of"]
            ))
        return clusters

    def save_entity_mentions(self, run_id: str, mentions: List[EntityMention]) -> None:
        with self.conn:
            for m in mentions:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO entity_mentions (
                        mention_id, run_id, article_id, entity_name, entity_type,
                        is_client, confidence, justification, evidence_text, start_char, end_char
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        m.mention_id,
                        run_id,
                        m.article_id,
                        m.entity_name,
                        m.entity_type,
                        1 if m.is_client else 0,
                        m.confidence,
                        m.justification,
                        m.evidence_text,
                        m.start_char,
                        m.end_char
                    )
                )

    def save_claims(self, run_id: str, claims: List[Claim]) -> None:
        with self.conn:
            for c in claims:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO claims (
                        claim_id, run_id, cluster_id, language, section,
                        claim_text, article_id, source_url, start_char, end_char,
                        evidence_text, verification_status, rejection_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c.claim_id,
                        run_id,
                        c.cluster_id,
                        c.language,
                        c.section,
                        c.claim_text,
                        c.article_id,
                        c.source_url,
                        c.start_char,
                        c.end_char,
                        c.evidence_text,
                        c.verification_status.value,
                        c.rejection_reason
                    )
                )

    def get_claims(self, run_id: str) -> List[Claim]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM claims WHERE run_id = ?", (run_id,))
        claims = []
        for row in cursor.fetchall():
            claims.append(Claim(
                claim_id=row["claim_id"],
                cluster_id=row["cluster_id"],
                language=row["language"],
                section=row["section"],
                claim_text=row["claim_text"],
                article_id=row["article_id"],
                source_url=row["source_url"],
                start_char=row["start_char"],
                end_char=row["end_char"],
                evidence_text=row["evidence_text"],
                verification_status=row["verification_status"],
                rejection_reason=row["rejection_reason"]
            ))
        return claims

    def save_crm_task(self, run_id: str, task: CRMTask) -> bool:
        """Saves a CRM task. Returns True if created, False if already exists (idempotent)."""
        with self.conn:
            try:
                self.conn.execute(
                    """
                    INSERT INTO crm_tasks (
                        task_id, run_id, idempotency_key, client_name, cluster_id,
                        title, description, severity, status, created_at, audit_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task.task_id,
                        run_id,
                        task.idempotency_key,
                        task.client_name,
                        task.cluster_id,
                        task.title,
                        task.description,
                        task.severity.value,
                        task.status,
                        task.created_at.isoformat(),
                        task.audit_id
                    )
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def log_crm_audit(
        self,
        audit_id: str,
        run_id: str,
        idempotency_key: str,
        action: str,
        payload: Dict[str, Any],
        response: Dict[str, Any],
        status_code: int
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO crm_audit (
                    audit_id, run_id, idempotency_key, action, payload_json,
                    response_json, status_code, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    run_id,
                    idempotency_key,
                    action,
                    json.dumps(payload),
                    json.dumps(response),
                    status_code,
                    datetime.now(timezone.utc).isoformat()
                )
            )

    def get_crm_tasks(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        if run_id:
            cursor.execute("SELECT * FROM crm_tasks WHERE run_id = ?", (run_id,))
        else:
            cursor.execute("SELECT * FROM crm_tasks ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def get_crm_audit_logs(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        if run_id:
            cursor.execute("SELECT * FROM crm_audit WHERE run_id = ? ORDER BY timestamp DESC", (run_id,))
        else:
            cursor.execute("SELECT * FROM crm_audit ORDER BY timestamp DESC")
        return [dict(row) for row in cursor.fetchall()]

    def set_checkpoint(self, run_id: str, stage: str, status: str = "completed", metadata: Optional[Dict[str, Any]] = None) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO checkpoints (run_id, stage, status, completed_at, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    stage,
                    status,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(metadata or {})
                )
            )

    def is_checkpoint_completed(self, run_id: str, stage: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM checkpoints WHERE run_id = ? AND stage = ?", (run_id, stage))
        row = cursor.fetchone()
        return bool(row and row[0] == "completed")

    def record_cost_entry(
        self,
        run_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_eur: float,
        cumulative_cost_eur: float
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO cost_ledger (
                    run_id, timestamp, provider, model, input_tokens, output_tokens,
                    cost_eur, cumulative_cost_eur
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    datetime.now(timezone.utc).isoformat(),
                    provider,
                    model,
                    input_tokens,
                    output_tokens,
                    cost_eur,
                    cumulative_cost_eur
                )
            )

    def get_total_cost(self, run_id: str) -> float:
        cursor = self.conn.cursor()
        cursor.execute("SELECT SUM(cost_eur) FROM cost_ledger WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        return float(row[0] or 0.0)

    def close(self) -> None:
        self.conn.close()
