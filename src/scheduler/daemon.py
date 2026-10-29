"""Autonomous Scheduler Daemon for Scheduled Early Morning and Interval Media Runs."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from src.config import AgentSystemConfig
from src.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)


class AutonomousDaemon:
    """Manages autonomous recurring runs (daily morning or intraday interval)."""

    def __init__(self, config: AgentSystemConfig) -> None:
        self.config = config
        self.enabled = False
        self.mode = "daily"  # 'daily' or 'interval'
        self.daily_time_utc = "06:00"  # 06:00 UTC (early morning before market open)
        self.interval_seconds = 3 * 3600  # Default 3 hours for high-frequency/stock updates
        self.is_running = False
        self.last_run_time: Optional[str] = None
        self.last_run_id: Optional[str] = None
        self.next_run_time: Optional[str] = None
        self.total_runs_completed = 0
        self.last_error: Optional[str] = None

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._execution_lock = threading.Lock()

    def start(self, mode: str = "daily", interval_hours: int = 3, daily_time_utc: str = "06:00") -> None:
        """Start the background autonomous scheduler thread."""
        self.mode = mode
        self.interval_seconds = max(1, interval_hours) * 3600
        self.daily_time_utc = daily_time_utc
        self.enabled = True
        self._stop_event.clear()

        self._compute_next_run()

        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="AutonomousDaemon")
            self._thread.start()
            logger.info("Autonomous scheduler daemon started in %s mode", self.mode)

    def stop(self) -> None:
        """Stop the background autonomous scheduler thread."""
        self.enabled = False
        self._stop_event.set()
        self.next_run_time = None
        logger.info("Autonomous scheduler daemon stopped")

    def trigger_run_now(self) -> Dict[str, Any]:
        """Manually trigger an autonomous run in the background."""
        if self.is_running:
            return {"status": "already_running", "message": "A pipeline run is currently in progress."}

        # Spawn execution in separate thread so it doesn't block the caller
        exec_thread = threading.Thread(target=self._execute_pipeline, daemon=True, name="ManualScheduledTrigger")
        exec_thread.start()
        return {"status": "started", "message": "Pipeline run triggered successfully."}

    def get_status(self) -> Dict[str, Any]:
        """Get current scheduler health and next-run cadence."""
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "interval_hours": int(self.interval_seconds / 3600),
            "daily_time_utc": self.daily_time_utc,
            "is_running": self.is_running,
            "last_run_time": self.last_run_time,
            "last_run_id": self.last_run_id,
            "next_run_time": self.next_run_time,
            "total_runs_completed": self.total_runs_completed,
            "last_error": self.last_error,
        }

    def _compute_next_run(self) -> None:
        """Calculate the next execution timestamp based on active mode."""
        now = datetime.now(timezone.utc)
        if self.mode == "interval":
            next_dt = now + timedelta(seconds=self.interval_seconds)
            self.next_run_time = next_dt.isoformat()
        else:  # Daily morning run
            try:
                target_hour, target_min = map(int, self.daily_time_utc.split(":"))
            except Exception:
                target_hour, target_min = 6, 0

            candidate = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(days=1)
            self.next_run_time = candidate.isoformat()

    def _scheduler_loop(self) -> None:
        """Main loop that polls for trigger times without busy-waiting."""
        while not self._stop_event.is_set():
            if not self.enabled:
                time.sleep(2)
                continue

            now = datetime.now(timezone.utc)
            if self.next_run_time:
                try:
                    target_dt = datetime.fromisoformat(self.next_run_time)
                    if now >= target_dt:
                        self._execute_pipeline()
                        self._compute_next_run()
                except Exception as e:
                    logger.error("Error evaluating next run time: %s", e)
                    self._compute_next_run()

            # Sleep in small increments to respond quickly to stop/toggle events
            self._stop_event.wait(timeout=5)

    def _execute_pipeline(self) -> None:
        """Run the end-to-end pipeline under execution lock."""
        with self._execution_lock:
            if self.is_running:
                return

            self.is_running = True
            self.last_error = None
            start_iso = datetime.now(timezone.utc).isoformat()

            try:
                logger.info("Executing scheduled autonomous pipeline run at %s", start_iso)
                orchestrator = PipelineOrchestrator(self.config)
                summary = orchestrator.run()
                self.last_run_time = datetime.now(timezone.utc).isoformat()
                self.last_run_id = summary.run_id
                self.total_runs_completed += 1
                logger.info("Scheduled pipeline completed successfully (run_id: %s)", summary.run_id)
            except Exception as e:
                self.last_error = str(e)
                logger.exception("Scheduled pipeline failed: %s", e)
            finally:
                self.is_running = False
