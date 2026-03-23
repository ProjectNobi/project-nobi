"""
Nobi Burn Verifier
==================
Independently verifies on-chain burn activity by querying the blockchain
for `add_stake_burn` extrinsics from the subnet owner hotkey, then comparing
against our internal burn_history.json records.

This lets ANYONE independently verify that Project Nobi is burning its
owner take emissions as promised.

Usage:
    from nobi.burn.verifier import BurnVerifier
    verifier = BurnVerifier(network="testnet", netuid=272)
    report = verifier.verify_range(start_block=1000, end_block=2000)
    print(report)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from nobi.burn.tracker import BurnTracker, DEFAULT_HISTORY_PATH

logger = logging.getLogger("nobi.burn.verifier")

# Network endpoint mapping
NETWORK_ENDPOINTS = {
    "testnet": "test",
    "mainnet": "finney",
    "local": "local",
}


class BurnVerifier:
    """
    Queries on-chain data to verify burn events match our internal records.

    Args:
        network: 'testnet' or 'mainnet'.
        netuid: The subnet ID to verify (default: 272).
        owner_hotkey_ss58: The owner hotkey SS58 address.
            If None, will be fetched from the chain.
        history_path: Path to burn_history.json.
    """

    def __init__(
        self,
        network: str = "testnet",
        netuid: int = 272,
        owner_hotkey_ss58: Optional[str] = None,
        history_path: Optional[Path] = None,
    ):
        self.network = network
        self.netuid = netuid
        self.owner_hotkey_ss58 = owner_hotkey_ss58
        self.tracker = BurnTracker(history_path=history_path)
        self._subtensor = None  # lazy

    def _get_subtensor(self):
        """Lazy-init subtensor connection."""
        if self._subtensor is None:
            try:
                import bittensor as bt
                endpoint = NETWORK_ENDPOINTS.get(self.network, "test")
                self._subtensor = bt.Subtensor(network=endpoint)
                logger.info(f"Connected to {self.network} subtensor")
            except ImportError:
                raise RuntimeError("bittensor SDK not installed. Install with: pip install bittensor")
        return self._subtensor

    def _get_owner_hotkey(self) -> Optional[str]:
        """Fetch the subnet owner hotkey from chain if not already set."""
        if self.owner_hotkey_ss58:
            return self.owner_hotkey_ss58
        try:
            subtensor = self._get_subtensor()
            hotkey = subtensor.get_subnet_owner_hotkey(netuid=self.netuid)
            if hotkey:
                self.owner_hotkey_ss58 = hotkey
                logger.info(f"Owner hotkey: {hotkey}")
            return hotkey
        except Exception as e:
            logger.error(f"Failed to get owner hotkey: {e}")
            return None

    def query_onchain_burns(
        self, start_block: int, end_block: int
    ) -> List[Dict[str, Any]]:
        """
        Query the blockchain for add_stake_burn extrinsics from the owner hotkey
        in the given block range.

        NOTE: This queries block-by-block, which can be slow for large ranges.
        For production use, consider using a blockchain explorer API or indexer.

        Args:
            start_block: Starting block number (inclusive).
            end_block: Ending block number (inclusive).

        Returns:
            List of on-chain burn event dicts with keys:
            block, timestamp, amount_alpha, tx_hash, hotkey, netuid.
        """
        subtensor = self._get_subtensor()
        owner_hotkey = self._get_owner_hotkey()
        if not owner_hotkey:
            logger.warning("No owner hotkey — cannot verify on-chain burns")
            return []

        onchain_burns = []
        logger.info(f"Querying on-chain burns: blocks {start_block} → {end_block}")

        # Query block-by-block for extrinsics
        # In bittensor v10, we query the substrate interface directly
        for block_num in range(start_block, end_block + 1):
            try:
                block_hash = subtensor.get_block_hash(block_num)
                if not block_hash:
                    continue

                # Query block extrinsics via substrate interface
                block_data = subtensor.substrate.get_block(block_hash=block_hash)
                if not block_data or "extrinsics" not in block_data:
                    continue

                for extrinsic in block_data.get("extrinsics", []):
                    ext_data = self._parse_extrinsic(extrinsic, owner_hotkey, block_num, block_hash)
                    if ext_data:
                        onchain_burns.append(ext_data)

            except Exception as e:
                logger.debug(f"Block {block_num} query error: {e}")
                continue

        logger.info(f"Found {len(onchain_burns)} on-chain burns in range")
        return onchain_burns

    def _parse_extrinsic(
        self,
        extrinsic: Any,
        owner_hotkey: str,
        block_num: int,
        block_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a block extrinsic to see if it's an add_stake_burn from our hotkey.

        Returns a burn event dict if matched, else None.
        """
        try:
            # Substrate extrinsics are complex objects; extract the call data
            call = None
            signer = None

            if hasattr(extrinsic, 'value'):
                ext_val = extrinsic.value
                call = ext_val.get('call', {})
                signer = ext_val.get('address', {})
            elif isinstance(extrinsic, dict):
                call = extrinsic.get('call', {})
                signer = extrinsic.get('address', {})

            if not call:
                return None

            call_module = call.get('call_module', '')
            call_function = call.get('call_function', '')

            # Match SubtensorModule.add_stake_burn
            if call_module != 'SubtensorModule' or call_function != 'add_stake_burn':
                return None

            # Check hotkey matches
            call_args = call.get('call_args', {})
            if isinstance(call_args, list):
                call_args = {a.get('name'): a.get('value') for a in call_args}

            hotkey_ss58 = call_args.get('hotkey_ss58') or call_args.get('hotkey', '')
            if hotkey_ss58 != owner_hotkey:
                return None

            # Extract amount and netuid
            amount_raw = call_args.get('amount', 0)
            netuid = call_args.get('netuid', self.netuid)

            if int(netuid) != self.netuid:
                return None

            # Convert RAO to TAO
            amount_tao = float(amount_raw) / 1e9 if isinstance(amount_raw, int) else float(amount_raw)

            return {
                "block": block_num,
                "block_hash": block_hash,
                "tx_hash": f"{block_hash[:10]}...",  # approximate; real tx hash requires event query
                "amount_alpha": amount_tao,
                "hotkey": hotkey_ss58,
                "netuid": int(netuid),
                "network": self.network,
                "timestamp": None,  # block timestamp would require additional query
            }
        except Exception as e:
            logger.debug(f"Extrinsic parse error: {e}")
            return None

    def verify_range(
        self, start_block: int, end_block: int
    ) -> Dict[str, Any]:
        """
        Verify our internal burn records against on-chain data for a block range.

        Compares:
        - On-chain add_stake_burn calls from our owner hotkey
        - Our internal burn_history.json records for the same range

        Returns a verification report with any discrepancies.

        Args:
            start_block: Start of block range to verify.
            end_block: End of block range to verify.

        Returns:
            Verification report dict.
        """
        logger.info(f"Verifying burns: blocks {start_block} → {end_block}")

        # Get on-chain burns
        onchain = self.query_onchain_burns(start_block, end_block)

        # Get internal records for same range
        internal = [
            r for r in self.tracker.get_burn_history(network=self.network, netuid=self.netuid)
            if start_block <= r.get("block", 0) <= end_block
        ]

        # Compare
        onchain_total = sum(b.get("amount_alpha", 0.0) for b in onchain)
        internal_total = sum(r.get("amount_alpha", 0.0) for r in internal)

        onchain_count = len(onchain)
        internal_count = len(internal)

        discrepancy = abs(onchain_total - internal_total)
        match = discrepancy < 0.0001  # within 0.0001 ALPHA tolerance

        # Identify any missing records
        onchain_blocks = {b["block"] for b in onchain}
        internal_blocks = {r.get("block") for r in internal}

        in_chain_not_internal = onchain_blocks - internal_blocks
        in_internal_not_chain = internal_blocks - onchain_blocks

        report = {
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "block_range": {"start": start_block, "end": end_block},
            "network": self.network,
            "netuid": self.netuid,
            "owner_hotkey": self.owner_hotkey_ss58,
            "onchain": {
                "count": onchain_count,
                "total_alpha": onchain_total,
                "burns": onchain,
            },
            "internal": {
                "count": internal_count,
                "total_alpha": internal_total,
                "burns": internal,
            },
            "result": {
                "match": match,
                "discrepancy_alpha": discrepancy,
                "burns_in_chain_not_recorded": list(in_chain_not_internal),
                "burns_recorded_not_in_chain": list(in_internal_not_chain),
            },
            "verdict": "✅ VERIFIED" if match else "❌ DISCREPANCY FOUND",
        }

        if match:
            logger.info(f"✅ Verification passed: {onchain_count} burns, {onchain_total:.6f} ALPHA")
        else:
            logger.warning(
                f"❌ Discrepancy: on-chain={onchain_total:.6f}, internal={internal_total:.6f}, "
                f"delta={discrepancy:.6f}"
            )

        return report

    def verify_latest(self, blocks_back: int = 10000) -> Dict[str, Any]:
        """
        Verify burns over the most recent N blocks.

        Args:
            blocks_back: Number of blocks to look back (default: ~35 hours at ~12s/block).

        Returns:
            Verification report.
        """
        subtensor = self._get_subtensor()
        current = subtensor.get_current_block()
        start = max(0, current - blocks_back)
        return self.verify_range(start_block=start, end_block=current)

    def get_summary(self) -> Dict[str, Any]:
        """
        Return a quick summary of our burn commitments (from internal records only).
        Does not hit the chain — fast and always available.

        Returns:
            Dict with total burned, burn count, latest burn, and commitment statement.
        """
        total = self.tracker.get_total_burned(network=self.network, netuid=self.netuid)
        count = self.tracker.get_burn_count(network=self.network, netuid=self.netuid)
        latest = self.tracker.get_latest_burn(network=self.network, netuid=self.netuid)

        return {
            "commitment": "100% of owner take (18% of subnet emissions) is burned permanently",
            "network": self.network,
            "netuid": self.netuid,
            "total_alpha_burned": total,
            "total_burn_events": count,
            "latest_burn": latest,
            "on_chain_verifiable": True,
            "burn_mechanism": "SubtensorModule.add_stake_burn (owner buyback → burn)",
            "note": "All burns are publicly verifiable on-chain. Call verify_range() to cross-check.",
        }
