# J.A.R.V.I.S Development Roadmap

> **Branch:** `test-jarvis`
>
> This is the authoritative development checklist for the current J.A.R.V.I.S roadmap.
>
> **Important roadmap decision:** Phase 10 (Desktop Automation / Agent Capabilities) was deliberately moved forward and became **Phase 7**. The later phases were shifted accordingly. The commit history is the source of truth for completed sub-phases.

---

# Phase 6 — Conversational System

Phase 6 was completed before the Desktop Automation work began.

- [x] Fix 8 — cleanup + shutdown/resource stability
- [x] Fix 9 — regression testing + checkpoint

**Phase status:** ✅ Completed

---

# Phase 7 — Desktop Automation / Agent Capabilities

This is the phase we are currently developing.

This phase is the deliberate move from **“assistant that answers”** to **“assistant that does things.”**

The work originally planned as Phase 10 was moved forward into Phase 7.

## Phase 7.1 — Secure Automation Foundation

**Commit:** `dca8aa88e9e5f51e4823d6eb502a366b625bb176`

- [x] Structured `AutomationAction` model
- [x] Risk-level classification
- [x] High-risk action registry
- [x] Central automation router
- [x] Central automation executor
- [x] Authorization/security gate
- [x] Explicit confirmation requirement
- [x] Face-authentication requirement
- [x] Fail-closed authorization behavior
- [x] Initial shell-command routing/execution

**Phase 7.1 status:** ✅ Completed

---

## Phase 7.2 — Desktop Application Control

**Commit:** `ec1c49d779d5f119efc430f0022ccd190e41ec1`

- [x] Known desktop application registry
- [x] Application executable resolution
- [x] Application aliases
- [x] Natural-language application names
- [x] Chrome
- [x] Edge
- [x] VS Code
- [x] Spotify
- [x] Notepad
- [x] Calculator
- [x] Paint
- [x] File Explorer
- [x] Task Manager
- [x] Command Prompt
- [x] Windows Terminal
- [x] `open` / `launch` / `start` / `run` routing

**Phase 7.2 status:** ✅ Completed

> **Known deferred issue:** the existing Command Prompt executor condition is intentionally left alone per the current development decision.

---

## Phase 7.3 — Filesystem Automation

**Initial implementation commit:** `7a29fd4a45367aa1a4fd0cc56b99e7bbaa0e2515`

The implementation introduced structured filesystem automation and subsequently received several refinement commits.

### Filesystem capabilities

- [x] Open folders
- [x] List directories
- [x] Find files
- [x] Create files
- [x] Create folders
- [x] Rename files
- [x] Rename folders
- [x] Move files
- [x] Copy files
- [x] Delete files
- [x] Delete folders
- [x] Special directory aliases
- [x] Filesystem path normalization
- [x] Ranked filename matching
- [x] Strongest-match filtering
- [x] Multiple-result presentation
- [x] Natural-language result selection
- [x] Numeric selection
- [x] Cardinal-word selection
- [x] Ordinal-word selection
- [x] Wrapped selections such as “the first one”
- [x] `number two` / `option one` style selections
- [x] Selection parser regression tests
- [x] Filesystem matching regression tests
- [x] Security authorization regression tests

### Subsequent Phase 7.3 refinement work

The following commits refined the Phase 7.3 implementation:

- `ad4c280d5176967853bf5261749fac687bc08551` — First changes requested
- `4ff46a7f0db5c1ea8a99608afd318ff100398e01` — Second change
- `de1c52089f5458c41c6e9fbb098be84c0160ea92` — Third Change
- `92004040cac4bc6552fc425fc95421d324413dd2` — Fourth Change
- `82e17bd6b90214faad0ebbb35d11ea20bc1cc99a` — Fifth Change
- `380d69196caa4fa6512006aebf01aafc4a482413` — sixth change
- `6a94f69bc81f0a6910c2f58831c7454ee1e97bd6` — Seventh Change
- `8c2d4d8d7cdac979703341aa165637d85a0599b8` — Eight change

These include the multiple-result selection UX, natural-language selection parsing, ranked file matching, and HUD integration.

**Phase 7.3 implementation status:** ✅ Implemented / refined

### Phase 7.3 validation checkpoint

The project owner reported completing the Phase 7.3 live validation checks locally on **2026-10-09**. The checks below are recorded as owner-verified; this editing session did not independently execute live desktop/voice tests.

- [x] Run complete automated regression suite — previously reported 22/22 tests passing (historical result; not rerun in this session)
- [x] Verify Porcupine hotword startup with the pinned legacy local version
- [x] Verify local Kokoro English TTS startup with `am_michael`
- [x] Verify Faster-Whisper English speech reaches OmniRoute
- [x] Fix and validate low-confidence/incorrect Whisper language classification for valid English transcripts
- [x] Test safe application automation through J.A.R.V.I.S.
- [x] Test folder open/list operations
- [x] Test file search
- [x] Test multiple-result selection
- [x] Test create/rename/move/copy using disposable test data
- [x] Test protected delete operations using disposable test data
- [x] Test authorization cancellation/failure paths
- [x] Test error handling for nonexistent targets
- [x] Complete remaining live E2E automation tests
- [x] Record final Phase 7.3 checkpoint
- [x] Record the completed checkpoint in this branch

**Current Phase 7 status:** ✅ Phase 7.3 validation complete according to the project owner's local report

---

# Phase 8 — J.A.R.V.I.S. Intelligence / Context

This is the next major intelligence-focused phase after Desktop Automation.

## Phase 8 Core Objective

> **Give JARVIS the ability to infer what the user means from imperfect speech, conversation history, memory, and current interaction state.**

The goal is to move JARVIS from a system that primarily reacts to literal transcripts into a **context-aware interpreting entity** that can recover intended meaning, maintain conversational continuity, and respond or act appropriately.

JARVIS should treat speech recognition output as an imperfect signal rather than blindly assuming the transcript is exactly what the user intended.

### Phase 8.1 — Contextual Interpretation Foundation

- [x] Create a dedicated contextual interpretation layer between STT and command/LLM handling
- [x] Preserve the raw STT transcript separately from the interpreted user meaning
- [x] Combine current transcript with recent conversation context
- [x] Combine current transcript with active interaction/task state
- [x] Resolve obvious STT errors using conversational context
- [x] Resolve pronouns and references such as “it”, “that”, “this”, “there”, and “the previous one”
- [x] Resolve incomplete or elliptical commands using context
- [x] Detect when the transcript is ambiguous rather than forcing an incorrect interpretation
- [x] Ask a clarification question only when context cannot safely determine the user's intent
- [x] Add regression tests for context-based interpretation
- [x] Run contextual-interpreter regression checkpoint — 27/27 tests passed at the original checkpoint (historical; not re-verified against the current branch head)

**Phase 8.1 status: 🟡 Partial implementation present; integration/closure remains open.**

The interpreter, structured result, contextual prompt, temporary interaction state, and interpreter tests are present in the branch. The full runtime path is not yet consistently context-aware:

- General interpretation in `engine/command.py` runs only when in-memory conversation history exists, so a fresh-session request bypasses it.
- Completed automation actions are not added to conversation history, limiting follow-ups such as “close that” or “move the previous one.”
- Raw and interpreted text are not persisted as separate fields; the result object keeps both only during interpretation.
- Low-confidence responses restore the raw transcript but also clear `needs_clarification`, which can suppress a clarification that the model requested.
- Re-run the automated suite against the current branch head before treating any historical test count as current.

These are Phase 8.1 integration-hardening tasks. They should be addressed before declaring 8.1 complete, even though much of the interpreter foundation is already implemented.

### Phase 8.2 — Long-Term Memory System

- [x] Design a dedicated JARVIS memory architecture instead of treating conversation history as memory
- [x] Separate episodic memory from persistent semantic memory
- [x] Store high-confidence durable user facts and preferences via selective LLM extraction
- [x] Store successful automation interaction events as episodic memories
- [x] Add explicit memory creation/update rules and confidence/importance gates
- [x] Prevent ordinary questions and low-value conversation from automatically becoming persistent memory through a heuristic extraction gate
- [x] Support query-relevance retrieval using lexical ranking over active memories
- [x] Supersede previous semantic values when a new value arrives for the same key
- [x] Support memory expiration; episodic records default to a configurable 90-day TTL
- [x] Add memory persistence/retrieval/update/expiry regression tests in `tests/test_memory.py`
- [ ] Run `pytest -v tests/test_memory.py` and the full suite in the local Python 3.11 environment

**Phase 8.2 status:** 🟡 Implementation committed; local regression execution remains pending. The implementation uses SQLite and lexical retrieval; embeddings/vector search and a dedicated memory-management HUD are not part of this sub-phase implementation.

### Phase 8.3 — User Profile / Preferences / Working Context

- [ ] Create a structured user-context/profile representation
- [ ] Store durable user preferences
- [ ] Store communication preferences
- [ ] Store relevant project/work context
- [ ] Track temporary active task state separately from long-term memory
- [ ] Track pending selections and unresolved conversational references
- [ ] Allow the contextual interpreter to use relevant user context
- [ ] Prevent unrelated personal/context information from being injected into prompts
- [ ] Add tests for context isolation and relevance

### Phase 8.4 — Conversation Summarization & Context Compression

- [ ] Summarize long conversations instead of continually expanding the raw prompt
- [ ] Maintain recent turns plus compact historical summaries
- [ ] Generate/update summaries when conversations become large
- [ ] Preserve important facts, decisions, unresolved tasks, and references in summaries
- [ ] Avoid losing important context during summarization
- [ ] Validate summarized-context conversations against equivalent full-history conversations
- [ ] Add regression tests for long-context continuity

### Phase 8.5 — Contextual Follow-Ups & Reference Resolution

- [ ] Support natural follow-ups without requiring the user to repeat context
- [ ] Resolve references to previously mentioned files, applications, people, tasks, and answers
- [ ] Connect Phase 7 selection state with Phase 8 contextual interpretation
- [ ] Understand responses such as “the first one”, “yes”, “no”, “that one”, and “do it”
- [ ] Preserve pending conversational state across multi-turn interactions
- [ ] Detect when a follow-up belongs to an existing task versus starting a new task
- [ ] Add multi-turn E2E tests for contextual follow-ups

### Phase 8.6 — Smarter Intent Detection

- [ ] Introduce structured semantic intent representation
- [ ] Distinguish conversation, information requests, automation requests, clarifications, confirmations, and cancellations
- [ ] Use contextual interpretation to improve intent detection when STT is imperfect
- [ ] Preserve deterministic routing for security-sensitive automation
- [ ] Convert interpreted automation intent into existing `AutomationAction` structures
- [ ] Do not allow LLM interpretation to bypass authorization/security gates
- [ ] Add ambiguous-intent and misheard-command regression tests

### Phase 8.7 — Intelligent Error / Fallback Handling

- [ ] Classify STT, interpretation, LLM, automation, authorization, and TTS failures separately
- [ ] Replace generic failure responses with context-appropriate recovery
- [ ] Retry transient LLM/provider failures when safe
- [ ] Recover gracefully from malformed/empty LLM responses
- [ ] Preserve conversation context across recoverable failures
- [ ] Ask the user for clarification when recovery requires missing information
- [ ] Add failure-recovery regression tests

### Phase 8.8 — LLM Provider / Model Fallback Strategy

This is limited to **runtime reliability and fallback behavior**. Full provider/model configuration remains Phase 10.

- [ ] Define a controlled fallback policy around the existing OmniRoute architecture
- [ ] Detect connection failures, timeouts, provider failures, and invalid responses
- [ ] Retry requests only when the failure is safely retryable
- [ ] Support controlled model/provider fallback where the existing runtime configuration permits it
- [ ] Preserve a consistent JARVIS response contract across fallback providers/models
- [ ] Log which fallback path was used for diagnostics
- [ ] Add provider/fallback regression tests
- [ ] Keep full provider selection/configuration for Phase 10

### Phase 8.9 — Intelligence Integration & E2E Validation

- [ ] Integrate contextual interpretation into the existing STT → command/automation → LLM pipeline
- [ ] Verify imperfect-transcript recovery using realistic speech-recognition errors
- [ ] Verify context-aware file/application references
- [ ] Verify multi-turn follow-up conversations
- [ ] Verify long-term memory retrieval
- [ ] Verify user preference/context retrieval
- [ ] Verify clarification behavior for genuinely ambiguous requests
- [ ] Verify automation security remains fail-closed after contextual interpretation
- [ ] Verify recoverable LLM/provider failures preserve conversation state
- [ ] Run complete Phase 8 automated regression suite
- [ ] Run complete Phase 8 live voice E2E suite
- [ ] Record final Phase 8 checkpoint
- [ ] Commit Phase 8 checkpoint

**Phase 8 status:** 🟡 Partial foundation present; overall Phase 8 is incomplete. Phase 8.2 and later sub-phases have not been implemented.

---

# Phase 9 — Advanced Voice & Vision

This is where the assistant becomes substantially more capable as a voice/vision assistant.

Possible areas:

- [ ] Better interruption / barge-in handling
- [ ] Improved wake-word reliability
- [ ] Speaker/voice personalization
- [ ] Screen/vision understanding
- [ ] Camera-based interaction
- [ ] Richer multimodal commands
- [x] FaceNet/MTCNN authentication foundation exists

Recent local Kokoro TTS work belongs to the broader voice capability work, but it does not by itself close Phase 9.

**Phase status:** ⏳ Not started

---

# Phase 10 — AI Provider / Model Configuration

This was the feature originally positioned as Phase 7 and was deliberately postponed while Desktop Automation was moved forward.

The Settings system will eventually support:

```
AI Provider
├── OmniRoute
├── OpenAI
├── Gemini
├── OpenRouter
└── Custom OpenAI-compatible

Model
API Key
Base URL
Test Connection
```

Planned checklist:

- [ ] AI provider selection
- [ ] OmniRoute configuration
- [ ] OpenAI configuration
- [ ] Gemini configuration
- [ ] OpenRouter configuration
- [ ] Custom OpenAI-compatible provider
- [ ] Model configuration
- [ ] API key configuration
- [ ] Base URL configuration
- [ ] Test Connection functionality
- [ ] Secure API-key storage
- [ ] Provider/model configuration regression testing

**Phase status:** ⏳ Not started

---

# Phase 11 — UI / Experience Polish

The cinematic UI receives its final dedicated polish pass.

- [ ] Smoother animations
- [ ] Better transitions
- [ ] Responsive behavior
- [ ] Loading states
- [ ] Richer visual feedback
- [ ] Performance optimization
- [ ] Accessibility
- [ ] Polished error states

**Phase status:** ⏳ Not started

---

# Phase 12 — Production / Release

Final release preparation:

```
Testing
→ Packaging
→ Installer
→ Environment setup
→ Logging
→ Crash recovery
→ Documentation
→ Release build
```

Checklist:

- [ ] Testing
- [ ] Packaging
- [ ] Installer
- [ ] Environment setup
- [ ] Logging
- [ ] Crash recovery
- [ ] Documentation
- [ ] Release build

**Phase status:** ⏳ Not started

---

# Current Roadmap Position

```
PHASE 6
  ✅ Conversational System
        ↓
PHASE 7
  ✅ Desktop Automation / Agent
      ├─ 7.1 ✅ Secure Automation Foundation
      ├─ 7.2 ✅ Desktop Application Control
      └─ 7.3 ✅ Filesystem Automation — local E2E validation reported complete
        ↓
PHASE 8
  🟡 Contextual foundation present; overall phase incomplete
      ├─ 8.1 🟡 Interpreter exists; runtime integration and validation open
      ├─ 8.2 🟡 Long-Term Memory — implementation committed; tests pending
      ├─ 8.3 ⏳ User Profile / Working Context
      ├─ 8.4 ⏳ Conversation Summarization
      ├─ 8.5 ⏳ Contextual Follow-Ups
      ├─ 8.6 ⏳ Smarter Intent Detection
      ├─ 8.7 ⏳ Intelligent Error / Fallback Handling
      ├─ 8.8 ⏳ LLM Provider / Model Fallback
      └─ 8.9 ⏳ Intelligence Integration & E2E Validation
        ↓
PHASE 9
  ⏳ Advanced Voice + Vision
        ↓
PHASE 10
  ⏳ AI Provider / Model Configuration
        ↓
PHASE 11
  ⏳ UI + Experience Polish
        ↓
PHASE 12
  ⏳ Production / Release
```

## Roadmap Rules

1. Check off work only after it has actually been implemented and/or tested.
2. A sub-phase is not closed merely because its code exists; its required validation/checkpoint must also be completed.
3. Do not silently move work between phases.
4. The Command Prompt executor issue is intentionally deferred and should not be treated as part of the current Phase 7.3 checkpoint unless explicitly reopened.
5. The roadmap should be updated as each phase/sub-phase is completed.
6. The Git history and this checklist together define the project's development progression.
7. Phase 8 must improve JARVIS's ability to infer **intended meaning**, not merely improve literal transcript handling.
8. Contextual interpretation must never bypass the existing deterministic automation security and authorization gates.
9. Full AI provider/model configuration remains part of Phase 10; Phase 8 only addresses runtime reliability and controlled fallback behavior.
