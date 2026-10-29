"""Unit tests for the Autonomous Daemon and scheduling cadences."""

from datetime import datetime, timezone
from src.config import AgentSystemConfig
from src.scheduler.daemon import AutonomousDaemon


def test_scheduler_daily_computation():
    config = AgentSystemConfig.load("config.example.yaml")
    daemon = AutonomousDaemon(config)
    daemon.mode = "daily"
    daemon.daily_time_utc = "06:00"
    daemon._compute_next_run()

    assert daemon.next_run_time is not None
    next_dt = datetime.fromisoformat(daemon.next_run_time)
    assert next_dt.hour == 6
    assert next_dt.minute == 0
    assert next_dt > datetime.now(timezone.utc)


def test_scheduler_interval_computation():
    config = AgentSystemConfig.load("config.example.yaml")
    daemon = AutonomousDaemon(config)
    daemon.mode = "interval"
    daemon.interval_seconds = 2 * 3600
    daemon._compute_next_run()

    assert daemon.next_run_time is not None
    next_dt = datetime.fromisoformat(daemon.next_run_time)
    diff_sec = (next_dt - datetime.now(timezone.utc)).total_seconds()
    assert 7100 < diff_sec <= 7205


def test_scheduler_start_stop_lifecycle():
    config = AgentSystemConfig.load("config.example.yaml")
    daemon = AutonomousDaemon(config)
    daemon.start(mode="daily", daily_time_utc="07:00")

    status = daemon.get_status()
    assert status["enabled"] is True
    assert status["mode"] == "daily"
    assert status["daily_time_utc"] == "07:00"
    assert status["next_run_time"] is not None

    daemon.stop()
    stopped_status = daemon.get_status()
    assert stopped_status["enabled"] is False
    assert stopped_status["next_run_time"] is None


def test_scheduler_execution_lock_prevents_overlap():
    config = AgentSystemConfig.load("config.example.yaml")
    daemon = AutonomousDaemon(config)
    daemon.is_running = True

    # When already running, manual trigger returns already_running
    res = daemon.trigger_run_now()
    assert res["status"] == "already_running"
