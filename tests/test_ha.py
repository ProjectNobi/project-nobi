"""
Tests for the High-Availability Validator Failover system.
"""

import json
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from nobi.ha.failover import ValidatorFailover


# ─── Helpers ─────────────────────────────────────────────────────────

def _make_pm2_jlist(name: str, status: str = "online", restarts: int = 0, uptime_ms: float = None):
    """Build a fake PM2 jlist JSON string for one process."""
    if uptime_ms is None:
        uptime_ms = time.time() * 1000 - 3600_000  # 1 hour ago
    return json.dumps([{
        "name": name,
        "pm_id": 0,
        "pm2_env": {
            "status": status,
            "restart_time": restarts,
            "pm_uptime": uptime_ms,
        },
    }])


def _make_empty_jlist():
    return json.dumps([])


def _make_weight_logs():
    return "2026-03-20T10:00:00 | set_weights successfully for netuid 272"


def _make_no_weight_logs():
    return "2026-03-20T10:00:00 | Starting validator..."


def _make_subprocess_result(rc=0, stdout="", stderr=""):
    result = MagicMock()
    result.returncode = rc
    result.stdout = stdout
    result.stderr = stderr
    return result


class FakeFailover(ValidatorFailover):
    """Failover with injectable health check results for deterministic testing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._primary_health_override = None
        self._backup_health_override = None

    def _check_host_health(self, host):
        if host == self.primary_host and self._primary_health_override is not None:
            return self._primary_health_override
        if host == self.backup_host and self._backup_health_override is not None:
            return self._backup_health_override
        return super()._check_host_health(host)

    def set_primary_health(self, online=True, crash_looping=False, setting_weights=True):
        self._primary_health_override = {
            "online": online,
            "status": "online" if online else "stopped",
            "uptime": 3600.0 if online else 0.0,
            "restarts": 0,
            "crash_looping": crash_looping,
            "setting_weights": setting_weights,
            "reachable": True,
            "error": None,
        }

    def set_backup_health(self, online=True, crash_looping=False, setting_weights=True):
        self._backup_health_override = {
            "online": online,
            "status": "online" if online else "stopped",
            "uptime": 3600.0 if online else 0.0,
            "restarts": 0,
            "crash_looping": crash_looping,
            "setting_weights": setting_weights,
            "reachable": True,
            "error": None,
        }


@pytest.fixture
def tmp_log(tmp_path):
    return str(tmp_path / "ha_failover.json")


@pytest.fixture
def failover(tmp_log):
    return FakeFailover(
        primary_host="localhost",
        backup_host="server4",
        pm2_name="nobi-validator",
        primary_down_threshold=300,
        recovery_cooldown=600,
        log_file=tmp_log,
    )


# ─── Basic construction & properties ────────────────────────────────

class TestInit:
    def test_default_state_is_normal(self, failover):
        assert failover.state == ValidatorFailover.STATE_NORMAL

    def test_hosts_stored(self, failover):
        assert failover.primary_host == "localhost"
        assert failover.backup_host == "server4"

    def test_pm2_name_stored(self, failover):
        assert failover.pm2_name == "nobi-validator"

    def test_log_file_created(self, failover):
        assert failover.log_file.parent.exists()

    def test_custom_thresholds(self, tmp_log):
        f = ValidatorFailover(
            "h1", "h2", primary_down_threshold=120, recovery_cooldown=300,
            log_file=tmp_log,
        )
        assert f.primary_down_threshold == 120
        assert f.recovery_cooldown == 300


# ─── Health check helpers ────────────────────────────────────────────

class TestHealthChecks:
    def test_check_primary_healthy(self, failover):
        failover.set_primary_health(online=True)
        assert failover.check_primary() is True

    def test_check_primary_down(self, failover):
        failover.set_primary_health(online=False)
        assert failover.check_primary() is False

    def test_check_primary_crash_looping(self, failover):
        failover.set_primary_health(online=True, crash_looping=True)
        assert failover.check_primary() is False

    def test_check_backup_healthy(self, failover):
        failover.set_backup_health(online=True)
        assert failover.check_backup() is True

    def test_check_backup_down(self, failover):
        failover.set_backup_health(online=False)
        assert failover.check_backup() is False

    def test_check_backup_crash_looping(self, failover):
        failover.set_backup_health(online=True, crash_looping=True)
        assert failover.check_backup() is False


# ─── is_local helper ────────────────────────────────────────────────

class TestIsLocal:
    def test_localhost(self, failover):
        assert failover._is_local("localhost") is True

    def test_ipv4_loopback(self, failover):
        assert failover._is_local("127.0.0.1") is True

    def test_ipv6_loopback(self, failover):
        assert failover._is_local("::1") is True

    def test_remote_host(self, failover):
        assert failover._is_local("server4") is False


# ─── Auto failover: Normal state ────────────────────────────────────

class TestAutoFailoverNormal:
    def test_primary_healthy_no_action(self, failover):
        failover.set_primary_health(online=True)
        failover.set_backup_health(online=False)
        result = failover.auto_failover()
        assert result["action"] == "none"
        assert result["primary_healthy"] is True
        assert failover.state == ValidatorFailover.STATE_NORMAL

    def test_primary_down_starts_monitoring(self, failover):
        failover.set_primary_health(online=False)
        failover.set_backup_health(online=False)
        result = failover.auto_failover()
        assert result["action"] == "monitoring"
        assert failover.state == ValidatorFailover.STATE_NORMAL  # Not yet failover
        assert failover._primary_down_since is not None

    @patch.object(FakeFailover, "promote_backup", return_value=True)
    def test_primary_down_past_threshold_triggers_failover(self, mock_promote, failover):
        failover.set_primary_health(online=False)
        failover.set_backup_health(online=True)
        # Simulate primary down since 10 minutes ago
        failover._primary_down_since = time.time() - 600
        result = failover.auto_failover()
        assert result["action"] == "failover"
        assert failover.state == ValidatorFailover.STATE_FAILOVER
        mock_promote.assert_called_once()

    @patch.object(FakeFailover, "promote_backup", return_value=False)
    def test_primary_down_backup_promote_fails_goes_degraded(self, mock_promote, failover):
        failover.set_primary_health(online=False)
        failover.set_backup_health(online=False)
        failover._primary_down_since = time.time() - 600
        result = failover.auto_failover()
        assert result["action"] == "alert"
        assert failover.state == ValidatorFailover.STATE_DEGRADED

    def test_primary_recovers_before_threshold(self, failover):
        failover.set_primary_health(online=False)
        failover.auto_failover()  # Start monitoring
        assert failover._primary_down_since is not None

        failover.set_primary_health(online=True)
        result = failover.auto_failover()
        assert result["action"] == "none"
        assert failover._primary_down_since is None  # Reset


# ─── Auto failover: Failover state ──────────────────────────────────

class TestAutoFailoverFailoverState:
    @patch.object(FakeFailover, "promote_backup", return_value=True)
    def test_primary_recovers_enters_both_running(self, mock_promote, failover):
        failover.set_primary_health(online=False)
        failover.set_backup_health(online=True)
        failover._primary_down_since = time.time() - 600
        failover.auto_failover()  # Trigger failover
        assert failover.state == ValidatorFailover.STATE_FAILOVER

        failover.set_primary_health(online=True)
        result = failover.auto_failover()
        assert result["action"] == "recovery"
        assert failover.state == ValidatorFailover.STATE_BOTH_RUNNING

    def test_backup_also_down_goes_degraded(self, failover):
        failover._state = ValidatorFailover.STATE_FAILOVER
        failover.set_primary_health(online=False)
        failover.set_backup_health(online=False)
        result = failover.auto_failover()
        assert result["action"] == "alert"
        assert failover.state == ValidatorFailover.STATE_DEGRADED

    def test_backup_still_serving(self, failover):
        failover._state = ValidatorFailover.STATE_FAILOVER
        failover.set_primary_health(online=False)
        failover.set_backup_health(online=True)
        result = failover.auto_failover()
        assert result["action"] == "none"
        assert "Backup is serving" in result["message"]


# ─── Auto failover: Both running (cooldown) ─────────────────────────

class TestAutoFailoverBothRunning:
    @patch.object(FakeFailover, "_stop_backup", return_value=True)
    def test_cooldown_complete_stops_backup(self, mock_stop, failover):
        failover._state = ValidatorFailover.STATE_BOTH_RUNNING
        failover._primary_recovered_since = time.time() - 700  # Past 600s cooldown
        failover.set_primary_health(online=True)
        failover.set_backup_health(online=True)
        result = failover.auto_failover()
        assert result["action"] == "recovery"
        assert failover.state == ValidatorFailover.STATE_NORMAL
        mock_stop.assert_called_once()

    def test_cooldown_not_yet_complete(self, failover):
        failover._state = ValidatorFailover.STATE_BOTH_RUNNING
        failover._primary_recovered_since = time.time() - 100  # Only 100s
        failover.set_primary_health(online=True)
        failover.set_backup_health(online=True)
        result = failover.auto_failover()
        assert result["action"] == "cooldown"
        assert failover.state == ValidatorFailover.STATE_BOTH_RUNNING

    def test_primary_relapses_during_cooldown(self, failover):
        failover._state = ValidatorFailover.STATE_BOTH_RUNNING
        failover._primary_recovered_since = time.time() - 100
        failover.set_primary_health(online=False)
        failover.set_backup_health(online=True)
        result = failover.auto_failover()
        assert result["action"] == "failover"
        assert failover.state == ValidatorFailover.STATE_FAILOVER
        assert failover._primary_recovered_since is None


# ─── Auto failover: Degraded state ──────────────────────────────────

class TestAutoFailoverDegraded:
    def test_primary_recovers_from_degraded(self, failover):
        failover._state = ValidatorFailover.STATE_DEGRADED
        failover.set_primary_health(online=True)
        failover.set_backup_health(online=False)
        result = failover.auto_failover()
        assert result["action"] == "recovery"
        assert failover.state == ValidatorFailover.STATE_NORMAL

    def test_backup_recovers_from_degraded(self, failover):
        failover._state = ValidatorFailover.STATE_DEGRADED
        failover.set_primary_health(online=False)
        failover.set_backup_health(online=True)
        result = failover.auto_failover()
        assert result["action"] == "failover"
        assert failover.state == ValidatorFailover.STATE_FAILOVER

    @patch.object(FakeFailover, "promote_backup", return_value=False)
    def test_still_degraded_tries_promotion(self, mock_promote, failover):
        failover._state = ValidatorFailover.STATE_DEGRADED
        failover.set_primary_health(online=False)
        failover.set_backup_health(online=False)
        result = failover.auto_failover()
        assert result["action"] == "alert"
        assert "degraded" in result["message"].lower() or "CRITICAL" in result["message"]
        mock_promote.assert_called_once()


# ─── get_status ──────────────────────────────────────────────────────

class TestGetStatus:
    def test_status_both_online(self, failover):
        failover.set_primary_health(online=True)
        failover.set_backup_health(online=True)
        status = failover.get_status()
        assert status["active"] == "both"
        assert status["state"] == ValidatorFailover.STATE_NORMAL

    def test_status_primary_only(self, failover):
        failover.set_primary_health(online=True)
        failover.set_backup_health(online=False)
        status = failover.get_status()
        assert status["active"] == "primary"

    def test_status_backup_only(self, failover):
        failover.set_primary_health(online=False)
        failover.set_backup_health(online=True)
        status = failover.get_status()
        assert status["active"] == "backup"

    def test_status_none_online(self, failover):
        failover.set_primary_health(online=False)
        failover.set_backup_health(online=False)
        status = failover.get_status()
        assert status["active"] == "none"

    def test_status_has_timestamp(self, failover):
        failover.set_primary_health(online=True)
        failover.set_backup_health(online=True)
        status = failover.get_status()
        assert "timestamp" in status

    def test_status_tracks_down_since(self, failover):
        failover._primary_down_since = time.time() - 60
        failover.set_primary_health(online=True)
        failover.set_backup_health(online=False)
        status = failover.get_status()
        assert status["primary_down_since"] is not None


# ─── Event logging and persistence ──────────────────────────────────

class TestLogging:
    def test_events_logged(self, failover):
        failover._log_event("test_event", "Test message")
        assert len(failover._events) == 1
        assert failover._events[0]["type"] == "test_event"

    def test_events_persisted_to_file(self, failover, tmp_log):
        failover._log_event("test_event", "Persisted!")
        assert Path(tmp_log).exists()
        data = json.loads(Path(tmp_log).read_text())
        assert len(data["events"]) == 1

    def test_load_state_restores(self, tmp_log):
        # Save some state
        f1 = FakeFailover("localhost", "server4", log_file=tmp_log)
        f1._state = ValidatorFailover.STATE_FAILOVER
        f1._primary_down_since = 1000.0
        f1._log_event("saved", "state saved")

        # Load in new instance
        f2 = FakeFailover("localhost", "server4", log_file=tmp_log)
        f2.load_state()
        assert f2.state == ValidatorFailover.STATE_FAILOVER
        assert f2._primary_down_since == 1000.0

    def test_load_state_missing_file(self, tmp_log):
        f = FakeFailover("localhost", "server4", log_file=tmp_log + ".nonexist")
        f.load_state()  # Should not raise
        assert f.state == ValidatorFailover.STATE_NORMAL


# ─── Promote / Demote with mocked subprocess ────────────────────────

class TestPromoteDemote:
    @patch("subprocess.run")
    def test_promote_backup_restart_success(self, mock_run, tmp_log):
        mock_run.return_value = _make_subprocess_result(rc=0, stdout="restarted")
        f = ValidatorFailover("localhost", "server4", log_file=tmp_log)
        assert f.promote_backup() is True

    @patch("subprocess.run")
    def test_promote_backup_restart_fails_tries_start(self, mock_run, tmp_log):
        # First call (restart) fails, second (start) succeeds
        mock_run.side_effect = [
            _make_subprocess_result(rc=1, stderr="not found"),
            _make_subprocess_result(rc=0, stdout="started"),
        ]
        f = ValidatorFailover("localhost", "server4", log_file=tmp_log)
        assert f.promote_backup() is True
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_promote_backup_both_fail(self, mock_run, tmp_log):
        mock_run.return_value = _make_subprocess_result(rc=1, stderr="error")
        f = ValidatorFailover("localhost", "server4", log_file=tmp_log)
        assert f.promote_backup() is False

    @patch("subprocess.run")
    def test_demote_primary_success(self, mock_run, tmp_log):
        mock_run.return_value = _make_subprocess_result(rc=0, stdout="stopped")
        f = ValidatorFailover("localhost", "server4", log_file=tmp_log)
        assert f.demote_primary() is True

    @patch("subprocess.run")
    def test_demote_primary_failure(self, mock_run, tmp_log):
        mock_run.return_value = _make_subprocess_result(rc=1, stderr="error")
        f = ValidatorFailover("localhost", "server4", log_file=tmp_log)
        assert f.demote_primary() is False


# ─── Raw _check_host_health with mocked subprocess ──────────────────

class TestRawHealthCheck:
    @patch("subprocess.run")
    def test_healthy_host(self, mock_run, tmp_log):
        jlist = _make_pm2_jlist("nobi-validator", "online", restarts=0)
        mock_run.side_effect = [
            _make_subprocess_result(rc=0, stdout=jlist),  # pm2 jlist
            _make_subprocess_result(rc=0, stdout=_make_weight_logs()),  # pm2 logs
        ]
        f = ValidatorFailover("localhost", "server4", pm2_name="nobi-validator", log_file=tmp_log)
        h = f._check_host_health("localhost")
        assert h["online"] is True
        assert h["reachable"] is True
        assert h["crash_looping"] is False

    @patch("subprocess.run")
    def test_crash_looping_host(self, mock_run, tmp_log):
        # High restarts, recent uptime (process keeps restarting)
        now_ms = time.time() * 1000
        jlist = _make_pm2_jlist("nobi-validator", "online", restarts=5, uptime_ms=now_ms - 30_000)
        mock_run.side_effect = [
            _make_subprocess_result(rc=0, stdout=jlist),
            _make_subprocess_result(rc=0, stdout=""),
        ]
        f = ValidatorFailover("localhost", "server4", pm2_name="nobi-validator", log_file=tmp_log)
        h = f._check_host_health("localhost")
        assert h["crash_looping"] is True

    @patch("subprocess.run")
    def test_unreachable_host(self, mock_run, tmp_log):
        mock_run.return_value = _make_subprocess_result(rc=1, stderr="Connection refused")
        f = ValidatorFailover("localhost", "server4", pm2_name="nobi-validator", log_file=tmp_log)
        h = f._check_host_health("server4")
        assert h["reachable"] is False
        assert h["online"] is False

    @patch("subprocess.run")
    def test_process_not_found(self, mock_run, tmp_log):
        mock_run.return_value = _make_subprocess_result(rc=0, stdout=_make_empty_jlist())
        f = ValidatorFailover("localhost", "server4", pm2_name="nobi-validator", log_file=tmp_log)
        h = f._check_host_health("localhost")
        assert h["status"] == "not_found"
        assert h["online"] is False

    @patch("subprocess.run")
    def test_weight_setting_detected(self, mock_run, tmp_log):
        jlist = _make_pm2_jlist("nobi-validator", "online")
        mock_run.side_effect = [
            _make_subprocess_result(rc=0, stdout=jlist),
            _make_subprocess_result(rc=0, stdout=_make_weight_logs()),
        ]
        f = ValidatorFailover("localhost", "server4", pm2_name="nobi-validator", log_file=tmp_log)
        h = f._check_host_health("localhost")
        assert h["setting_weights"] is True

    @patch("subprocess.run")
    def test_no_weight_setting(self, mock_run, tmp_log):
        jlist = _make_pm2_jlist("nobi-validator", "online")
        mock_run.side_effect = [
            _make_subprocess_result(rc=0, stdout=jlist),
            _make_subprocess_result(rc=0, stdout=_make_no_weight_logs()),
        ]
        f = ValidatorFailover("localhost", "server4", pm2_name="nobi-validator", log_file=tmp_log)
        h = f._check_host_health("localhost")
        assert h["setting_weights"] is False


# ─── Full failover scenario (end-to-end with FakeFailover) ──────────

class TestEndToEndScenario:
    @patch.object(FakeFailover, "promote_backup", return_value=True)
    @patch.object(FakeFailover, "_stop_backup", return_value=True)
    def test_full_lifecycle(self, mock_stop, mock_promote, failover):
        """Test: normal → monitoring → failover → recovery → cooldown → normal."""
        # 1. Normal — primary healthy
        failover.set_primary_health(online=True)
        failover.set_backup_health(online=False)
        r = failover.auto_failover()
        assert r["action"] == "none"
        assert failover.state == ValidatorFailover.STATE_NORMAL

        # 2. Primary goes down — monitoring starts
        failover.set_primary_health(online=False)
        r = failover.auto_failover()
        assert r["action"] == "monitoring"

        # 3. Primary still down past threshold → failover
        failover._primary_down_since = time.time() - 600
        failover.set_backup_health(online=True)
        r = failover.auto_failover()
        assert r["action"] == "failover"
        assert failover.state == ValidatorFailover.STATE_FAILOVER

        # 4. Primary recovers → both running
        failover.set_primary_health(online=True)
        r = failover.auto_failover()
        assert r["action"] == "recovery"
        assert failover.state == ValidatorFailover.STATE_BOTH_RUNNING

        # 5. Cooldown not yet done
        r = failover.auto_failover()
        assert r["action"] == "cooldown"

        # 6. Cooldown done → back to normal
        failover._primary_recovered_since = time.time() - 700
        r = failover.auto_failover()
        assert r["action"] == "recovery"
        assert failover.state == ValidatorFailover.STATE_NORMAL
        mock_stop.assert_called_once()

    def test_never_zero_validators_invariant(self, failover):
        """In degraded state, system tries to start backup — never accepts zero."""
        failover._state = ValidatorFailover.STATE_DEGRADED
        failover.set_primary_health(online=False)
        failover.set_backup_health(online=False)

        with patch.object(failover, "promote_backup", return_value=False) as mock:
            r = failover.auto_failover()
            assert r["action"] == "alert"
            mock.assert_called_once()  # Always tries to recover
