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

**Commit:** `ec1c49d779d5f119efec430f0022ccd190e41ec1`

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

### Phase 7.3 checkpoint still required

The implementation is not considered fully closed until we complete live end-to-end testing.

- [x] Run complete automated regression suite — 22/22 tests passing
- [x] Verify Porcupine hotword startup with the pinned legacy local version
- [x] Verify local Kokoro English TTS startup with `am_michael`
- [x] Verify Faster-Whisper English speech reaches OmniRoute
- [x] Fix and validate low-confidence/incorrect Whisper language classification for valid English transcripts

- [ ] Test safe application automation through J.A.R.V.I.S.
- [ ] Test folder open/list operations
- [ ] Test file search
- [ ] Test multiple-result selection
- [ ] Test create/rename/move/copy using disposable test data
- [ ] Test protected delete operations using disposable test data
- [ ] Test authorization cancellation/failure paths
- [ ] Test error handling for nonexistent targets
- [ ] Complete remaining live E2E automation tests
- [ ] Record final Phase 7.3 checkpoint
- [ ] Commit Phase 7.3 checkpoint

**Current Phase 7 status:** 🔄 Phase 7.3 live E2E validation

---

# Phase 8 — J.A.R.V.I.S. Intelligence / Context

This is the next major intelligence-focused phase after Desktop Automation.

Potential scope:

- [ ] Better long-term memory
- [ ] User preferences/context
- [ ] Better conversation summarization
- [ ] Contextual follow-ups
- [ ] Smarter intent detection
- [ ] Improved error/fallback handling
- [ ] Provider/model fallback strategy

**Phase status:** ⏳ Not started

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
  🔄 Desktop Automation / Agent
      ├─ 7.1 ✅ Secure Automation Foundation
      ├─ 7.2 ✅ Desktop Application Control
      └─ 7.3 🔄 Filesystem Automation — Live E2E Checkpoint
        ↓
PHASE 8
  🟡 Intelligence + Context — Next
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
