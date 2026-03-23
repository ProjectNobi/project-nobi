"""
Project Nobi — pytest conftest.py

Global test fixtures and hooks to ensure proper test isolation across all test files.

KNOWN ISSUE FIXED:
  test_stress_10k.py sets os.environ["NOBI_DISABLE_EMBEDDINGS"] = "1" at module
  import time (needed to prevent heavy model loading during the stress test imports).
  When pytest runs the full suite, this env var persists into test_semantic_memory.py,
  causing 5 embedding-related tests to fail.

  Fix: This autouse fixture clears NOBI_DISABLE_EMBEDDINGS before each test
  that belongs to test_semantic_memory.py, and also resets the EmbeddingEngine
  singleton so it re-initialises cleanly without the disabled flag.
"""

import os
import pytest


@pytest.fixture(autouse=True)
def _isolate_embedding_env(request):
    """
    Per-test fixture that clears embedding-disabling env vars before each test
    in test_semantic_memory.py, ensuring those tests always see embeddings enabled.

    For all other test files the env var is left as-is (stress tests may set it
    themselves in their setUp).
    """
    if "test_semantic_memory" in request.fspath.basename:
        # Clear the flag so embeddings are enabled for this test
        was_set = os.environ.pop("NOBI_DISABLE_EMBEDDINGS", None)
        # Also reset the singleton so it re-initialises without the disabled flag
        try:
            from nobi.memory.embeddings import reset_engine
            reset_engine()
        except Exception:
            pass
        yield
        # Restore after test (keeps stress tests happy if they run later)
        if was_set is not None:
            os.environ["NOBI_DISABLE_EMBEDDINGS"] = was_set
    else:
        yield
