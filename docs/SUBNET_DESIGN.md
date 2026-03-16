# Project Nobi — Subnet Design Document

## Overview
A Bittensor subnet where miners compete to provide the best personal AI companion experience.

## Synapse Protocol

### CompanionRequest
```python
class CompanionRequest(bt.Synapse):
    # User's message
    message: str
    # Encrypted user memory context (only miner can decrypt)
    memory_context: Optional[bytes]
    # User preferences (language, personality style, etc.)
    preferences: dict
    # Tool requests (if agentic task)
    tools_requested: Optional[list[str]]
    # Session continuity token
    session_token: str
```

### CompanionResponse
```python
class CompanionResponse(bt.Synapse):
    # AI response
    response: str
    # Updated memory entries to store
    memory_updates: Optional[list[dict]]
    # Tool execution results
    tool_results: Optional[list[dict]]
    # Quality metadata
    confidence: float
    latency_ms: int
```

## Scoring Mechanism

Validators score miners on:

| Dimension | Weight | How |
|-----------|--------|-----|
| Response Quality | 40% | LLM-as-judge comparison |
| Memory Accuracy | 20% | Can miner recall past interactions correctly? |
| Tool Execution | 15% | Did requested actions complete successfully? |
| Latency | 10% | Speed of response |
| Privacy | 15% | Data handling compliance checks |

## Memory Protocol
- User memory is encrypted client-side
- Miners receive encrypted context, decrypt with user-granted session key
- Memory updates are encrypted before storage
- No miner can read another user's memory
- Distributed storage across miners for redundancy

## Privacy Architecture
- End-to-end encryption for all personal data
- Zero-knowledge proofs for memory verification
- User controls what miners can access
- Right to delete — user can wipe all data

## Economics
- Users pay subscription (TAO or fiat via bridge)
- Payment split: 70% to miners, 18% to subnet owner, 12% to validators
- Premium tiers unlock more memory, better models, priority routing
