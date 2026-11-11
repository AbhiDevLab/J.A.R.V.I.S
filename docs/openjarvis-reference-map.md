# OpenJarvis Reference Map for J.A.R.V.I.S

**Audit date:** 11 November 2026  
**Reference repository:** https://github.com/open-jarvis/OpenJarvis  
**Reference revision inspected:** `6201505cd3425079459589f54764667b4758ce48`  
**J.A.R.V.I.S development branch:** `test-jarvis`

This document records verified implementation patterns, not assumed product capabilities. Re-check the cited source files and tests before adapting a pattern after the reference repository changes.

## What OpenJarvis actually provides

The inspected public repository has a modular local-first AI stack with:

- A single-turn speech input/output path and configurable STT/TTS backends.
- Tool-using agents, including native ReAct and function-calling orchestration loops.
- A tool registry and agent/tool discovery/resolution mechanisms.
- Persistent user facts and document retrieval, including lexical, dense and hybrid retrieval backends.
- Session history/compression, scheduled agents, and continuous/operative agent patterns.
- Event/trace telemetry, evaluations and trace-driven learning policies.
- Security policies, approval flows, loop guards and sandboxed execution paths.

Relevant source locations:

| Capability | Verified source |
|---|---|
| ReAct thought/action/observation loop | `src/openjarvis/agents/native_react.py` |
| Function-calling orchestration and governance hook | `src/openjarvis/agents/orchestrator.py` |
| Dynamic tool resolution | `src/openjarvis/agents/tool_resolver.py` |
| Loop protection | `src/openjarvis/agents/loop_guard.py` |
| Background memory extraction | `src/openjarvis/memory/service.py` |
| Fact extraction policy | `src/openjarvis/memory/extractor.py` |
| Fact storage and provenance tiers | `src/openjarvis/memory/store.py` |
| Speech capture and playback | `src/openjarvis/speech/voice_io.py` |
| Voice chat orchestration | `src/openjarvis/cli/_voice_chat.py` |
| Trace-driven learning design | `docs/architecture/learning.md` |

## Comparison with planned J.A.R.V.I.S capabilities

OpenJarvis does **not** contain every capability planned for J.A.R.V.I.S. It is a framework and local-first personal AI stack, not a drop-in Windows voice-assistant implementation.

J.A.R.V.I.S-specific capabilities that must remain owned by this repository include Windows application/window control, filesystem automation, ADB/Android operations, face/voice authentication, the Porcupine wake-word process, existing permission tiers, and the current Kokoro/SAPI5 interruption contract. The inspected OpenJarvis speech path records an utterance, transcribes it, then plays TTS; it is not evidence of AEC or unrestricted full-duplex barge-in.

OpenJarvis has broader generic agent orchestration, retrieval and trace-learning infrastructure. These are candidates for selective future adaptation, not reasons to replace J.A.R.V.I.S's deterministic desktop router or security gate.

## Pattern adapted in this change

OpenJarvis's `MemoryService` uses a bounded queue and one background worker to extract durable facts after a completed exchange. J.A.R.V.I.S already has its own selective, non-sensitive semantic-memory extractor, but it was called synchronously after TTS. This change reuses the *background handoff pattern* while retaining J.A.R.V.I.S's current extractor, SQLite memory schema, eligibility rules, confidence gates and retention policy.

The queue is best-effort and bounded: a full queue drops an extraction job rather than delaying live interaction. Extraction failures are isolated to the worker. Memory is not an execution instruction and continues to be supplied to interpretation as reference data only.

## Adaptation rules

1. Inspect the actual OpenJarvis source and tests at a recorded revision before adapting a capability.
2. Port only a pattern that fits the J.A.R.V.I.S Windows runtime, current provider, dependencies and architecture.
3. Preserve J.A.R.V.I.S deterministic routing, explicit confirmation/face-auth requirements, and fail-closed behavior.
4. Do not assume OpenJarvis has Windows-specific, face-auth, Porcupine, AEC, or wake-word-free interruption functionality without locating and testing its implementation.
5. Add J.A.R.V.I.S regression tests and verify on the target Windows machine for any hardware or desktop integration.
