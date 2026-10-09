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
- [x] Run contextual-interpreter regression checkpoint — 27/27 tests passed at the original checkpoint (historical)
- [x] Add hardening regression tests for selective interpretation, clarification state, and transcript persistence
- [x] Run focused contextual-interpreter tests after the Phase 8.1 hardening commits — 16 passed locally on 2026-10-09
- [x] Run the full regression suite after the Phase 8.1 hardening commits — 53 passed, 6 dependency warnings, on 2026-10-09
- [x] Run the three new file-open routing/path regression tests — owner reports passing locally
- [x] Rerun the full regression suite after the file-open routing/path fix — owner reports passing locally (56 tests expected)
- [x] Complete live file-open clarification/path validation — owner reports the explicit README.md open succeeded

**Phase 8.1 status: ✅ Core contextual interpreter, file-open routing regression fix, automated checks, and reported live file-open validation completed.** Legacy automation routes are not all unified under the structured action-history pipeline; that remains integration work for Phase 8.9.

The latest hardening adds the following:

A live clarification test exposed a separate file-open routing gap: `open file <absolute path>` fell through to application-launch routing, and file completion used fuzzy name search even for an exact path. The branch now routes explicit file-open phrases to the `open_file` action and checks an exact path before fuzzy search. The project owner reports the three regression tests, complete suite, and live explicit-path open test all passed locally.

- In `auto` mode, microphone utterances are interpreted by default, including in fresh sessions, so standalone speech-recognition errors can be corrected.
- Recognized application launches such as `open Chrome` retain a deterministic fast path when no context requires interpretation.
- Typed text uses selective interpretation based on conversation context, relevant memory, pending interaction state, follow-up language, and target-sensitive actions.
- `JARVIS_INTERPRETATION_MODE=auto|always|off` controls the policy. `JARVIS_INTERPRETATION_MIN_CONFIDENCE` sets the default 0.70 threshold.
- Explicit clarification requests survive low-confidence results. Pending clarification state is retained if the user's answer cannot be interpreted confidently.
- Conversational MongoDB records preserve `user_text`, `raw_user_text`, `interpreted_user_text`, and structured interpretation metadata separately. Old readers can continue using `user_text`.
- Successful structured automation events keep the interpreted request in conversation context and record the raw transcript/interpretation confidence in episodic-memory metadata.
- The contextual interpreter still only produces meaning. Deterministic routing and the existing authorization/face-authentication gate remain responsible for execution.
- Added regression tests for fresh-session voice interpretation, fresh-session target actions, clear app launch fast paths, pending/context triggers, interpretation mode, explicit low-confidence clarification, boolean normalization, and raw/interpreted persistence.

Remaining work: some legacy automation routes (such as the older app/YouTube/messaging path) are not yet unified under the structured action-history path. The owner reports that the post-fix file-open regression tests, full suite, and live file-open test passed on 2026-10-09. The Phase 8.3 focused tests, full suite, and live preference-retrieval test are now reported passing by the project owner.

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
- [x] Run focused memory/context regression suite — 16/16 tests passed locally on 2026-10-09
- [x] Run the complete regression suite — 63/63 tests reported passing locally after Phase 8.3 profile/context changes (project owner report, 2026-10-09)

**Phase 8.2 status:** ✅ Implemented and automated regression suite passing. The implementation uses SQLite and lexical retrieval; embeddings/vector search and a dedicated memory-management HUD are not part of this sub-phase implementation.

### Phase 8.3 implementation checkpoint

Initial implementation is committed on `test-jarvis` across `engine/user_context.py`, contextual interpreter/command wiring, `.env.example`, and `tests/test_user_context.py`. Two interpreter tests cover profile context triggers and prompt isolation. Five profile tests cover category persistence, relevance filtering, unrelated-context exclusion, sensitive/low-confidence rejection, and backward-compatible categorization of existing `user.*`/`project.*` memory keys.

The project owner subsequently reported that all Phase 8.3 focused tests, the full suite, and live preference-retrieval test passed locally on 2026-10-09.

### Phase 8.3 — User Profile / Preferences / Working Context

- [x] Create a structured user-context/profile representation in `engine/user_context.py`
- [x] Store durable profile entries by category using the existing SQLite memory layer
- [x] Support preference and communication-preference categories
- [x] Support relevant project/work context
- [x] Keep temporary active interaction state separate in `engine/interaction_state.py`
- [x] Keep pending selections and unresolved clarifications in ephemeral interaction state
- [x] Pass query-relevant user profile context to the contextual interpreter and response prompt
- [x] Filter profile retrieval by lexical relevance and label profile text as reference data, not instructions
- [x] Add focused tests for profile persistence, category mapping, sensitive/low-confidence rejection, and relevance filtering
- [x] Run the new Phase 8.3 profile/context tests locally — owner reports passing
- [x] Run the full regression suite with Phase 8.3 changes — owner reports all tests passing (63 tests expected)
- [x] Complete live profile-preference retrieval tests in JARVIS — owner reports passing

### Phase 8.4 — Conversation Summarization & Context Compression

- [x] Add `engine/conversation_summary.py` for rolling conversation summaries
- [x] Maintain compact historical summary plus a configurable recent-turn window
- [x] Trigger summary refresh after `JARVIS_SUMMARY_TRIGGER_TURNS` is exceeded
- [x] Preserve goals, explicit facts, decisions, filenames/paths, constraints, unresolved questions and pending tasks in the summary prompt
- [x] Fall back to a bounded extractive recap if the LLM fails, returns an empty response, or returns an oversized summary
- [x] Add summary enable/disable and summary/input size settings to `.env.example`
- [x] Add tests for trigger behavior, rolling updates, context reset, disabled mode, LLM prompts, and fallback handling
- [x] Run Phase 8.4 focused summarization tests locally — 7/7 passed on 2026-10-09
- [x] Run the full regression suite with Phase 8.4 changes — 70/70 passed, 6 dependency warnings, on 2026-10-09
- [ ] Validate long-conversation continuity live in JARVIS after the summary trigger is crossed

**Phase 8.4 implementation checkpoint:** `engine/conversation_summary.py` and `ConversationManager` integration are committed, with seven regression tests in `tests/test_conversation_summarization.py`. The project owner ran the focused Phase 8.4 suite (7/7 passing) and full suite (70/70 passing with six dependency warnings) locally on 2026-10-09. Only the live long-conversation continuity check remains.

**Conversation viewer navigation fix (2026-10-09):** A live UI issue showed that continuing an existing saved conversation hid both the main HUD and SiriWave view after its response; pressing Escape closed the transcript viewer without restoring either view. The viewer close handler now restores the main HUD, and a visible **History** button opens the conversation history sidebar while leaving the current transcript underneath. The project owner reports the three UI regression tests and full suite passed locally after correcting the test's handler extraction; the user also confirmed the history-switch and Escape-recovery UI behavior works. Record the 73-test suite as owner-reported validation.

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

**Phase 8 status:** 🟡 In progress. Phases 8.1–8.3 are implemented and owner-validated; Phase 8.4 focused and full automated tests are passing, with live long-conversation validation still pending. Phases 8.5–8.9 remain open.

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
      ├─ 8.1 ✅ Context interpreter + explicit file-open path validated locally
      ├─ 8.2 ✅ Long-Term Memory — implementation and 63-test regression suite passing
      ├─ 8.3 ✅ Structured profile context implemented and validated by owner
      ├─ 8.4 🟡 Rolling summaries implemented; 70 automated tests pass; live continuity test pending
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
