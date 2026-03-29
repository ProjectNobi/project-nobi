from .store import MemoryManager

try:
    from .graph import MemoryGraph
except ImportError:
    pass

try:
    from .llm_extractor import LLMEntityExtractor, merge_extractions
except ImportError:
    pass

try:
    from .contradictions import ContradictionDetector, Contradiction
except ImportError:
    pass

# MemoryBear — Biological Cognition Layer
try:
    from .forgetting import compute_activation, apply_forgetting, run_forgetting_cron
except ImportError:
    pass

try:
    from .inference import infer_implicit_memories, get_implicit_memories, run_inference_cron, clear_inference_data
except ImportError:
    pass

try:
    from .reflection import detect_conflicts, resolve_conflict, run_nightly_reflection, run_reflection_cron, clear_reflection_data
except ImportError:
    pass

try:
    from .emotion import (
        detect_emotion, store_emotion_reading, get_emotion_trend,
        get_current_mood, build_mood_context, EmotionReading, EmotionTrend,
        clear_emotion_data,
    )
except ImportError:
    pass

try:
    from .search import hybrid_search, bm25_score
except ImportError:
    pass


async def check_memorybear_health(db_path: str = "~/.nobi/bot_memories.db") -> dict:
    """
    Health check for all MemoryBear modules.
    Tests DB connectivity and returns status for each module.

    Returns:
        Dict with {module_name: {"status": "ok"|"error", "detail": str}}
    """
    import os
    import sqlite3

    db_path_expanded = os.path.expanduser(db_path)
    results = {}

    # Check DB exists
    if not os.path.exists(db_path_expanded):
        return {"database": {"status": "error", "detail": f"DB not found at {db_path_expanded}"}}

    results["database"] = {"status": "ok", "detail": db_path_expanded}

    # Check each module's table
    modules = {
        "forgetting": ("memories", "is_active"),
        "emotion": ("emotion_readings", "user_id"),
        "inference": ("implicit_memories", "user_id"),
        "reflection": ("memory_conflicts", "user_id"),
    }

    try:
        conn = sqlite3.connect(db_path_expanded)
        for module_name, (table, column) in modules.items():
            try:
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                results[module_name] = {"status": "ok", "detail": f"{row[0]} rows"}
            except Exception as e:
                results[module_name] = {"status": "error", "detail": str(e)}
        conn.close()
    except Exception as e:
        results["database"] = {"status": "error", "detail": str(e)}

    # Check BM25 availability
    try:
        from rank_bm25 import BM25Okapi  # noqa: F401
        results["bm25"] = {"status": "ok", "detail": "rank_bm25 installed"}
    except ImportError:
        results["bm25"] = {"status": "degraded", "detail": "rank_bm25 not installed — keyword fallback active"}

    # Check embeddings availability
    try:
        from nobi.memory.embeddings import get_engine
        engine = get_engine()
        results["embeddings"] = {"status": "ok" if engine else "degraded",
                                  "detail": "engine loaded" if engine else "no embedding engine"}
    except ImportError:
        results["embeddings"] = {"status": "degraded", "detail": "embeddings module not available"}

    return results
