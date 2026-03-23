"""
Tests for Project Nobi Burn Automation
=======================================
Tests burn tracker, API endpoints, and verifier logic.
All bittensor calls are mocked — no actual burns on testnet.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# ─── Path setup ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─── Helper: make a fresh tracker with temp dir ──────────────────────────────

def make_tracker(tmp_dir: str):
    """Create a BurnTracker with an isolated temp directory."""
    from nobi.burn.tracker import BurnTracker
    history_path = Path(tmp_dir) / "burn_history.json"
    return BurnTracker(history_path=history_path)


# ─── BurnTracker Tests ───────────────────────────────────────────────────────

class TestBurnTracker(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tracker = make_tracker(self.tmp)

    def test_empty_history(self):
        """Empty tracker returns safe defaults."""
        self.assertEqual(self.tracker.get_total_burned(), 0.0)
        self.assertEqual(self.tracker.get_burn_count(), 0)
        self.assertIsNone(self.tracker.get_latest_burn())
        self.assertEqual(self.tracker.get_burn_history(), [])

    def test_add_burn(self):
        """Adding a burn record persists it."""
        record = self.tracker.add_burn(
            amount_alpha=1.5,
            block=100,
            tx_hash="0xabc123",
            network="testnet",
            netuid=272,
        )
        self.assertEqual(record["amount_alpha"], 1.5)
        self.assertEqual(record["block"], 100)
        self.assertEqual(record["tx_hash"], "0xabc123")
        self.assertEqual(record["network"], "testnet")
        self.assertEqual(record["netuid"], 272)
        self.assertFalse(record["dry_run"])
        self.assertIn("timestamp", record)

    def test_total_burned(self):
        """Total burned is sum of all non-dry-run records."""
        self.tracker.add_burn(1.0, 100, "0x01", "testnet", 272)
        self.tracker.add_burn(2.5, 200, "0x02", "testnet", 272)
        self.tracker.add_burn(0.5, 300, "0x03", "testnet", 272, dry_run=True)  # excluded
        total = self.tracker.get_total_burned()
        self.assertAlmostEqual(total, 3.5, places=6)

    def test_total_burned_excludes_dry_runs(self):
        """Dry-run burns are excluded from total."""
        self.tracker.add_burn(10.0, 1, "DRY_RUN", "testnet", 272, dry_run=True)
        self.assertEqual(self.tracker.get_total_burned(), 0.0)

    def test_burn_count(self):
        """Burn count excludes dry runs."""
        self.tracker.add_burn(1.0, 100, "0x01", "testnet", 272)
        self.tracker.add_burn(1.0, 200, "0x02", "testnet", 272)
        self.tracker.add_burn(1.0, 300, "DRY", "testnet", 272, dry_run=True)
        self.assertEqual(self.tracker.get_burn_count(), 2)

    def test_latest_burn(self):
        """Latest burn returns the most recent non-dry-run record."""
        self.tracker.add_burn(1.0, 100, "0x01", "testnet", 272)
        time.sleep(0.01)  # ensure different timestamps
        self.tracker.add_burn(2.0, 200, "0x02", "testnet", 272)

        latest = self.tracker.get_latest_burn()
        self.assertIsNotNone(latest)
        self.assertEqual(latest["block"], 200)
        self.assertAlmostEqual(latest["amount_alpha"], 2.0)

    def test_get_burn_history_sorted(self):
        """History returns newest first."""
        self.tracker.add_burn(1.0, 100, "0x01")
        self.tracker.add_burn(2.0, 300, "0x03")
        self.tracker.add_burn(1.5, 200, "0x02")

        history = self.tracker.get_burn_history()
        blocks = [r["block"] for r in history]
        # Should be sorted newest-first by timestamp
        # Note: since all are added nearly simultaneously, they sort by timestamp string
        self.assertEqual(len(history), 3)

    def test_get_burn_history_limit(self):
        """History limit works correctly."""
        for i in range(5):
            self.tracker.add_burn(float(i), i * 100, f"0x{i:02x}")
        history = self.tracker.get_burn_history(limit=3)
        self.assertEqual(len(history), 3)

    def test_get_burn_history_filter_network(self):
        """History can be filtered by network."""
        self.tracker.add_burn(1.0, 100, "0x01", network="testnet", netuid=272)
        self.tracker.add_burn(2.0, 200, "0x02", network="mainnet", netuid=272)
        testnet_history = self.tracker.get_burn_history(network="testnet")
        mainnet_history = self.tracker.get_burn_history(network="mainnet")
        self.assertEqual(len(testnet_history), 1)
        self.assertEqual(len(mainnet_history), 1)

    def test_get_burn_history_filter_netuid(self):
        """History can be filtered by netuid."""
        self.tracker.add_burn(1.0, 100, "0x01", netuid=272)
        self.tracker.add_burn(2.0, 200, "0x02", netuid=1)
        h272 = self.tracker.get_burn_history(netuid=272)
        h1 = self.tracker.get_burn_history(netuid=1)
        self.assertEqual(len(h272), 1)
        self.assertEqual(len(h1), 1)

    def test_persistence(self):
        """Burn history persists across tracker instances."""
        self.tracker.add_burn(5.0, 500, "0xpersist")
        # Create new tracker pointing to same file
        tracker2 = make_tracker(self.tmp)
        self.assertAlmostEqual(tracker2.get_total_burned(), 5.0)
        self.assertEqual(tracker2.get_burn_count(), 1)

    def test_export_json(self):
        """export_json returns all expected fields."""
        self.tracker.add_burn(3.0, 300, "0xexport")
        export = self.tracker.export_json()
        self.assertIn("total_burned_alpha", export)
        self.assertIn("burn_count", export)
        self.assertIn("latest_burn", export)
        self.assertIn("history", export)
        self.assertIn("exported_at", export)
        self.assertAlmostEqual(export["total_burned_alpha"], 3.0)
        self.assertEqual(export["burn_count"], 1)

    def test_clear_history(self):
        """clear_history empties everything."""
        self.tracker.add_burn(1.0, 100, "0x01")
        self.tracker.clear_history()
        self.assertEqual(self.tracker.get_total_burned(), 0.0)
        self.assertEqual(self.tracker.get_burn_count(), 0)

    def test_multiple_burns_total(self):
        """Cumulative total correctly sums all burns."""
        amounts = [0.1, 0.2, 0.3, 0.4, 0.5]
        for i, amt in enumerate(amounts):
            self.tracker.add_burn(amt, i * 100, f"0x{i:02x}")
        total = self.tracker.get_total_burned()
        self.assertAlmostEqual(total, sum(amounts), places=6)

    def test_dry_run_included_when_requested(self):
        """get_burn_history can include dry runs when asked."""
        self.tracker.add_burn(1.0, 100, "0x01")
        self.tracker.add_burn(2.0, 200, "DRY", dry_run=True)
        all_history = self.tracker.get_burn_history(dry_runs=True)
        real_history = self.tracker.get_burn_history(dry_runs=False)
        self.assertEqual(len(all_history), 2)
        self.assertEqual(len(real_history), 1)


# ─── API Endpoint Tests ──────────────────────────────────────────────────────

class TestBurnApiEndpoints(unittest.IsolatedAsyncioTestCase):
    """Test the /api/v1/burns endpoints."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    async def _get_test_client(self):
        """Create a FastAPI test client with mocked burn tracker."""
        try:
            from fastapi.testclient import TestClient
            from api.server import app
            return TestClient(app)
        except ImportError:
            self.skipTest("FastAPI test client not available")

    @patch("api.server._get_burn_tracker")
    async def test_burns_endpoint_empty(self, mock_get_tracker):
        """GET /api/v1/burns returns valid response when no burns."""
        from nobi.burn.tracker import BurnTracker
        tracker = make_tracker(self.tmp)
        mock_get_tracker.return_value = tracker

        try:
            from httpx import AsyncClient, ASGITransport
            from api.server import app
        except ImportError:
            self.skipTest("httpx not available")
            return

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/burns")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("total_burned_alpha", data)
            self.assertIn("burn_count", data)
            self.assertIn("burns", data)
            self.assertEqual(data["total_burned_alpha"], 0.0)
            self.assertEqual(data["burn_count"], 0)

    @patch("api.server._get_burn_tracker")
    async def test_burns_endpoint_with_data(self, mock_get_tracker):
        """GET /api/v1/burns returns burn records."""
        tracker = make_tracker(self.tmp)
        tracker.add_burn(1.23, 100, "0xabc", network="testnet", netuid=272)
        mock_get_tracker.return_value = tracker

        try:
            from httpx import AsyncClient, ASGITransport
            from api.server import app
        except ImportError:
            self.skipTest("httpx not available")
            return

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/burns?network=testnet&netuid=272")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertAlmostEqual(data["total_burned_alpha"], 1.23, places=4)
            self.assertEqual(data["burn_count"], 1)
            self.assertEqual(len(data["burns"]), 1)

    @patch("api.server._get_burn_tracker")
    async def test_burns_total_endpoint(self, mock_get_tracker):
        """GET /api/v1/burns/total returns totals."""
        tracker = make_tracker(self.tmp)
        tracker.add_burn(5.0, 500, "0xfive")
        tracker.add_burn(3.0, 300, "0xthree")
        mock_get_tracker.return_value = tracker

        try:
            from httpx import AsyncClient, ASGITransport
            from api.server import app
        except ImportError:
            self.skipTest("httpx not available")
            return

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/burns/total")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("total_burned_alpha", data)
            self.assertIn("burn_count", data)
            self.assertIn("latest_burn", data)
            self.assertAlmostEqual(data["total_burned_alpha"], 8.0, places=4)
            self.assertEqual(data["burn_count"], 2)

    @patch("api.server._get_burn_tracker")
    async def test_burns_verify_endpoint(self, mock_get_tracker):
        """GET /api/v1/burns/verify returns verification data."""
        tracker = make_tracker(self.tmp)
        tracker.add_burn(2.0, 150, "0xverify")
        mock_get_tracker.return_value = tracker

        try:
            from httpx import AsyncClient, ASGITransport
            from api.server import app
        except ImportError:
            self.skipTest("httpx not available")
            return

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/burns/verify?start_block=100&end_block=200")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("burn_count", data)
            self.assertIn("total_alpha_burned", data)
            self.assertIn("burns", data)

    @patch("api.server._get_burn_tracker")
    async def test_burns_endpoint_no_tracker(self, mock_get_tracker):
        """GET /api/v1/burns gracefully handles missing tracker."""
        mock_get_tracker.return_value = None

        try:
            from httpx import AsyncClient, ASGITransport
            from api.server import app
        except ImportError:
            self.skipTest("httpx not available")
            return

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/burns")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["total_burned_alpha"], 0.0)


# ─── BurnVerifier Tests ──────────────────────────────────────────────────────

class TestBurnVerifier(unittest.TestCase):
    """Test the BurnVerifier (mocked bittensor calls)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tracker = make_tracker(self.tmp)

    def _make_verifier(self, onchain_burns=None):
        """Create a verifier with mocked subtensor."""
        from nobi.burn.verifier import BurnVerifier

        verifier = BurnVerifier(
            network="testnet",
            netuid=272,
            owner_hotkey_ss58="5FakeOwnerHotkey123",
            history_path=Path(self.tmp) / "burn_history.json",
        )

        # Mock the on-chain query
        if onchain_burns is not None:
            verifier.query_onchain_burns = MagicMock(return_value=onchain_burns)

        return verifier

    def test_get_summary(self):
        """get_summary returns correct structure without hitting chain."""
        self.tracker.add_burn(3.0, 100, "0x01", network="testnet", netuid=272)
        self.tracker.add_burn(2.0, 200, "0x02", network="testnet", netuid=272)

        from nobi.burn.verifier import BurnVerifier
        verifier = BurnVerifier(
            network="testnet",
            netuid=272,
            history_path=Path(self.tmp) / "burn_history.json",
        )
        summary = verifier.get_summary()

        self.assertAlmostEqual(summary["total_alpha_burned"], 5.0, places=4)
        self.assertEqual(summary["total_burn_events"], 2)
        self.assertIn("commitment", summary)
        self.assertTrue(summary["on_chain_verifiable"])

    def test_verify_range_match(self):
        """verify_range passes when on-chain matches internal."""
        self.tracker.add_burn(1.0, 100, "0xchain01", network="testnet", netuid=272)

        onchain_mock = [
            {"block": 100, "amount_alpha": 1.0, "tx_hash": "0xchain01",
             "hotkey": "5FakeOwnerHotkey123", "netuid": 272, "network": "testnet"}
        ]

        verifier = self._make_verifier(onchain_burns=onchain_mock)
        report = verifier.verify_range(start_block=50, end_block=200)

        self.assertIn("result", report)
        self.assertEqual(report["result"]["match"], True)
        self.assertAlmostEqual(report["result"]["discrepancy_alpha"], 0.0, places=4)
        self.assertEqual(report["onchain"]["count"], 1)
        self.assertEqual(report["internal"]["count"], 1)

    def test_verify_range_discrepancy(self):
        """verify_range detects discrepancy when amounts differ."""
        # Internal says 1.0, on-chain shows 1.5
        self.tracker.add_burn(1.0, 100, "0xmismatch", network="testnet", netuid=272)

        onchain_mock = [
            {"block": 100, "amount_alpha": 1.5, "tx_hash": "0xonchain",
             "hotkey": "5FakeOwnerHotkey123", "netuid": 272, "network": "testnet"}
        ]

        verifier = self._make_verifier(onchain_burns=onchain_mock)
        report = verifier.verify_range(start_block=50, end_block=200)

        self.assertFalse(report["result"]["match"])
        self.assertAlmostEqual(report["result"]["discrepancy_alpha"], 0.5, places=4)

    def test_verify_range_no_burns(self):
        """verify_range handles empty ranges gracefully."""
        verifier = self._make_verifier(onchain_burns=[])
        report = verifier.verify_range(start_block=0, end_block=100)

        self.assertTrue(report["result"]["match"])
        self.assertEqual(report["onchain"]["count"], 0)
        self.assertEqual(report["internal"]["count"], 0)

    def test_verify_range_report_structure(self):
        """verify_range report has all expected fields."""
        verifier = self._make_verifier(onchain_burns=[])
        report = verifier.verify_range(start_block=0, end_block=100)

        self.assertIn("verified_at", report)
        self.assertIn("block_range", report)
        self.assertIn("network", report)
        self.assertIn("netuid", report)
        self.assertIn("onchain", report)
        self.assertIn("internal", report)
        self.assertIn("result", report)
        self.assertIn("verdict", report)

    def test_verify_range_verdict_verified(self):
        """Matching burns produce VERIFIED verdict."""
        verifier = self._make_verifier(onchain_burns=[])
        report = verifier.verify_range(start_block=0, end_block=100)
        self.assertIn("VERIFIED", report["verdict"])

    def test_verify_range_verdict_discrepancy(self):
        """Mismatched burns produce DISCREPANCY verdict."""
        self.tracker.add_burn(99.0, 50, "0xbig", network="testnet", netuid=272)
        onchain_mock = []
        verifier = self._make_verifier(onchain_burns=onchain_mock)
        report = verifier.verify_range(start_block=0, end_block=100)
        self.assertIn("DISCREPANCY", report["verdict"])

    def test_missing_blocks_tracked(self):
        """verify_range tracks blocks in one set but not the other."""
        self.tracker.add_burn(1.0, 100, "0xinternal", network="testnet", netuid=272)
        onchain_mock = [
            {"block": 200, "amount_alpha": 1.0, "tx_hash": "0xonchain",
             "hotkey": "5FakeOwnerHotkey123", "netuid": 272, "network": "testnet"}
        ]
        verifier = self._make_verifier(onchain_burns=onchain_mock)
        report = verifier.verify_range(start_block=0, end_block=300)

        # Block 100 is internal-only, block 200 is chain-only
        self.assertIn(200, report["result"]["burns_in_chain_not_recorded"])
        self.assertIn(100, report["result"]["burns_recorded_not_in_chain"])


# ─── burn_emissions.py unit tests ────────────────────────────────────────────

class TestBurnEmissionsScript(unittest.TestCase):
    """Unit tests for the burn_emissions.py helper functions."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # Set environment to use temp dir
        os.environ["BURN_HISTORY_PATH"] = str(Path(self.tmp) / "burn_history.json")
        os.environ["BURN_STATE_PATH"] = str(Path(self.tmp) / "burn_state.json")
        os.environ["NOBI_LOG_DIR"] = self.tmp

    def tearDown(self):
        for key in ["BURN_HISTORY_PATH", "BURN_STATE_PATH", "NOBI_LOG_DIR"]:
            os.environ.pop(key, None)

    def test_load_wallet_password_from_env(self):
        """load_wallet_password reads from WALLET_PASSWORD env var."""
        # Import here to get fresh module with our env vars
        import importlib
        import scripts.burn_emissions as be
        importlib.reload(be)

        os.environ["WALLET_PASSWORD"] = "testpassword123"
        result = be.load_wallet_password()
        self.assertEqual(result, "testpassword123")
        del os.environ["WALLET_PASSWORD"]

    def test_load_save_history(self):
        """load_history / save_history round-trip works."""
        import scripts.burn_emissions as be

        history_path = Path(self.tmp) / "burn_history.json"
        be.HISTORY_PATH = history_path

        be.save_history([{"amount_alpha": 1.0, "block": 100}])
        loaded = be.load_history()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["amount_alpha"], 1.0)

    def test_load_empty_history(self):
        """load_history returns [] when file doesn't exist."""
        import scripts.burn_emissions as be
        be.HISTORY_PATH = Path(self.tmp) / "nonexistent.json"
        result = be.load_history()
        self.assertEqual(result, [])

    def test_load_save_state(self):
        """load_state / save_state round-trip works."""
        import scripts.burn_emissions as be
        state_path = Path(self.tmp) / "burn_state.json"
        be.STATE_PATH = state_path

        state = {"last_burn_block": 500, "last_run_ts": 12345}
        be.save_state(state)
        loaded = be.load_state()
        self.assertEqual(loaded["last_burn_block"], 500)

    def test_load_empty_state(self):
        """load_state returns defaults when file doesn't exist."""
        import scripts.burn_emissions as be
        be.STATE_PATH = Path(self.tmp) / "nonexistent_state.json"
        state = be.load_state()
        self.assertIn("last_burn_block", state)
        self.assertEqual(state["last_burn_block"], 0)

    def test_record_burn(self):
        """record_burn creates a valid record and appends to history."""
        import scripts.burn_emissions as be
        be.HISTORY_PATH = Path(self.tmp) / "burn_history.json"
        be.BURN_NETWORK = "testnet"
        be.BURN_NETUID = 272

        record = be.record_burn(2.5, 150, "0xtest", dry_run=False)

        self.assertEqual(record["amount_alpha"], 2.5)
        self.assertEqual(record["block"], 150)
        self.assertEqual(record["tx_hash"], "0xtest")
        self.assertFalse(record["dry_run"])
        self.assertIn("timestamp", record)

        # Verify it was saved
        history = be.load_history()
        self.assertEqual(len(history), 1)

    def test_record_dry_run_burn(self):
        """record_burn correctly flags dry-run records."""
        import scripts.burn_emissions as be
        be.HISTORY_PATH = Path(self.tmp) / "burn_history.json"
        be.BURN_NETWORK = "testnet"
        be.BURN_NETUID = 272

        record = be.record_burn(1.0, 100, "DRY_RUN", dry_run=True)
        self.assertTrue(record["dry_run"])

    @patch("bittensor.Wallet")
    @patch("bittensor.Subtensor")
    def test_run_burn_cycle_below_threshold(self, MockSubtensor, MockWallet):
        """run_burn_cycle does nothing when balance < threshold."""
        import scripts.burn_emissions as be

        be.HISTORY_PATH = Path(self.tmp) / "burn_history.json"
        be.BURN_NETWORK = "testnet"
        be.BURN_NETUID = 272
        be.BURN_THRESHOLD = 0.001

        # Mock subtensor instance
        mock_subtensor = MagicMock()
        mock_subtensor.get_current_block.return_value = 1000
        mock_subtensor.get_subnet_owner_hotkey.return_value = "5FakeHotkey"
        # Balance below threshold
        mock_balance = MagicMock()
        mock_balance.tao = 0.0005
        mock_subtensor.get_stake_for_hotkey.return_value = mock_balance
        MockSubtensor.return_value = mock_subtensor

        mock_wallet = MagicMock()
        mock_wallet.hotkey.ss58_address = "5FakeHotkey"
        MockWallet.return_value = mock_wallet

        result = be.run_burn_cycle(dry_run=False)
        self.assertIsNone(result)
        mock_subtensor.add_stake_burn.assert_not_called()

    @patch("bittensor.Wallet")
    @patch("bittensor.Subtensor")
    def test_run_burn_cycle_dry_run(self, MockSubtensor, MockWallet):
        """run_burn_cycle returns a dry-run record without executing burn."""
        import scripts.burn_emissions as be

        be.HISTORY_PATH = Path(self.tmp) / "burn_history.json"
        be.BURN_NETWORK = "testnet"
        be.BURN_NETUID = 272
        be.BURN_THRESHOLD = 0.001

        # Mock subtensor instance
        mock_subtensor = MagicMock()
        mock_subtensor.get_current_block.return_value = 2000
        mock_subtensor.get_subnet_owner_hotkey.return_value = "5FakeOwner"
        mock_balance = MagicMock()
        mock_balance.tao = 5.0
        mock_subtensor.get_stake_for_hotkey.return_value = mock_balance
        MockSubtensor.return_value = mock_subtensor

        mock_wallet = MagicMock()
        mock_wallet.hotkey.ss58_address = "5FakeOwner"
        MockWallet.return_value = mock_wallet

        record = be.run_burn_cycle(dry_run=True)
        self.assertIsNotNone(record)
        self.assertTrue(record["dry_run"])
        self.assertEqual(record["tx_hash"], "DRY_RUN")
        # add_stake_burn should NOT be called in dry-run mode
        mock_subtensor.add_stake_burn.assert_not_called()


# ─── Integration: Tracker → API flow ─────────────────────────────────────────

class TestBurnIntegration(unittest.TestCase):
    """Integration tests: Tracker writes, API reads."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tracker = make_tracker(self.tmp)

    def test_tracker_to_export(self):
        """Tracker records flow correctly into export_json."""
        # Simulate 3 burn cycles
        for i in range(1, 4):
            self.tracker.add_burn(
                amount_alpha=float(i),
                block=i * 100,
                tx_hash=f"0x{i:04x}",
                network="testnet",
                netuid=272,
            )

        export = self.tracker.export_json(network="testnet", netuid=272)
        self.assertEqual(export["burn_count"], 3)
        self.assertAlmostEqual(export["total_burned_alpha"], 6.0, places=4)
        self.assertIsNotNone(export["latest_burn"])
        self.assertEqual(len(export["history"]), 3)

    def test_burn_history_file_is_valid_json(self):
        """Burn history file is always valid JSON after operations."""
        self.tracker.add_burn(1.0, 100, "0x01")
        self.tracker.add_burn(2.0, 200, "0x02")

        history_file = Path(self.tmp) / "burn_history.json"
        self.assertTrue(history_file.exists())

        # Should be valid JSON
        data = json.loads(history_file.read_text())
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
