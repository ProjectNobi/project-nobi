# Project Nobi — Misc utilities

import time
from math import floor
from typing import Callable, Any
from functools import lru_cache, update_wrapper


def ttl_cache(maxsize: int = 128, typed: bool = False, ttl: int = -1):
    """LRU Cache with TTL."""
    if ttl <= 0:
        ttl = 65536
    hash_gen = _ttl_hash_gen(ttl)

    def wrapper(func: Callable) -> Callable:
        @lru_cache(maxsize, typed)
        def ttl_func(ttl_hash, *args, **kwargs):
            return func(*args, **kwargs)

        def wrapped(*args, **kwargs) -> Any:
            th = next(hash_gen)
            return ttl_func(th, *args, **kwargs)

        return update_wrapper(wrapped, func)

    return wrapper


def _ttl_hash_gen(seconds: int):
    start_time = time.time()
    while True:
        yield floor((time.time() - start_time) / seconds)


@ttl_cache(maxsize=1, ttl=12)
def ttl_get_block(self) -> int:
    """Retrieves the current block number, cached for 12 seconds."""
    return self.subtensor.get_current_block()
