"""Tests for pipeline resilience: malformed rows, duplicate records, checkpoints, and resume."""

import json
import pytest
from src.news.corpus_loader import CorpusLoader
from src.storage.database import Database


def test_malformed_jsonl_rows_quarantined_without_crash(tmp_path):
    corpus_file = tmp_path / "test_corpus.jsonl"
    lines = [
        json.dumps({"id": "art_1", "title": "Valid Article 1", "body": "Body content here."}),
        "THIS_IS_CORRUPTED_NON_JSON_CONTENT{{{",
        json.dumps({"id": "art_2", "title": "", "body": "Missing title row."}),
        json.dumps({"id": "art_3", "title": "Valid Article 3", "body": "Another valid body."}),
        "12345",  # non-dict json
    ]
    corpus_file.write_text("\n".join(lines), encoding="utf-8")

    loader = CorpusLoader()
    valid_articles, error_logs = loader.load_jsonl(str(corpus_file))

    assert len(valid_articles) == 2
    assert [a.id for a in valid_articles] == ["art_1", "art_3"]
    assert len(error_logs) >= 3


def test_duplicate_article_ids_detected_without_silent_overwrite(tmp_path):
    corpus_file = tmp_path / "test_dups.jsonl"
    lines = [
        json.dumps({"id": "art_same", "title": "First instance", "body": "Body A"}),
        json.dumps({"id": "art_same", "title": "Duplicate instance", "body": "Body B"}),
    ]
    corpus_file.write_text("\n".join(lines), encoding="utf-8")

    loader = CorpusLoader()
    valid_articles, error_logs = loader.load_jsonl(str(corpus_file))

    assert len(valid_articles) == 1
    assert valid_articles[0].title == "First instance"
    assert any("Duplicate article ID" in err for err in error_logs)


def test_checkpoint_and_resume_state(tmp_path):
    db_file = tmp_path / "test_ckpt.db"
    db = Database(str(db_file))
    run_id = "run_resume_test"

    assert db.is_checkpoint_completed(run_id, "ingestion") is False
    db.set_checkpoint(run_id, "ingestion", "completed", {"articles": 10})
    assert db.is_checkpoint_completed(run_id, "ingestion") is True
    assert db.is_checkpoint_completed(run_id, "clustering") is False
