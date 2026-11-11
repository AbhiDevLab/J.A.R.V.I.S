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

This phase is complete according to the implementation and owner-reported validation checkpoints below.

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
- [x] Validate long-conversation continuity live in JARVIS after the summary trigger is crossed — `rolling-summary-checkpoint` and its purpose were recalled on 2026-10-11 after multiple additional exchanges

**Phase 8.4 checkpoint — complete (2026-10-11):** `engine/conversation_summary.py` and `ConversationManager` integration are committed, with seven regression tests in `tests/test_conversation_summarization.py`. The owner confirmed live recall of `rolling-summary-checkpoint` and its purpose after multiple unrelated exchanges. The owner also ran the full regression suite after adding chat timestamps: 75/75 tests passed, with six dependency warnings. Timestamp UI and persistence tests passed 2/2.

**Conversation viewer navigation fix (2026-10-09):** A live UI issue showed that continuing an existing saved conversation hid both the main HUD and SiriWave view after its response; pressing Escape closed the transcript viewer without restoring either view. The viewer close handler now restores the main HUD, and a visible **History** button opens the conversation history sidebar while leaving the current transcript underneath. The project owner reports the three UI regression tests and full suite passed locally after correcting the test's handler extraction; the user also confirmed the history-switch and Escape-recovery UI behavior works. Record the 73-test suite as owner-reported validation.

### Phase 8.5 — Contextual Follow-Ups & Reference Resolution

- [ ] Support natural follow-ups across conversations/tasks without requiring the user to repeat context
- [x] Capture an immediate, bounded voice reply after a clarification/confirmation question without requiring another wake word; preserve pending state on timeout and reuse the existing Continuous Listening microphone owner
- [ ] Resolve references to previously mentioned files, applications, people, tasks, and answers
- [x] Connect Phase 7 selection state with Phase 8 contextual interpretation for pending candidate lists
- [x] Resolve clear ordinal and numeric choices deterministically before LLM interpretation (including wrapped forms such as “option 3”)
- [x] Keep descriptive/ambiguous selection replies on the contextual interpreter with candidate state supplied
- [x] Make filename matching tolerant to speech recognition replacing punctuation with spaces, while preserving literal exact-match priority
- [x] Add focused regression tests for ordinal selection, numeric wrappers, cancellation/“all”, and descriptive candidate references (`tests/test_contextual_followups.py`)
- [x] Add regression tests for hyphen/extension normalization and duplicate normalized filename candidates (`tests/test_speech_filename_matching.py`)
- [x] Route generic `open <filename>` requests into structured file-open resolution when no known application or folder matches
- [x] Add a regression test for generic speech-style file-open routing (`tests/test_open_file_routing.py`)
- [x] Run focused Phase 8.5, filename-matching, and file-open routing tests — 23/23 passed locally on 2026-10-11
- [x] Run the complete regression suite after the routing changes — 84/84 passed, with 6 dependency warnings, on 2026-10-11
- [x] Re-run the live ambiguous filename-selection test after the generic-open routing fix — JARVIS displayed both matching paths; the spoken selection “the second one” opened the file in folder B containing `TEST FILE B` (owner-verified 2026-10-11)

- [ ] Extend contextual resolution to prior files, applications, people, tasks, and answers across turns
- [ ] Preserve pending conversational state across multi-turn interactions beyond the current selection/clarification flows
- [ ] Distinguish continuation of a prior task from a new task and handle yes/no/do-it conservatively
- [ ] Add multi-turn end-to-end tests for contextual follow-ups


**Implementation checkpoint (2026-10-11):** Added `engine/reference_resolver.py` to build a bounded, recency-ranked reference index for recent file paths, known applications, contact names, user tasks, and JARVIS answers. The index is now supplied to contextual interpretation and conversational response prompts. Assistant turns that explicitly ask whether to proceed can create a pending confirmation state; clear cancellations are handled directly, while approvals must resolve to a concrete action above the configured confidence threshold. Focused regression cases were added to `tests/test_contextual_followups.py`. Validation is pending on the project owner's Windows environment; keep Phase 8.5 open until the focused and full regression suites and live multi-turn follow-up scenarios pass.

**Legacy fallback routing regression (2026-10-11):** Fixed a bug where the fallback's substring check for `open` treated questions such as “Which file did you just open?” as application-launch commands, causing Windows to try launching `which.exe`. Legacy open, YouTube, and message/call fallbacks now require explicit command prefixes. Added `tests/test_legacy_routing.py`; focused/full local validation is pending.

### Phase 8.6 — Smarter Intent Detection

- [x] Introduce structured semantic intent representation
- [x] Distinguish conversation, information requests, automation requests, clarifications, confirmations, and cancellations
- [x] Use contextual interpretation to improve intent detection when STT is imperfect
- [x] Preserve deterministic routing for security-sensitive automation
- [x] Convert interpreted automation intent into existing `AutomationAction` structures
- [x] Do not allow LLM interpretation to bypass authorization/security gates
- [x] Add ambiguous-intent and misheard-command regression tests


**Implementation checkpoint (2026-10-11):** Added `engine/intent_classifier.py` with structured `SemanticIntent`/`IntentClassification` results, conservative question-vs-command separation, confidence-aware contextual intent use, and explicit routing eligibility. Integrated it into `engine/command.py`: only classified automation requests reach the structured router or legacy automation fallbacks; the router still creates `AutomationAction` and the existing executor/security gate remains authoritative. Added `tests/test_intent_classifier.py`; project owner reported 52/52 focused tests and 106/106 full-suite tests passing on 2026-10-11 (six dependency warnings). Live intent-routing validation remains pending before this sub-phase can be closed.

### Phase 8.7 — Intelligent Error / Fallback Handling

Implementation checkpoint (2026-11-07, branch `phase-8-reliability-2026-11-07`):

- [x] Classify STT, interpretation, LLM, automation, authorization, and TTS failures separately in the user-facing recovery path
- [x] Replace generic failure responses with context-appropriate recovery for speech input, LLM availability, TTS, and uncertain automation execution
- [x] Retry transient LLM/provider failures when safe
- [x] Recover gracefully from malformed/empty LLM responses through bounded retries and controlled fallback
- [x] Preserve the failed request and pending dialogue state across recoverable LLM failures
- [x] Ask the user to explicitly retry, cancel, or submit a new request; never infer retry approval from unrelated input
- [x] Add focused LLM recovery tests in `tests/test_llm_client.py`
- [x] Add deterministic retry/cancel/new-request state tests in `tests/test_llm_recovery.py`
- [x] Add TTS/text-preservation and pending-request recovery tests in `tests/test_command_recovery.py`
- [x] Run the full CI regression suite — **106 passed, 5 warnings** on 2026-11-07

**Validation note:** Automated tests pass. Keep live Windows microphone/STT, TTS-device failure, authorization-denial, and uncertain desktop-action checks open until verified on the owner's Windows system.

### Phase 8.8 — LLM Provider / Model Fallback Strategy

This is limited to **runtime reliability and fallback behavior**. Full provider/model configuration remains Phase 10.

Implementation checkpoint (2026-11-07, branch `phase-8-reliability-2026-11-07`):

- [x] Define a controlled fallback policy around the existing OmniRoute architecture
- [x] Detect connection failures, timeouts, transient provider errors, HTTP errors, and malformed/empty responses
- [x] Retry only transient failures with bounded attempts and backoff
- [x] Support an explicitly configured fallback model through the same OmniRoute endpoint (`OMNIROUTE_FALLBACK_MODEL`)
- [x] Preserve the non-streaming string response contract across primary/fallback models
- [x] Log the selected model, retry attempts, and fallback path without logging credentials or raw response bodies
- [x] Add provider/retry/fallback tests in `tests/test_llm_client.py`
- [x] Run the full CI regression suite — **106 passed, 5 warnings** on 2026-11-07
- [x] Keep full provider selection/configuration for Phase 10

**Scope guard:** No direct OpenAI/Gemini/OpenRouter provider selection was added. That remains Phase 10.

### Phase 8.9 — Intelligence Integration & E2E Validation

- [x] Consolidate per-turn conversation, memory, profile, reference, application-activity, and pending-interaction context into `engine/intelligence_context.py`
- [x] Integrate the shared context snapshot into the typed/voice command path used by contextual interpretation and LLM response generation
- [x] Keep verified application activity available to interpretation while excluding it from the general response context
- [x] Keep extracted document contents out of the shared context snapshot and long-term memory
- [x] Add regression tests for source composition, prompt-context separation, and empty-context behavior in `tests/test_intelligence_context.py`
- [x] Integrate contextual interpretation into the post-STT command/automation → LLM pipeline and cover it with command-pipeline E2E tests; physical STT handoff remains part of live Windows validation
- [x] Add command-pipeline E2E regressions for cross-turn file references and pending approvals; verify an approved high-risk delete still passes through the authorization gate
- [x] Add real command-pipeline E2E regressions for high-confidence speech correction and low-confidence clarification without action execution
- [x] Add command-pipeline coverage proving retrieved SQLite memory and relevant profile preferences reach both contextual interpretation and response generation
- [x] Add command-pipeline coverage for genuinely ambiguous voice requests and preservation of pending dialogue state after a recoverable provider failure
- [x] Record the source-verified Stanford OpenJarvis capability map and selective adoption rules in `docs/stanford-openjarvis-reference.md`
- [x] Verify imperfect-transcript recovery using realistic speech-recognition errors — owner-verified: “open load pad” was correctly interpreted as “open Notepad” and opened once (2026-11-12)
- [x] Verify context-aware file references through the real command pipeline and deterministic file router (automated E2E)
- [x] Verify multi-turn file references and pending confirmation continuation (automated E2E)
- [x] Verify persistent SQLite memory retrieval reaches interpretation and answer generation (automated E2E)
- [x] Verify relevant user profile/preferences reach interpretation and answer generation (automated E2E)
- [x] Verify low-confidence and genuinely ambiguous requests stop for clarification without executing (automated E2E)
- [x] Verify contextual pending approval still passes through the existing high-risk authorization gate (automated E2E)
- [x] Verify interpreter provider timeout preserves the request and pending selection for explicit retry (automated E2E)
- [x] Run complete regression suite on GitHub Actions — PR #28, run #117: regression and Windows voice-contract jobs passed
- [ ] Run complete Phase 8 live Windows voice E2E suite — initial owner-verified STT correction passed; remaining real-device context, memory, clarification and failure-recovery scenarios still need validation
- [ ] Record final Phase 8 checkpoint
- [ ] Commit Phase 8 checkpoint

### Phase 8.10 — Privacy-conscious Interaction Tracing

- [x] Add a local SQLite interaction-trace store with opaque trace IDs and an explicit metadata allowlist
- [x] Add trace opt-out, configurable local database path, 1–365 day retention and a 50,000-event hard cap
- [x] Instrument command start, contextual interpretation, intent classification, clarification, automation outcome, response generation, provider failure and interruption
- [x] Keep transcripts, prompts, model responses, document content, paths, shell arguments, tool output and credentials out of the trace schema
- [x] Document trace storage, privacy boundaries, configuration and local inspection
- [x] Pass automated trace privacy/lifecycle and command-pipeline regression tests in CI — PR #29, run #121: full regression and Windows voice-contract jobs passed
- [ ] Owner-verify the local trace database on Windows and inspect representative events
- [ ] Confirm opt-out prevents trace database creation on the target machine

**Phase status:** 🟡 Implementation and CI validation complete; owner-side Windows storage/opt-out verification pending

---

**Phase 8 status:** 🟡 In progress. Phase 8.9's post-STT command pipeline now has automated end-to-end coverage for contextual transcript correction, file references, multi-turn approval continuation, real SQLite memory and profile retrieval, ambiguous-request clarification, fail-closed authorization and provider-timeout recovery. The owner reports that the live “open load pad” → “open Notepad” speech-correction test worked. The complete regression suite and Windows voice-contract job passed GitHub Actions run #117 after PR #28. Remaining work is the broader live Windows voice/context/memory/security/failure-recovery validation and the final Phase 8 checkpoint; no final completion is claimed yet.

---

# Phase 9 — Advanced Voice & Vision

This is where the assistant becomes substantially more capable as a voice/vision assistant.

## Phase 9.1 — Continuous Listening Engine

- [x] Add an opt-in continuous listening preference, disabled by default
- [x] Start hands-free capture only after successful face or voice authentication
- [x] Reuse the contextual voice command pipeline for each captured utterance
- [x] Use bounded phrase capture and silence-based endpoint detection
- [x] Keep the Porcupine process from competing for the microphone while continuous mode is active
- [x] Add a visible live listening-status indicator
- [x] Add an accessible one-tap voice-mode waveform button beside the one-shot microphone in both composers
- [x] Remove the separate continuous-listening settings checkbox; the voice-mode button controls the existing authenticated listener and persists the preference
- [x] Keep the one-shot microphone separate and disabled while continuous mode owns the microphone
- [x] Support the voice command "stop listening" and an immediate UI pause control
- [x] Verify live Windows microphone ownership and repeated hands-free turns (owner-verified on Windows, 2026-11-07)
- [x] Verify stop/restart behavior and the existing wake-word mode after continuous mode is disabled (owner-verified on Windows, 2026-11-07)

**UI control refinement (2026-11-10):** Replaced the continuous-listening settings checkbox with an accessible ChatGPT-style waveform button in the main and conversation composers. Both controls invoke the existing authenticated single-worker listener; the Python listener remains authoritative for active-state updates. The one-shot microphone remains a separate control and is disabled while continuous listening owns the microphone. The live listening indicator and pause fallback remain available. Automated UI lifecycle coverage is added in `tests/test_continuous_listening_ui.py`; local Windows interaction validation is required before recording this UI refinement as owner-verified.

**Scope note:** Phase 9.1 is a sequential, half-duplex listening loop. The microphone is not opened while JARVIS is processing or speaking, which prevents its own TTS output from being transcribed. Voice barge-in without a wake word, acoustic echo cancellation, and full-duplex capture remain Phase 9.2 work.

Possible areas:

- [ ] Better interruption / barge-in handling
- [ ] Improved wake-word reliability
- [ ] Speaker/voice personalization
- [ ] Screen/vision understanding
- [ ] Camera-based interaction
- [ ] Richer multimodal commands
- [x] FaceNet/MTCNN authentication foundation exists

Recent local Kokoro TTS work belongs to the broader voice capability work, but it does not by itself close Phase 9.

**Validation checkpoint (2026-11-08):** Owner-reported live Windows verification completed. The automated suite passed **163 tests**, with 6 dependency warnings and no failures. Continuous Listening, consecutive commands, stop/pause, microphone handoff, Notepad open/read, and wake-word restoration were verified.

**Phase status:** ✅ Phase 9.1 validated

---

## Phase 9.2 — Advanced Voice Interaction

- [x] Add one-shot wake-word-free follow-up listening when a voice-originated assistant turn explicitly awaits a user answer
- [x] Keep reply capture bounded and return to normal wake-word operation on timeout; do not create a second microphone reader while Continuous Listening owns the device
- [ ] Validate follow-up timing, timeout recovery and question/answer handoff on Windows hardware

- [x] Add TTS-window-only Porcupine microphone handoff while Continuous Listening is enabled
- [x] Route a wake-word hit during Kokoro/SAPI5 playback into the shared TTS interrupt event
- [x] Ignore wake-word hits outside the TTS window in continuous mode to prevent duplicate activation flows
- [x] Add bounded adaptive-energy VAD and phrase-endpoint configuration
- [x] Add focused regression tests for microphone gating, interruption routing, and VAD configuration
- [x] Add regression coverage for TTS consuming the shared interrupt event and cleaning up playback state
- [x] Add a Windows CI job for mocked TTS interruption and playback-cleanup regression tests
- [x] Run the complete pytest suite and inspect CI — GitHub Actions run #43: **149 passed, 5 warnings** (2026-11-08)
- [ ] Validate barge-in timing and microphone handoff on Windows hardware
- [ ] Implement wake-word-free speech barge-in after reliable AEC is available
- [x] Investigate Windows-compatible AEC candidates and capture requirements (Echoff alpha, pywebrtc-audio beta, Windows AEC APO); integration remains pending
- [ ] Validate no TTS self-triggering, false interruptions, or competing microphone readers

**Implementation note:** The current increment is wake-word barge-in: say "Jarvis" during playback to stop JARVIS. It does not yet support interrupting with arbitrary speech. Acoustic echo cancellation and full-duplex capture remain open; see `docs/phase-9.2-voice-interaction.md`.

- [x] Add isolated optional Echoff 0.3.0 probe dependency without changing normal runtime requirements
- [x] Document repeatable Windows AEC device discovery, capture, privacy, and acceptance procedure
- [ ] Run AEC probe on the target Windows microphone and output endpoints
- [ ] Review raw/AEC recordings and confirm near-end speech preservation
- [ ] Integrate a single-owner AEC capture path only after hardware acceptance

**Phase status:** 🟡 Implementation started; automated and live validation pending

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
      └─ 7.3 ✅ Filesystem Automation
        ↓
PHASE 8
  🟡 Intelligence / Context — final owner-side Windows validation open
      ├─ 8.1 ✅ Contextual interpretation foundation
      ├─ 8.2 ✅ SQLite semantic + episodic memory
      ├─ 8.3 ✅ Structured profile/preferences context
      ├─ 8.4 ✅ Rolling conversation summaries
      ├─ 8.5 🟡 Reference resolution + immediate answer capture implemented; broader live validation open
      ├─ 8.6 🟡 Structured intent detection; live routing validation open
      ├─ 8.7 🟡 Error recovery; live device/failure validation open
      ├─ 8.8 ✅ OmniRoute bounded retry/fallback implementation
      ├─ 8.9 🟡 Shared context integration; full live E2E validation open
      └─ 8.10 🟡 Interaction tracing; local storage/opt-out validation open
        ↓
PHASE 9
  🟡 Advanced Voice + Vision
      ├─ 9.1 ✅ Continuous Listening Engine — core live validation complete
      └─ 9.2 🟡 Advanced Voice Interaction — pending-answer capture implemented; hardware validation open
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
