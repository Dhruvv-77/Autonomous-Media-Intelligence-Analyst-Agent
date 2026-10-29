"""Append-only JSONL tracing with automated redaction of sensitive data."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from src.models import TraceEvent


class Tracer:
    def __init__(self, trace_path: str = "outputs/trace.jsonl", redact: bool = True) -> None:
        self.trace_path = Path(trace_path)
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.redact = redact
        self._secret_patterns = [
            re.compile(r"(AIza[0-9A-Za-z-_]{35})"),  # Gemini / Google API keys
            re.compile(r"(sk-[a-zA-Z0-9]{32,})"),    # OpenAI style keys
            re.compile(r"(bearer\s+)([a-zA-Z0-9\._\-]+)", re.IGNORECASE),
        ]

    def _sanitize(self, obj: Any) -> Any:
        if not self.redact:
            return obj
        if isinstance(obj, str):
            res = obj
            for pattern in self._secret_patterns:
                res = pattern.sub("[REDACTED_SECRET]", res)
            return res
        if isinstance(obj, dict):
            sanitized = {}
            for k, v in obj.items():
                if any(sec in k.lower() for sec in ["api_key", "secret", "password", "token", "authorization"]):
                    sanitized[k] = "[REDACTED_SECRET]"
                else:
                    sanitized[k] = self._sanitize(v)
            return sanitized
        if isinstance(obj, list):
            return [self._sanitize(item) for item in obj]
        return obj

    def log_event(
        self,
        run_id: str,
        stage: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        tokens: Optional[int] = None,
        cost_eur: Optional[float] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None
    ) -> TraceEvent:
        clean_details = self._sanitize(details or {})
        clean_error = self._sanitize(error) if error else None
        
        event = TraceEvent(
            timestamp=datetime.now(timezone.utc),
            run_id=run_id,
            stage=stage,
            event_type=event_type,
            details=clean_details,
            tokens=tokens,
            cost_eur=cost_eur,
            duration_ms=duration_ms,
            error=clean_error
        )
        
        with open(self.trace_path, "a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")
            
        return event
