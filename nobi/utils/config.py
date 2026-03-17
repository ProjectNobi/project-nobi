# Project Nobi — Configuration utilities
# Adapted from bittensor-subnet-template

import os
import subprocess
import argparse
import bittensor as bt
from .logging import setup_events_logger


def is_cuda_available():
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "-L"], stderr=subprocess.STDOUT
        )
        if "NVIDIA" in output.decode("utf-8"):
            return "cuda"
    except Exception:
        pass
    return "cpu"


def check_config(cls, config: "bt.Config"):
    """Checks/validates the config namespace object."""
    bt.logging.check_config(config)

    full_path = os.path.expanduser(
        "{}/{}/{}/netuid{}/{}".format(
            config.logging.logging_dir,
            config.wallet.name,
            config.wallet.hotkey,
            config.netuid,
            config.neuron.name,
        )
    )
    config.neuron.full_path = os.path.expanduser(full_path)
    if not os.path.exists(config.neuron.full_path):
        os.makedirs(config.neuron.full_path, exist_ok=True)

    if not config.neuron.dont_save_events:
        events_logger = setup_events_logger(
            config.neuron.full_path, config.neuron.events_retention_size
        )
        bt.logging.register_primary_logger(events_logger.name)


def add_args(cls, parser):
    """Adds relevant arguments to the parser."""
    parser.add_argument("--netuid", type=int, help="Subnet netuid", default=1)
    parser.add_argument(
        "--neuron.device", type=str, help="Device to run on.", default=is_cuda_available()
    )
    parser.add_argument(
        "--neuron.epoch_length", type=int,
        help="The default epoch length (how often we set weights, measured in 12 second blocks).",
        default=100,
    )
    parser.add_argument(
        "--mock", action="store_true", help="Mock neuron and all network components.", default=False,
    )
    parser.add_argument(
        "--neuron.events_retention_size", type=str,
        help="Events retention size.", default=2 * 1024 * 1024 * 1024,
    )
    parser.add_argument(
        "--neuron.dont_save_events", action="store_true",
        help="If set, we dont save events to a log file.", default=False,
    )


def add_miner_args(cls, parser):
    """Add miner specific arguments."""
    parser.add_argument("--neuron.name", type=str, default="miner")
    parser.add_argument(
        "--blacklist.force_validator_permit", action="store_true",
        help="If set, we will force incoming requests to have a permit.", default=False,
    )
    parser.add_argument(
        "--blacklist.allow_non_registered", action="store_true",
        help="If set, miners will accept queries from non registered entities.", default=False,
    )
    parser.add_argument(
        "--neuron.openrouter_api_key", type=str,
        help="OpenRouter API key for LLM inference.", default="",
    )
    parser.add_argument(
        "--neuron.model", type=str,
        help="Model to use via OpenRouter.", default="anthropic/claude-3.5-haiku",
    )


def add_validator_args(cls, parser):
    """Add validator specific arguments."""
    parser.add_argument("--neuron.name", type=str, default="validator")
    parser.add_argument(
        "--neuron.timeout", type=float,
        help="The timeout for each forward call in seconds.", default=30,
    )
    parser.add_argument(
        "--neuron.num_concurrent_forwards", type=int,
        help="The number of concurrent forwards running at any time.", default=1,
    )
    parser.add_argument(
        "--neuron.sample_size", type=int,
        help="The number of miners to query in a single step.", default=10,
    )
    parser.add_argument(
        "--neuron.disable_set_weights", action="store_true",
        help="Disables setting weights.", default=False,
    )
    parser.add_argument(
        "--neuron.moving_average_alpha", type=float,
        help="Moving average alpha parameter.", default=0.1,
    )
    parser.add_argument(
        "--neuron.axon_off", "--axon_off", action="store_true",
        help="Set this flag to not attempt to serve an Axon.", default=False,
    )
    parser.add_argument(
        "--neuron.vpermit_tao_limit", type=int,
        help="The maximum number of TAO allowed to query a validator with a vpermit.", default=4096,
    )
    parser.add_argument(
        "--neuron.openrouter_api_key", type=str,
        help="OpenRouter API key for LLM-as-judge scoring.", default="",
    )


def config(cls):
    """Returns the configuration object."""
    parser = argparse.ArgumentParser()
    bt.wallet.add_args(parser)
    bt.subtensor.add_args(parser)
    bt.logging.add_args(parser)
    bt.axon.add_args(parser)
    cls.add_args(parser)
    return bt.config(parser)
