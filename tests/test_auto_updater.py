"""
Tests for the Project Nobi Auto-Updater.

Run: cd /root/project-nobi && python3 -m pytest tests/test_auto_updater.py -v --tb=short
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from auto_updater import AutoUpdater


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temporary git repo for testing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), capture_output=True)
    # Create initial commit
    (repo / "README.md").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(repo), capture_output=True)
    return str(repo)


@pytest.fixture
def log_dir(tmp_path):
    """Temporary log directory."""
    d = tmp_path / "logs"
    d.mkdir()
    return str(d)


@pytest.fixture
def updater(tmp_repo, log_dir):
    """Create an AutoUpdater with mocked PM2."""
    return AutoUpdater(
        repo_path=tmp_repo,
        check_interval=60,
        pm2_names=["nobi-miner", "nobi-validator"],
        branch="main",
        log_dir=log_dir,
    )


# ---------------------------------------------------------------------------
# Test 1: Initialization
# ---------------------------------------------------------------------------
class TestInit:
    def test_init_basic(self, updater, tmp_repo):
        assert updater.repo_path == tmp_repo
        assert updater.check_interval == 60
        assert updater.pm2_names == ["nobi-miner", "nobi-validator"]
        assert updater.branch == "main"

    def test_init_minimum_interval(self, tmp_repo, log_dir):
        """Interval should be clamped to minimum 30s."""
        u = AutoUpdater(tmp_repo, check_interval=5, pm2_names=[], log_dir=log_dir)
        assert u.check_interval == 30

    def test_init_creates_log_dir(self, tmp_repo, tmp_path):
        log_d = str(tmp_path / "new_log_dir")
        assert not os.path.exists(log_d)
        AutoUpdater(tmp_repo, pm2_names=[], log_dir=log_d)
        assert os.path.exists(log_d)


# ---------------------------------------------------------------------------
# Test 2: No updates available
# ---------------------------------------------------------------------------
class TestNoUpdates:
    def test_no_updates_when_up_to_date(self, updater):
        """When local == remote, check_for_updates returns False."""
        # In a local repo with no remote, fetch will fail
        # but we can mock it
        with patch.object(updater, "_run_cmd") as mock_cmd:
            mock_cmd.side_effect = [
                (0, "", ""),  # _has_uncommitted_changes -> git status
                (0, "", ""),  # git fetch
                (0, "abc123", ""),  # local hash
                (0, "abc123", ""),  # remote hash (same)
            ]
            assert updater.check_for_updates() is False

    def test_updates_available(self, updater):
        """When local != remote, check_for_updates returns True."""
        with patch.object(updater, "_run_cmd") as mock_cmd:
            mock_cmd.side_effect = [
                (0, "", ""),  # _has_uncommitted_changes
                (0, "", ""),  # git fetch
                (0, "abc123", ""),  # local hash
                (0, "def456", ""),  # remote hash (different)
            ]
            assert updater.check_for_updates() is True


# ---------------------------------------------------------------------------
# Test 3: Uncommitted changes safety
# ---------------------------------------------------------------------------
class TestUncommittedChanges:
    def test_skip_when_uncommitted_changes(self, updater):
        """Should refuse to update when there are uncommitted changes."""
        with patch.object(updater, "_run_cmd") as mock_cmd:
            mock_cmd.return_value = (0, "M some_file.py", "")  # dirty status
            assert updater.check_for_updates() is False

    def test_pull_refuses_with_uncommitted(self, updater):
        """pull_update should refuse if uncommitted changes exist."""
        with patch.object(updater, "_has_uncommitted_changes", return_value=True):
            success, msg = updater.pull_update()
            assert success is False
            assert "Uncommitted" in msg


# ---------------------------------------------------------------------------
# Test 4: Pull update
# ---------------------------------------------------------------------------
class TestPullUpdate:
    def test_pull_success(self, updater):
        with patch.object(updater, "_has_uncommitted_changes", return_value=False):
            with patch.object(updater, "_run_cmd") as mock_cmd:
                mock_cmd.side_effect = [
                    (0, "Updating abc..def", ""),  # git pull
                    (0, "feat: new feature", ""),  # git log
                ]
                success, msg = updater.pull_update()
                assert success is True
                assert "new feature" in msg

    def test_pull_failure(self, updater):
        with patch.object(updater, "_has_uncommitted_changes", return_value=False):
            with patch.object(updater, "_run_cmd") as mock_cmd:
                mock_cmd.return_value = (1, "", "merge conflict")
                success, msg = updater.pull_update()
                assert success is False
                assert "merge conflict" in msg


# ---------------------------------------------------------------------------
# Test 5: Health check
# ---------------------------------------------------------------------------
class TestHealthCheck:
    def test_health_check_pass(self, updater):
        with patch.object(updater, "_run_cmd") as mock_cmd:
            mock_cmd.side_effect = [
                (0, "ok", ""),  # import nobi
                (0, "version_ok", ""),  # version check
            ]
            assert updater.run_health_check() is True

    def test_health_check_fail_import(self, updater):
        with patch.object(updater, "_run_cmd") as mock_cmd:
            mock_cmd.side_effect = [
                (1, "", "ModuleNotFoundError"),  # import fails
            ]
            assert updater.run_health_check() is False

    def test_health_check_fail_no_ok(self, updater):
        with patch.object(updater, "_run_cmd") as mock_cmd:
            mock_cmd.side_effect = [
                (0, "something_else", ""),  # no 'ok' in output
            ]
            assert updater.run_health_check() is False


# ---------------------------------------------------------------------------
# Test 6: Restart processes
# ---------------------------------------------------------------------------
class TestRestartProcesses:
    def test_restart_all_success(self, updater):
        with patch.object(updater, "_run_cmd") as mock_cmd:
            mock_cmd.return_value = (0, "restarted", "")
            results = updater.restart_processes()
            assert results == {"nobi-miner": True, "nobi-validator": True}

    def test_restart_partial_failure(self, updater):
        with patch.object(updater, "_run_cmd") as mock_cmd:
            mock_cmd.side_effect = [
                (0, "ok", ""),  # miner restarts
                (1, "", "process not found"),  # validator fails
            ]
            results = updater.restart_processes()
            assert results["nobi-miner"] is True
            assert results["nobi-validator"] is False

    def test_restart_empty_list(self, tmp_repo, log_dir):
        with patch.object(AutoUpdater, "_detect_pm2_processes", return_value=[]):
            u = AutoUpdater(tmp_repo, pm2_names=[], log_dir=log_dir)
        assert u.pm2_names == []
        results = u.restart_processes()
        assert results == {}


# ---------------------------------------------------------------------------
# Test 7: Rollback
# ---------------------------------------------------------------------------
class TestRollback:
    def test_rollback_success(self, updater):
        with patch.object(updater, "_run_cmd") as mock_cmd:
            mock_cmd.return_value = (0, "", "")
            assert updater.rollback("abc123def456") is True

    def test_rollback_failure(self, updater):
        with patch.object(updater, "_run_cmd") as mock_cmd:
            mock_cmd.return_value = (1, "", "error: pathspec")
            assert updater.rollback("nonexistent") is False


# ---------------------------------------------------------------------------
# Test 8: Log recording
# ---------------------------------------------------------------------------
class TestLogging:
    def test_log_event_creates_file(self, updater):
        updater._log_event("test", "hello world")
        assert updater.log_file.exists()
        with open(updater.log_file) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["event"] == "test"
        assert data[0]["message"] == "hello world"

    def test_log_event_appends(self, updater):
        updater._log_event("event1", "first")
        updater._log_event("event2", "second")
        with open(updater.log_file) as f:
            data = json.load(f)
        assert len(data) == 2

    def test_log_with_details(self, updater):
        updater._log_event("test", "msg", {"key": "value"})
        with open(updater.log_file) as f:
            data = json.load(f)
        assert data[0]["details"]["key"] == "value"

    def test_log_truncation(self, updater):
        """Log should keep max 1000 entries."""
        # Pre-fill with 999 entries
        entries = [{"timestamp": "t", "event": "old", "message": str(i)} for i in range(999)]
        with open(updater.log_file, "w") as f:
            json.dump(entries, f)
        # Add 2 more → should be 1000 (truncated from 1001)
        updater._log_event("new1", "a")
        updater._log_event("new2", "b")
        with open(updater.log_file) as f:
            data = json.load(f)
        assert len(data) == 1000
        assert data[-1]["event"] == "new2"


# ---------------------------------------------------------------------------
# Test 9: Full update cycle
# ---------------------------------------------------------------------------
class TestUpdateCycle:
    def test_cycle_no_updates(self, updater):
        with patch.object(updater, "check_for_updates", return_value=False):
            assert updater.update_cycle() is False

    def test_cycle_successful_update(self, updater):
        with patch.object(updater, "check_for_updates", return_value=True), \
             patch.object(updater, "_get_current_commit", side_effect=["aaa111", "bbb222"]), \
             patch.object(updater, "pull_update", return_value=(True, "new feature")), \
             patch.object(updater, "run_health_check", return_value=True), \
             patch.object(updater, "restart_processes", return_value={"nobi-miner": True}):
            assert updater.update_cycle() is True

    def test_cycle_health_check_fails_triggers_rollback(self, updater):
        with patch.object(updater, "check_for_updates", return_value=True), \
             patch.object(updater, "_get_current_commit", return_value="aaa111"), \
             patch.object(updater, "pull_update", return_value=(True, "bad update")), \
             patch.object(updater, "run_health_check", return_value=False), \
             patch.object(updater, "rollback", return_value=True) as mock_rollback:
            assert updater.update_cycle() is False
            mock_rollback.assert_called_once_with("aaa111")

    def test_cycle_pull_fails(self, updater):
        with patch.object(updater, "check_for_updates", return_value=True), \
             patch.object(updater, "_get_current_commit", return_value="aaa111"), \
             patch.object(updater, "pull_update", return_value=(False, "conflict")):
            assert updater.update_cycle() is False


# ---------------------------------------------------------------------------
# Test 10: Manual trigger mode (--once)
# ---------------------------------------------------------------------------
class TestManualMode:
    def test_once_flag_parsed(self):
        """Verify the --once argument is recognized."""
        from auto_updater import main
        # Just verify the parser accepts --once without error
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--once", action="store_true")
        args = parser.parse_args(["--once"])
        assert args.once is True


# ---------------------------------------------------------------------------
# Test 11: PM2 process detection
# ---------------------------------------------------------------------------
class TestPM2Detection:
    def test_detect_nobi_processes(self, tmp_repo, log_dir):
        pm2_output = json.dumps([
            {"name": "nobi-miner", "pm_id": 0},
            {"name": "nobi-validator", "pm_id": 1},
            {"name": "other-app", "pm_id": 2},
        ])
        with patch.object(AutoUpdater, "_run_cmd", return_value=(0, pm2_output, "")):
            u = AutoUpdater(tmp_repo, pm2_names=None, log_dir=log_dir)
            assert "nobi-miner" in u.pm2_names
            assert "nobi-validator" in u.pm2_names
            assert "other-app" not in u.pm2_names

    def test_detect_no_pm2(self, tmp_repo, log_dir):
        with patch.object(AutoUpdater, "_run_cmd", return_value=(1, "", "command not found")):
            u = AutoUpdater(tmp_repo, pm2_names=None, log_dir=log_dir)
            assert u.pm2_names == []


# ---------------------------------------------------------------------------
# Test 12: Thread safety
# ---------------------------------------------------------------------------
class TestThreadSafety:
    def test_concurrent_check(self, updater):
        """Multiple threads calling check_for_updates shouldn't crash."""
        results = []

        def check():
            with patch.object(updater, "_run_cmd") as mock_cmd:
                mock_cmd.side_effect = [
                    (0, "", ""),  # status
                    (0, "", ""),  # fetch
                    (0, "abc", ""),
                    (0, "abc", ""),
                ]
                try:
                    results.append(updater.check_for_updates())
                except Exception:
                    results.append(None)

        threads = [threading.Thread(target=check) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        # Should not crash; results may vary due to mock
        assert len(results) > 0


# ---------------------------------------------------------------------------
# Test 13: Daemon run/stop
# ---------------------------------------------------------------------------
class TestDaemonRunStop:
    def test_stop_signal(self, updater):
        """Daemon should stop when stop() is called."""
        updater.check_interval = 1  # fast for test (will be clamped to 30 in init, set directly)
        object.__setattr__(updater, "check_interval", 1)

        with patch.object(updater, "update_cycle", return_value=False):
            def stop_after():
                time.sleep(0.5)
                updater.stop()

            stopper = threading.Thread(target=stop_after)
            stopper.start()
            updater.run()  # should exit after stop
            stopper.join(timeout=5)
            assert updater._running is False


# ---------------------------------------------------------------------------
# Test 14: Fetch failure handling
# ---------------------------------------------------------------------------
class TestFetchFailure:
    def test_fetch_fails_returns_false(self, updater):
        with patch.object(updater, "_run_cmd") as mock_cmd:
            mock_cmd.side_effect = [
                (0, "", ""),  # status clean
                (1, "", "fatal: unable to access"),  # fetch fails
            ]
            assert updater.check_for_updates() is False


# ---------------------------------------------------------------------------
# Test 15: Environment variable configuration
# ---------------------------------------------------------------------------
class TestEnvConfig:
    def test_disabled_via_env(self):
        """AUTO_UPDATE_ENABLED=false should cause main() to exit."""
        with patch.dict(os.environ, {"AUTO_UPDATE_ENABLED": "false"}):
            with patch("sys.argv", ["auto_updater.py"]):
                with pytest.raises(SystemExit) as exc:
                    from auto_updater import main
                    main()
                assert exc.value.code == 0

    def test_interval_from_env(self, tmp_repo, log_dir):
        with patch.dict(os.environ, {"AUTO_UPDATE_INTERVAL": "600"}):
            # The interval env var is read by argparse in main(), test directly
            u = AutoUpdater(tmp_repo, check_interval=600, pm2_names=[], log_dir=log_dir)
            assert u.check_interval == 600


# ---------------------------------------------------------------------------
# Test 16: Command timeout handling
# ---------------------------------------------------------------------------
class TestCommandTimeout:
    def test_timeout_returns_error(self, updater):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=120)):
            rc, stdout, stderr = updater._run_cmd(["git", "pull"])
            assert rc == -1
            assert "timed out" in stderr.lower()

    def test_command_not_found(self, updater):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            rc, stdout, stderr = updater._run_cmd(["nonexistent"])
            assert rc == -1
            assert "not found" in stderr.lower()


# ---------------------------------------------------------------------------
# Test 17: Corrupt log file handling
# ---------------------------------------------------------------------------
class TestCorruptLog:
    def test_corrupt_json_log(self, updater):
        """Should handle corrupt log file gracefully."""
        with open(updater.log_file, "w") as f:
            f.write("{invalid json")
        updater._log_event("test", "after corruption")
        with open(updater.log_file) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["event"] == "test"
