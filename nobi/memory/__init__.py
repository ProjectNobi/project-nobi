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
    from .inference import infer_implicit_memories, get_implicit_memories, run_inference_cron
except ImportError:
    pass

try:
    from .reflection import detect_conflicts, resolve_conflict, run_nightly_reflection, run_reflection_cron
except ImportError:
    pass

try:
    from .emotion import (
        detect_emotion, store_emotion_reading, get_emotion_trend,
        get_current_mood, build_mood_context, EmotionReading, EmotionTrend,
    )
except ImportError:
    pass

try:
    from .search import hybrid_search, bm25_score
except ImportError:
    pass
