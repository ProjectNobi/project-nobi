#!/usr/bin/env python3
# Project Nobi — Validator Neuron
# Phase 1: Query miners, score companion responses

import time
import bittensor as bt

from nobi.base.validator import BaseValidatorNeuron
from nobi.validator import forward


class Validator(BaseValidatorNeuron):
    """
    Project Nobi Validator — scores miners on companion response quality.

    Sends test queries to miners, evaluates responses using LLM-as-judge,
    and sets weights based on quality scores.
    """

    def __init__(self, config=None):
        super(Validator, self).__init__(config=config)

        bt.logging.info("load_state()")
        self.load_state()

    async def forward(self):
        """
        Validator forward pass:
        - Generate test query
        - Query miners
        - Score responses
        - Update weights
        """
        return await forward(self)


if __name__ == "__main__":
    with Validator() as validator:
        while True:
            bt.logging.info(f"Validator running... {time.time()}")
            time.sleep(5)
