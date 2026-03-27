# Project Nobi — Base Miner Neuron
# Portions adapted from opentensor/bittensor-subnet-template (MIT License)
# Copyright (c) 2023 Opentensor. See THIRD_PARTY_NOTICES.md

import time
import asyncio
import threading
import argparse
import traceback
import bittensor as bt

from nobi.base.neuron import BaseNeuron
from nobi.utils.config import add_miner_args
from typing import Union


class BaseMinerNeuron(BaseNeuron):
    """Base class for Project Nobi miners."""

    neuron_type: str = "MinerNeuron"

    @classmethod
    def add_args(cls, parser: argparse.ArgumentParser):
        super().add_args(parser)
        add_miner_args(cls, parser)

    def __init__(self, config=None):
        super().__init__(config=config)

        if not self.config.blacklist.force_validator_permit:
            bt.logging.warning(
                "You are allowing non-validators to send requests to your miner."
            )
        if self.config.blacklist.allow_non_registered:
            bt.logging.warning(
                "You are allowing non-registered entities to send requests to your miner."
            )

        self.axon = bt.Axon(
            wallet=self.wallet,
            config=self.config,
        )

        bt.logging.info(f"Attaching forward functions to miner axon.")
        self.axon.attach(
            forward_fn=self.forward,
            blacklist_fn=self.blacklist,
            priority_fn=self.priority,
        )

        # Attach memory protocol handlers if the miner implements them
        # Note: no blacklist/priority for memory synapses (they have different signatures)
        if hasattr(self, 'forward_memory_store'):
            try:
                self.axon.attach(forward_fn=self.forward_memory_store)
                bt.logging.info("Attached MemoryStore handler to axon")
            except Exception as e:
                bt.logging.debug(f"MemoryStore attach skipped: {e}")

        if hasattr(self, 'forward_memory_recall'):
            try:
                self.axon.attach(forward_fn=self.forward_memory_recall)
                bt.logging.info("Attached MemoryRecall handler to axon")
            except Exception as e:
                bt.logging.debug(f"MemoryRecall attach skipped: {e}")

        # GDPR Art. 17: attach MemoryForget handler if miner implements it
        # Graceful degradation: older miners without this method are simply skipped
        if hasattr(self, 'forward_memory_forget'):
            try:
                self.axon.attach(forward_fn=self.forward_memory_forget)
                bt.logging.info("Attached MemoryForget handler to axon (GDPR Art. 17)")
            except Exception as e:
                bt.logging.debug(f"MemoryForget attach skipped: {e}")

        bt.logging.info(f"Axon created: {self.axon}")

        self.should_exit: bool = False
        self.is_running: bool = False
        self.thread: Union[threading.Thread, None] = None
        self.lock = asyncio.Lock()

    def run(self):
        self.sync()

        bt.logging.info(
            f"Serving miner axon {self.axon} on network: {self.config.subtensor.chain_endpoint} "
            f"with netuid: {self.config.netuid}"
        )
        self.axon.serve(netuid=self.config.netuid, subtensor=self.subtensor)
        self.axon.start()

        bt.logging.info(f"Miner starting at block: {self.block}")

        try:
            while not self.should_exit:
                while (
                    self.block - self.metagraph.last_update[self.uid]
                    < self.config.neuron.epoch_length
                ):
                    time.sleep(1)
                    if self.should_exit:
                        break
                self.sync()
                self.step += 1
        except KeyboardInterrupt:
            self.axon.stop()
            bt.logging.success("Miner killed by keyboard interrupt.")
            exit()
        except Exception as e:
            bt.logging.error(traceback.format_exc())

    def run_in_background_thread(self):
        if not self.is_running:
            bt.logging.debug("Starting miner in background thread.")
            self.should_exit = False
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            self.is_running = True
            bt.logging.debug("Started")

    def stop_run_thread(self):
        if self.is_running:
            bt.logging.debug("Stopping miner in background thread.")
            self.should_exit = True
            if self.thread is not None:
                self.thread.join(5)
            self.is_running = False
            bt.logging.debug("Stopped")

    def __enter__(self):
        self.run_in_background_thread()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop_run_thread()

    def resync_metagraph(self):
        bt.logging.info("resync_metagraph()")
        self.metagraph.sync(subtensor=self.subtensor)
