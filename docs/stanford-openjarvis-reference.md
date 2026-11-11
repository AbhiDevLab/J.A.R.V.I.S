# Stanford OpenJarvis — verified reference for J.A.R.V.I.S

**Reference snapshot:** OpenJarvis `main` at commit `6201505cd3425079459589f54764667b4758ce48`  
**Reviewed:** 2026-11-11  
**J.A.R.V.I.S target branch:** `test-jarvis`

This document records what was verified in the public OpenJarvis source and how those patterns should influence J.A.R.V.I.S. It is a source map, not a promise that every OpenJarvis feature is present in J.A.R.V.I.S.

## 1. What makes OpenJarvis capable during an interaction

OpenJarvis is a modular local-first personal-AI framework, not one monolithic assistant implementation. Its runtime composes intelligence/model selection, an agent, tools, memory/session context, and learning/evaluation.

### Per-request intelligence loop

Its documented agent context carries the conversation, available tools, retrieved memory results and metadata. Tool-using agents can iterate rather than stopping after a single model response:

1. Build the model messages from the user request and session context.
2. Include the registered tool descriptions/schema.
3. Ask the model for a response or a tool call.
4. Execute a selected tool through the shared tool executor.
5. Append the tool result as an observation and ask the model to continue.
6. Stop when the model returns a final answer or a bounded turn limit is reached.

The native ReAct implementation parses a structured response and performs a Thought → Action → Observation loop. The Orchestrator implementation uses function-calling messages. Both are bounded by a maximum turn count. OpenJarvis also has a loop guard for repeated identical calls and tool-call cycles.

This is an important source of its *interactive* capability: the model can inspect a result, choose the next tool, and revise its answer in the same task. It is not merely a larger system prompt.

Verified source:
- [Agent architecture](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/docs/architecture/agents.md)
- [Native ReAct agent](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/src/openjarvis/agents/native_react.py)
- [Orchestrator agent](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/src/openjarvis/agents/orchestrator.py)
- [Tool resolver](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/src/openjarvis/agents/tool_resolver.py)
- [Loop guard](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/src/openjarvis/agents/loop_guard.py)

### Context and memory

OpenJarvis separates session context, persistent agent state and searchable knowledge. Its memory architecture documents SQLite/FTS5 as a lightweight persistent retrieval option, plus optional BM25, dense-vector, ColBERT and hybrid retrieval backends. Those choices are alternatives with different dependency, latency and persistence tradeoffs; the project does not require every backend for every installation.

The persistent-memory showcase also demonstrates human-readable `SOUL.md`, `MEMORY.md` and `USER.md` files for agent identity/preferences. That is a documented pattern, not evidence that every OpenJarvis run automatically uses those three files.

Verified source:
- [Memory architecture](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/docs/architecture/memory.md)
- [Memory service](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/src/openjarvis/memory/service.py)
- [Memory store](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/src/openjarvis/memory/store.py)
- [Persistent-memory showcase](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/docs/showcase/persistent-memory.md)

### Learning from traces and evaluation

OpenJarvis records interaction/agent traces, including step types, outcomes, tool results, durations and feedback. Its analyzers aggregate that history. Learning policies can use the accumulated observations to improve routing or agent strategy. The learned router has a minimum sample count before a learned query-class/model mapping is trusted.

This is not the same as the model retraining itself after every user message. The verified architecture is trace collection plus analysis/policy updates and benchmark/evaluation gates. That distinction matters: a system should measure success before changing its future behavior.

Verified source:
- [Learning architecture](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/docs/architecture/learning.md)
- [Trace collector](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/src/openjarvis/traces/collector.py)
- [Trace analyzer](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/src/openjarvis/traces/analyzer.py)
- [Learned router](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/src/openjarvis/learning/routing/learned_router.py)
- [Agent evaluation harness](https://github.com/open-jarvis/OpenJarvis/tree/6201505cd3425079459589f54764667b4758ce48/src/openjarvis/evals)

### Tool security

OpenJarvis has reusable security layers such as input/output scanning and sandboxed execution options. Those mechanisms are complementary to J.A.R.V.I.S's native Windows action authorization. They are not a reason to replace J.A.R.V.I.S's risk classification, explicit confirmation, face-authentication or administrator-elevation controls.

Verified source:
- [Security guardrails](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/src/openjarvis/security/guardrails.py)
- [Agent architecture and sandbox guidance](https://github.com/open-jarvis/OpenJarvis/blob/6201505cd3425079459589f54764667b4758ce48/docs/architecture/agents.md)

## 2. Capability comparison with the J.A.R.V.I.S roadmap

| Capability | Stanford OpenJarvis source | J.A.R.V.I.S status / difference |
|---|---|---|
| Context-aware answers | Conversation/session context and retrieved memory are passed into agents | Implemented through conversation summaries, contextual interpretation, profile, references and per-turn context snapshot |
| Persistent memory | Persistent memory and searchable document knowledge; optional retrieval backends | Implemented using SQLite semantic/episodic memory and lexical retrieval |
| Multi-step tool use | General function-calling and native ReAct loops, bounded by turn limits | Structured deterministic desktop actions exist; a general model-driven ReAct tool loop is not implemented |
| Tool schemas/discovery | Shared tool registry/resolver, function schemas, skills and MCP adapters | J.A.R.V.I.S has `AutomationAction`, deterministic router/executor and Windows application/filesystem handlers; not the same general tool catalog |
| Loop protection | Dedicated loop guard for repeated calls and cycling patterns | No equivalent general agent-loop guard is needed for the current one-action deterministic path; revisit if a bounded tool loop is introduced |
| Trace-based learning | Trace store, analyzer and learned routing/agent policies | No equivalent end-to-end trace-driven optimization loop currently exists |
| Evaluation | Dedicated benchmark datasets, scorers and agent scenario/evaluation harnesses | J.A.R.V.I.S has pytest regressions; broader realistic multi-turn/voice evaluation is still a Phase 8.9 task |
| Speech input/output | Pluggable STT/TTS and turn-based microphone/playback helpers in the inspected speech path | J.A.R.V.I.S has Faster-Whisper, Kokoro/SAPI5, Porcupine, continuous listening and wake-word interruption |
| Wake-word barge-in / AEC | No equivalent implementation found in the inspected OpenJarvis speech path | J.A.R.V.I.S has wake-word-during-TTS interruption; unrestricted speech barge-in and AEC are not being pursued in the current plan |
| Windows desktop / Android | Broad generic tools and connectors; not the same as J.A.R.V.I.S's Windows-specific integration | J.A.R.V.I.S has Windows app/window control, filesystem automation, face/voice permission flows and ADB/Android integration |

**Conclusion:** OpenJarvis does not have every capability planned for J.A.R.V.I.S, and J.A.R.V.I.S does not have every OpenJarvis capability. They overlap in context, memory, tools, speech and security, but their emphasis differs. OpenJarvis is a modular local-first agent framework; J.A.R.V.I.S is a Windows desktop assistant with direct system control and a dedicated authorization architecture.

## 3. What we should selectively adopt

Adoption order should follow demonstrated value and preserve existing behavior:

1. **Scenario-based end-to-end evaluations first.** OpenJarvis has dedicated agent scenario and evaluation tests. J.A.R.V.I.S should keep validating the whole STT → interpretation → intent → deterministic routing → authorization → result path, including low-confidence and failure cases. This is the active Phase 8.9 work.
2. **Privacy-conscious interaction traces next.** Record structured metadata such as input channel, interpreted intent/confidence, selected route, action type, result category and latency. Do not record raw audio, full prompts, credentials, private document text or arbitrary shell arguments by default. Use traces for offline analysis and regression-case creation before considering adaptive behavior.
3. **A bounded tool loop only for tasks that need multiple observations.** If introduced, use explicit schemas, a strict turn/time budget, repeated-call protection and a tool allowlist. All system-changing actions must still become `AutomationAction` instances and pass through the existing J.A.R.V.I.S authorization gate.
4. **Measure memory retrieval before adding heavier retrieval.** Keep the current SQLite memory contract. Consider hybrid/vector retrieval only if a reproducible evaluation set shows lexical retrieval misses relevant memories often enough to justify model downloads, dependencies and runtime cost.
5. **Keep speech capture separate from STT.** OpenJarvis's speech adapters demonstrate the value of separating capture/voice I/O from transcription backends. Any future Windows capture change must still have one microphone owner and must preserve the existing half-duplex fallback.

## 4. What we should not copy blindly

- Do not replace J.A.R.V.I.S's deterministic Windows automation path with model-generated shell or unrestricted tool execution.
- Do not let a model's `Action` text bypass `AutomationAction`, risk classification, authorization or face/UAC checks.
- Do not enable a multi-step agent loop without a loop guard, strict bounds and tests for duplicate side effects.
- Do not import all OpenJarvis dependencies or its Rust runtime into J.A.R.V.I.S merely to copy architecture.
- Do not claim continuous online model learning. Trace-driven policy updates require evidence, sample thresholds and regression/evaluation gates.
- Do not adopt Echoff/AEC or wake-word-free barge-in as a requirement of OpenJarvis; those features were not found in the inspected speech implementation.

## 5. Current implementation selected from this reference

The first low-risk adoption is OpenJarvis's emphasis on **scenario-based end-to-end testing**. The J.A.R.V.I.S Phase 8.9 E2E suite now includes:
- A high-confidence speech-recognition correction that must travel through the real contextual interpreter, intent classifier and deterministic router before reaching the executor.
- A low-confidence correction that must stop at clarification and never reach the executor.
- Retrieval from the real temporary SQLite memory store and profile store, with relevant context verified in both the interpretation prompt and final answer prompt.
- A genuinely ambiguous spoken target that must remain a clarification and never reach the automation executor.
- A contextual-interpreter provider timeout that must preserve the pending selection and original request for explicit retry.

These tests add no runtime dependency and do not change production routing or permissions. The project owner separately reported that the live spoken correction test ("open load pad" → "open Notepad") worked correctly. Broader live Windows context, memory, clarification, provider-recovery and multi-turn checks remain open until performed on the target machine.


## 6. Follow-on adoption: interaction traces

The next selected OpenJarvis pattern is append-only trace collection for post-run analysis. J.A.R.V.I.S now has a local SQLite trace foundation in `engine/interaction_trace.py` and command-path event hooks. It records allowlisted metadata (channel, interpretation confidence, intent/source, route, action type, coarse outcome, allowlisted provider category and stage latency) and excludes user-content fields.

This is observability only. It does not train or update a model, alter routing policy, bypass deterministic automation, or learn a new permission. Trace collection can be disabled with `JARVIS_INTERACTION_TRACES_ENABLED=0`; by default records remain local, expire after 30 days (configurable 1–365), and are capped at 50,000 events.

Verified J.A.R.V.I.S source on the implementation branch:
- [Interaction trace store](../engine/interaction_trace.py)
- [Trace privacy/operations guide](interaction-tracing.md)
