"""
Tests for the Validator Monitor and enhanced Auto-Updater.

Run: cd /root/project-nobi && python3 -m pytest tests/test_validator_monitor.py -v --tb=short
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from validator_monitor import ValidatorMonitor, detect_validator_processes
from auto_updater import (
    AutoUpdater,
    RESTART_GRACEFUL,
    RESTART_HARD,
    DEFAULT_RESTART_STRATEGIES,
    STEP_COMPLETE_PATTERNS,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temporary git repo for testing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), capture_output=True)
    (repo / "README.md").write_text("hello")
    (repo / "requirements.txt").write_text("bittensor>=10.2.0\n")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(repo), capture_output=True)
    return str(repo)


@pytest.fixture
def log_dir(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    return str(d)


@pytest.fixture
def health_file(tmp_path):
    return str(tmp_path / "health.json")


@pytest.fixture
def monitor(health_file):
    return ValidatorMonitor(
        pm2_name="nobi-validator",
        netuid=272,
        network="test",
        health_file=health_file,
    )


@pytest.fixture
def updater(tmp_repo, log_dir):
    return AutoUpdater(
        repo_path=tmp_repo,
        check_interval=60,
        pm2_names=["nobi-validator", "nobi-miner"],
        branch="main",
        log_dir=log_dir,
    )


# ============================================================================
# ValidatorMonitor Tests
# ============================================================================

class TestValidatorMonitorInit:
    """Test 1: ValidatorMonitor initialization."""

    def test_basic_init(self, monitor):
        assert monitor.pm2_name == "nobi-validator"
        assert monitor.netuid == 272
        assert monitor.network == "test"

    def test_health_file_dir_created(self, tmp_path):
        hf = str(tmp_path / "new_dir" / "health.json")
        m = ValidatorMonitor("test-val", health_file=hf)
        assert (tmp_path / "new_dir").exists()

    def test_default_health_file(self):
        m = ValidatorMonitor("test-val")
        assert "validator_health.json" in str(m.health_file)


class TestCheckHealth:
    """Test 2-5: Health check logic."""

    def test_healthy_validator(self, monitor):
        """Test 2: Fully healthy validator."""
        pm2_data = [{"name": "nobi-validator", "pm_id": 0, "pm2_env": {
            "status": "online", "restart_time": 2, "pm_uptime": time.time() * 1000 - 3600000
        }}]
        logs = "Connected to subtensor\nset_weights successful\n"

        with patch.object(monitor, "_run_cmd") as mock:
            mock.side_effect = [
                (0, json.dumps(pm2_data), ""),  # pm2 jlist
                (0, logs, ""),  # pm2 logs
                (0, logs, ""),  # pm2 logs (weight check)
            ]
            health = monitor.check_health()

        assert health["running"] is True
        assert health["connected"] is True
        assert health["setting_weights"] is True
        assert health["crash_looping"] is False

    def test_not_found(self, monitor):
        """Test 3: Validator process not found."""
        with patch.object(monitor, "_run_cmd") as mock:
            mock.return_value = (0, json.dumps([]), "")
            health = monitor.check_health()

        assert health["running"] is False
        assert health["status"] == "not_found"

    def test_crash_looping(self, monitor):
        """Test 4: Crash-looping validator (high restarts, low uptime)."""
        pm2_data = [{"name": "nobi-validator", "pm_id": 0, "pm2_env": {
            "status": "online", "restart_time": 15, "pm_uptime": time.time() * 1000 - 5000
        }}]
        with patch.object(monitor, "_run_cmd") as mock:
            mock.side_effect = [
                (0, json.dumps(pm2_data), ""),
                (0, "", ""),  # logs
                (0, "", ""),  # weight check logs
            ]
            health = monitor.check_health()

        assert health["crash_looping"] is True
        assert health["restarts"] == 15

    def test_not_connected(self, monitor):
        """Test 5: Running but not connected."""
        pm2_data = [{"name": "nobi-validator", "pm_id": 0, "pm2_env": {
            "status": "online", "restart_time": 0, "pm_uptime": time.time() * 1000 - 100000
        }}]
        with patch.object(monitor, "_run_cmd") as mock:
            mock.side_effect = [
                (0, json.dumps(pm2_data), ""),
                (0, "Starting up...\nLoading model...\n", ""),  # no connection keywords
                (0, "Starting up...\nLoading model...\n", ""),
            ]
            health = monitor.check_health()

        assert health["running"] is True
        assert health["connected"] is False


class TestWeightSetting:
    """Test 6-8: Weight setting detection."""

    def test_weights_being_set(self, monitor):
        """Test 6: Weights actively being set."""
        logs = """2026-03-20T10:00:00 Setting weights for epoch 5
2026-03-20T10:15:00 set_weights successful
2026-03-20T10:30:00 set_weights successful"""

        result = monitor.check_weight_setting(logs)
        assert result["successful"] is True
        assert result["count_recent"] == 3

    def test_no_weights(self, monitor):
        """Test 7: No weight setting detected."""
        logs = "Starting validator...\nLoading model...\nForward pass complete\n"
        result = monitor.check_weight_setting(logs)
        assert result["successful"] is False
        assert result["count_recent"] == 0

    def test_weight_interval_calculation(self, monitor):
        """Test 8: Weight setting interval calculation."""
        logs = """2026-03-20T10:00:00 set_weights ok
2026-03-20T10:30:00 set_weights ok"""

        result = monitor.check_weight_setting(logs)
        assert result["interval"] is not None
        assert result["interval"] == 1800.0  # 30 minutes


class TestDiagnoseIssues:
    """Test 9-12: Issue diagnosis."""

    def test_not_running_issue(self, monitor):
        """Test 9: Diagnose not-running validator."""
        with patch.object(monitor, "check_health", return_value={
            "running": False, "status": "not_found", "crash_looping": False,
            "connected": False, "setting_weights": False, "restarts": 0, "uptime": 0,
            "last_weight_set": None, "pm2_id": None, "timestamp": "",
        }), patch.object(monitor, "_get_pm2_logs", return_value=""):
            issues = monitor.diagnose_issues()

        assert any("not found" in i.lower() for i in issues)

    def test_crash_loop_issue(self, monitor):
        """Test 10: Diagnose crash-looping."""
        with patch.object(monitor, "check_health", return_value={
            "running": True, "status": "online", "crash_looping": True,
            "connected": True, "setting_weights": False, "restarts": 20, "uptime": 5,
            "last_weight_set": None, "pm2_id": 0, "timestamp": "",
        }), patch.object(monitor, "_get_pm2_logs", return_value=""):
            issues = monitor.diagnose_issues()

        assert any("crash-looping" in i.lower() for i in issues)

    def test_wallet_error_from_logs(self, monitor):
        """Test 11: Diagnose wallet issues from logs."""
        with patch.object(monitor, "check_health", return_value={
            "running": True, "status": "online", "crash_looping": False,
            "connected": True, "setting_weights": True, "restarts": 0, "uptime": 3600,
            "last_weight_set": "recently", "pm2_id": 0, "timestamp": "",
        }), patch.object(monitor, "_get_pm2_logs", return_value="Error: wallet key not found\n"):
            issues = monitor.diagnose_issues()

        assert any("wallet" in i.lower() for i in issues)

    def test_no_issues(self, monitor):
        """Test 12: No issues when everything healthy."""
        with patch.object(monitor, "check_health", return_value={
            "running": True, "status": "online", "crash_looping": False,
            "connected": True, "setting_weights": True, "restarts": 1, "uptime": 86400,
            "last_weight_set": "recently", "pm2_id": 0, "timestamp": "",
        }), patch.object(monitor, "_get_pm2_logs", return_value="All good\n"):
            issues = monitor.diagnose_issues()

        assert len(issues) == 0


class TestGetReport:
    """Test 13: Report generation."""

    def test_report_contains_sections(self, monitor):
        """Test 13: Report has all expected sections."""
        with patch.object(monitor, "check_health", return_value={
            "running": True, "status": "online", "crash_looping": False,
            "connected": True, "setting_weights": True, "restarts": 2, "uptime": 7200,
            "last_weight_set": "just now", "pm2_id": 0, "timestamp": "",
        }), patch.object(monitor, "check_weight_setting", return_value={
            "last_set": "line", "interval": 900, "successful": True, "count_recent": 5,
        }), patch.object(monitor, "check_metagraph_status", return_value={
            "uid": None, "stake": None, "trust": None, "vtrust": None, "rank": None,
            "available": False,
        }), patch.object(monitor, "diagnose_issues", return_value=[]):
            report = monitor.get_report()

        assert "Health Status" in report
        assert "Weight Setting" in report
        assert "No issues detected" in report
        assert "nobi-validator" in report


class TestSaveHealth:
    """Test 14: Health file saving."""

    def test_save_creates_file(self, monitor, health_file):
        """Test 14: Save health to file."""
        with patch.object(monitor, "check_health", return_value={
            "running": True, "status": "online", "crash_looping": False,
            "connected": True, "setting_weights": True, "restarts": 0, "uptime": 100,
            "last_weight_set": None, "pm2_id": 0, "timestamp": "",
        }), patch.object(monitor, "check_weight_setting", return_value={
            "last_set": None, "interval": None, "successful": True, "count_recent": 1,
        }), patch.object(monitor, "diagnose_issues", return_value=[]):
            monitor.save_health()

        assert os.path.exists(health_file)
        with open(health_file) as f:
            data = json.load(f)
        assert "nobi-validator" in data
        assert data["nobi-validator"]["health"]["running"] is True


class TestMinerScores:
    """Test 15: Miner score extraction."""

    def test_extract_scores(self, monitor):
        """Test 15: Extract miner scores from logs."""
        logs = """2026-03-20 scoring uid 5 score: 0.85
2026-03-20 scoring uid 12 score: 0.42
unrelated log line"""
        with patch.object(monitor, "_get_pm2_logs", return_value=logs):
            scores = monitor.get_miner_scores()
        # Should find score lines
        assert isinstance(scores, list)

    def test_no_scores(self, monitor):
        """Test 15b: No scores in logs."""
        with patch.object(monitor, "_get_pm2_logs", return_value="just regular logs\n"):
            scores = monitor.get_miner_scores()
        assert scores == []


class TestDetectValidatorProcesses:
    """Test 16: Auto-detection of validator processes."""

    def test_detect_validators(self):
        """Test 16: Detect validator processes from PM2."""
        pm2_data = json.dumps([
            {"name": "nobi-validator-1"},
            {"name": "nobi-miner-1"},
            {"name": "other-app"},
        ])
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=pm2_data)
            result = detect_validator_processes()
        assert "nobi-validator-1" in result
        assert "nobi-miner-1" not in result

    def test_detect_no_pm2(self):
        """Test 16b: No PM2 available."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = detect_validator_processes()
        assert result == []


# ============================================================================
# Enhanced AutoUpdater Tests
# ============================================================================

class TestRestartStrategies:
    """Test 17-18: Per-process restart strategies."""

    def test_validator_gets_graceful(self, updater):
        """Test 17: Validator processes get graceful restart."""
        assert updater._get_restart_strategy("nobi-validator") == RESTART_GRACEFUL

    def test_miner_gets_hard(self, updater):
        """Test 17b: Miner processes get hard restart."""
        assert updater._get_restart_strategy("nobi-miner") == RESTART_HARD

    def test_explicit_strategy_override(self, tmp_repo, log_dir):
        """Test 18: Explicit strategies override defaults."""
        u = AutoUpdater(
            tmp_repo, pm2_names=["my-validator"], log_dir=log_dir,
            restart_strategies={"my-validator": RESTART_HARD},
        )
        assert u._get_restart_strategy("my-validator") == RESTART_HARD

    def test_unknown_process_gets_hard(self, updater):
        """Test 18b: Unknown processes default to hard restart."""
        assert updater._get_restart_strategy("some-random-app") == RESTART_HARD


class TestGracefulRestart:
    """Test 19-20: Graceful restart wait logic."""

    def test_wait_for_step_completion_found(self, updater):
        """Test 19: Detects step completion in logs."""
        with patch.object(updater, "_run_cmd") as mock:
            mock.return_value = (0, "epoch 5 step completed successfully", "")
            result = updater._wait_for_step_completion("nobi-validator", timeout=5)
        assert result is True

    def test_wait_for_step_completion_timeout(self, updater):
        """Test 20: Times out when no step completion."""
        with patch.object(updater, "_run_cmd") as mock:
            mock.return_value = (0, "processing batch 42...", "")
            with patch("auto_updater.time.sleep"):  # Don't actually sleep
                with patch("auto_updater.GRACEFUL_POLL_INTERVAL", 0):
                    result = updater._wait_for_step_completion("nobi-validator", timeout=0)
        assert result is False

    def test_wait_process_not_running(self, updater):
        """Test 20b: Process not running = safe to restart."""
        with patch.object(updater, "_run_cmd") as mock:
            mock.return_value = (1, "", "process not found")
            result = updater._wait_for_step_completion("nobi-validator", timeout=5)
        assert result is True


class TestDependencyCheck:
    """Test 21-22: Dependency change detection."""

    def test_detect_requirements_change(self, updater):
        """Test 21: Detect requirements.txt change."""
        with patch.object(updater, "_run_cmd") as mock:
            mock.return_value = (0, "requirements.txt\nsrc/main.py", "")
            assert updater.check_dependency_changes() is True

    def test_no_dependency_change(self, updater):
        """Test 21b: No dependency files changed."""
        with patch.object(updater, "_run_cmd") as mock:
            mock.return_value = (0, "src/main.py\ntests/test.py", "")
            assert updater.check_dependency_changes() is False

    def test_detect_pyproject_change(self, updater):
        """Test 22: Detect pyproject.toml change."""
        with patch.object(updater, "_run_cmd") as mock:
            mock.return_value = (0, "pyproject.toml", "")
            assert updater.check_dependency_changes() is True

    def test_install_dependencies_success(self, updater):
        """Test 22b: Successful dependency install."""
        with patch.object(updater, "_run_cmd") as mock:
            mock.return_value = (0, "Successfully installed", "")
            assert updater.install_dependencies() is True

    def test_install_dependencies_failure(self, updater):
        """Test 22c: Failed dependency install."""
        with patch.object(updater, "_run_cmd") as mock:
            mock.return_value = (1, "", "Could not find package")
            assert updater.install_dependencies() is False


class TestWebsiteSync:
    """Test 23-24: Website sync logic."""

    def test_sync_copies_files(self, updater, tmp_path):
        """Test 23: Website sync copies landing files."""
        # Create landing dir
        landing = Path(updater.repo_path) / "docs" / "landing"
        landing.mkdir(parents=True)
        (landing / "index.html").write_text("<h1>Hello</h1>")
        (landing / "style.css").write_text("body { color: red; }")

        # Create website dir
        website = tmp_path / "www"
        website.mkdir()
        updater.website_dir = str(website)

        result = updater.sync_website()
        assert result is True
        assert (website / "index.html").read_text() == "<h1>Hello</h1>"
        assert (website / "style.css").read_text() == "body { color: red; }"

    def test_sync_skips_no_landing(self, updater):
        """Test 23b: Skip sync when no docs/landing."""
        updater.website_dir = "/nonexistent"
        assert updater.sync_website() is False

    def test_sync_skips_no_website_dir(self, updater, tmp_path):
        """Test 24: Skip sync when website dir doesn't exist."""
        landing = Path(updater.repo_path) / "docs" / "landing"
        landing.mkdir(parents=True)
        (landing / "index.html").write_text("test")
        updater.website_dir = str(tmp_path / "nonexistent_www")
        assert updater.sync_website() is False

    def test_sync_copies_subdirectories(self, updater, tmp_path):
        """Test 24b: Sync copies subdirectories too."""
        landing = Path(updater.repo_path) / "docs" / "landing"
        assets = landing / "assets"
        assets.mkdir(parents=True)
        (assets / "logo.png").write_text("fake png")

        website = tmp_path / "www"
        website.mkdir()
        updater.website_dir = str(website)

        updater.sync_website()
        assert (website / "assets" / "logo.png").exists()


class TestPostRestartHealthCheck:
    """Test 25: Validator post-restart health verification."""

    def test_post_restart_healthy(self, updater):
        """Test 25: Post-restart health check detects healthy validator."""
        pm2_data = json.dumps([{"name": "nobi-validator", "pm_id": 0, "pm2_env": {
            "status": "online", "restart_time": 1, "pm_uptime": time.time() * 1000 - 20000
        }}])
        with patch.object(updater, "_run_cmd") as mock:
            mock.side_effect = [
                (0, pm2_data, ""),  # jlist
                (0, "Connected to subtensor\nset_weights ok\n", ""),  # logs
            ]
            with patch("auto_updater.time.sleep"):
                health = updater._check_validator_post_restart("nobi-validator", wait_seconds=0)

        assert health["running"] is True
        assert health["connected"] is True

    def test_post_restart_crash_loop(self, updater):
        """Test 25b: Post-restart detects crash loop."""
        pm2_data = json.dumps([{"name": "nobi-validator", "pm_id": 0, "pm2_env": {
            "status": "online", "restart_time": 10, "pm_uptime": time.time() * 1000 - 5000
        }}])
        with patch.object(updater, "_run_cmd") as mock:
            mock.side_effect = [
                (0, pm2_data, ""),
                (0, "Error: crash!\n", ""),
            ]
            with patch("auto_updater.time.sleep"):
                health = updater._check_validator_post_restart("nobi-validator", wait_seconds=0)

        assert health["crash_looping"] is True


class TestEnhancedUpdateCycle:
    """Test 26-27: Full update cycle with new features."""

    def test_cycle_with_deps_and_website(self, updater):
        """Test 26: Full cycle installs deps and syncs website."""
        with patch.object(updater, "check_for_updates", return_value=True), \
             patch.object(updater, "_get_current_commit", side_effect=["aaa", "bbb"]), \
             patch.object(updater, "pull_update", return_value=(True, "feat")), \
             patch.object(updater, "check_dependency_changes", return_value=True), \
             patch.object(updater, "install_dependencies", return_value=True) as mock_install, \
             patch.object(updater, "run_health_check", return_value=True), \
             patch.object(updater, "restart_processes", return_value={"nobi-validator": True}), \
             patch.object(updater, "sync_website", return_value=True) as mock_sync:
            result = updater.update_cycle()

        assert result is True
        mock_install.assert_called_once()
        mock_sync.assert_called_once()

    def test_cycle_no_deps_change(self, updater):
        """Test 27: Cycle skips dep install when no changes."""
        with patch.object(updater, "check_for_updates", return_value=True), \
             patch.object(updater, "_get_current_commit", side_effect=["aaa", "bbb"]), \
             patch.object(updater, "pull_update", return_value=(True, "fix")), \
             patch.object(updater, "check_dependency_changes", return_value=False), \
             patch.object(updater, "install_dependencies") as mock_install, \
             patch.object(updater, "run_health_check", return_value=True), \
             patch.object(updater, "restart_processes", return_value={}), \
             patch.object(updater, "sync_website"):
            updater.update_cycle()

        mock_install.assert_not_called()


class TestPM2ProcessHealth:
    """Test 28: PM2 process health check."""

    def test_check_pm2_health_online(self, updater):
        """Test 28: Check PM2 process health for online process."""
        pm2_data = json.dumps([{"name": "nobi-validator", "pm_id": 0, "pm2_env": {
            "status": "online", "restart_time": 3, "pm_uptime": time.time() * 1000 - 7200000
        }}])
        with patch.object(updater, "_run_cmd") as mock:
            mock.return_value = (0, pm2_data, "")
            health = updater._check_pm2_process_health("nobi-validator")

        assert health["running"] is True
        assert health["restarts"] == 3
        assert health["crash_looping"] is False

    def test_check_pm2_health_not_found(self, updater):
        """Test 28b: PM2 health for non-existent process."""
        with patch.object(updater, "_run_cmd") as mock:
            mock.return_value = (0, json.dumps([]), "")
            health = updater._check_pm2_process_health("nonexistent")

        assert health["running"] is False


class TestUptimeFormatting:
    """Test 29: Uptime formatting."""

    def test_seconds(self, monitor):
        assert monitor._format_uptime(30) == "30s"

    def test_minutes(self, monitor):
        assert "m" in monitor._format_uptime(300)

    def test_hours(self, monitor):
        assert "h" in monitor._format_uptime(7200)

    def test_days(self, monitor):
        assert "d" in monitor._format_uptime(172800)

    def test_zero(self, monitor):
        assert monitor._format_uptime(0) == "N/A"


class TestLogDiagnosis:
    """Test 30: Log-based error diagnosis."""

    def test_timeout_errors(self, monitor):
        issues = []
        monitor._diagnose_from_logs("connection timeout occurred\n", issues)
        assert any("timeout" in i.lower() for i in issues)

    def test_oom_errors(self, monitor):
        issues = []
        monitor._diagnose_from_logs("Process killed: out of memory\n", issues)
        assert any("memory" in i.lower() for i in issues)

    def test_no_errors(self, monitor):
        issues = []
        monitor._diagnose_from_logs("Everything running fine\nAll clear\n", issues)
        assert len(issues) == 0

    def test_multiple_errors(self, monitor):
        issues = []
        monitor._diagnose_from_logs("wallet error\nconnection timeout\nout of memory\n", issues)
        assert len(issues) == 3


class TestMetagraphFromLogs:
    """Test 31: Metagraph parsing from logs."""

    def test_parse_uid_from_logs(self, monitor):
        result = {"uid": None, "stake": None, "trust": None, "vtrust": None, "rank": None, "available": False}
        monitor._parse_metagraph_from_logs("Registered with uid: 42\nvtrust: 0.95\n", result)
        assert result["uid"] == 42
        assert result["vtrust"] == 0.95

    def test_parse_no_metagraph(self, monitor):
        result = {"uid": None, "stake": None, "trust": None, "vtrust": None, "rank": None, "available": False}
        monitor._parse_metagraph_from_logs("just normal logs\n", result)
        assert result["uid"] is None
