# J.A.R.V.I.S — Just A Rather Very Intelligent System

> **Next-generation Windows desktop AI assistant • Python • Eel • Computer Vision • Voice • LLMs • Desktop Automation • Context**

J.A.R.V.I.S is a Windows-focused personal desktop AI assistant that combines **biometric authentication, speech recognition, local neural TTS, conversational AI, contextual interpretation, structured desktop automation, Android/ADB control, persistent conversation history, and a cinematic HUD interface**.

The project is deliberately engineered as more than a chatbot: the architecture separates **speech, interpretation, conversation, automation, security, execution, and presentation** so individual capabilities can be tested and evolved independently.

> **Current development branch:** `test-jarvis`

---

# 🚀 What J.A.R.V.I.S Can Do

## 🔐 1. Secure Authentication

J.A.R.V.I.S supports layered local authentication:

- Face authentication using **MTCNN-assisted face detection + FaceNet/InceptionResnetV1 embeddings**.
- Configurable similarity threshold.
- Consecutive-frame verification.
- Configurable authentication timeout.
- Voice phrase fallback.
- High-risk automation uses a deterministic security gate.
- Protected actions require:
  1. Explicit voice confirmation.
  2. Successful face authentication.
- Authorization fails closed rather than allowing an uncertain action.
- Authentication data can remain local and is excluded from version control.

The LLM/context layer does **not** bypass the deterministic security boundary.

---

# 🎙️ 2. Speech Recognition

J.A.R.V.I.S can use local speech recognition through **Faster-Whisper**.

Capabilities include:

- Local transcription.
- Automatic language detection.
- English and Hindi handling.
- CPU/GPU-aware model initialization.
- Configurable Whisper model.
- Configurable beam size.
- Configurable language-detection segments.
- English transcript recovery when Whisper produces an unreliable language classification.
- Optional Google Speech Recognition fallback.

Typical pipeline:

~~~text
Microphone
    ↓
Speech Recognition
    ↓
Transcript + detected language
    ↓
Contextual interpretation
    ↓
Command / Conversation
~~~

---

# 🧠 3. Conversational AI via OmniRoute

J.A.R.V.I.S uses a provider-neutral **OmniRoute** client through its OpenAI-compatible `/chat/completions` interface.

This keeps J.A.R.V.I.S independent from a single LLM vendor while allowing the local OmniRoute layer to control the configured model/provider.

Capabilities:

- Configurable model.
- Configurable local OmniRoute base URL.
- OpenAI-compatible request format.
- Non-streaming responses.
- Provider/model information logged for diagnostics.
- Compatible with single-model or OmniRoute routing configurations.
- OmniRoute can provide model/provider fallback when configured externally.

The JARVIS application itself does not need to know the credentials of every downstream provider; those are handled by the OmniRoute layer.

---

# 🧩 4. Context-Aware Interpretation

A major Phase 8 capability is the **contextual interpretation layer**.

Instead of assuming speech-to-text output is perfect, J.A.R.V.I.S can treat it as an imperfect signal and use:

- Current transcript.
- Recent conversation history.
- Active interaction state.
- User language.
- Pending task context.

to infer the user's intended meaning.

Examples:

~~~text
User: "open my resumy"

Context:
"We were discussing my resume."

JARVIS interpretation:
"open my resume"
~~~

It can also resolve contextual references such as:

- "it"
- "that"
- "this"
- "there"
- "the previous one"
- "the first one"
- incomplete follow-up commands

The interpretation layer returns structured information including:

~~~text
raw_transcript
interpreted_query
intent
confidence
needs_clarification
clarification_question
used_context
~~~

The runtime uses a selective policy instead of sending every request to a second LLM call. In `auto` mode, microphone speech is interpreted by default so standalone speech-recognition errors can be corrected; clear known application launches such as `open Chrome` use a deterministic fast path when no context needs resolution. Typed text is interpreted when conversation history, relevant stored memory, pending interaction/clarification, follow-up wording, or a target-sensitive action suggests it can help.

Configuration:

~~~env
JARVIS_INTERPRETATION_MODE=auto
JARVIS_INTERPRETATION_MIN_CONFIDENCE=0.70
~~~

Set the mode to `always` to interpret every non-empty utterance, or `off` to disable the interpreter. Explicit clarification requests are preserved even below the rewrite-confidence threshold. Pending clarification state remains active if the answer is still too uncertain.

For persisted chat turns, the effective `user_text` remains backward-compatible, while `raw_user_text`, `interpreted_user_text`, and interpretation metadata are saved separately when MongoDB persistence is available.

### Safety boundary

Contextual interpretation **does not execute actions**.

It only produces meaning for the downstream command/conversation system. Existing deterministic routing and authorization remain responsible for execution.

---

# 💬 5. Conversation Context

J.A.R.V.I.S maintains a conversation manager that provides:

- Conversation IDs.
- Recent-turn in-memory context.
- Configurable context window.
- New-conversation support.
- Loading of saved conversations.
- Optional MongoDB persistence.
- Compact LLM-ready conversation context.

Configuration:

~~~env
MONGODB_URI=mongodb://127.0.0.1:27017/jarvis
JARVIS_CHAT_COLLECTION=chats
JARVIS_CONTEXT_TURNS=8
~~~

Conversation persistence is separate from the dedicated long-term memory subsystem below.

### Phase 8.2 — Persistent Long-Term Memory

J.A.R.V.I.S now has a dedicated memory layer in `engine/memory.py`, separate from the recent-turn conversation manager and temporary interaction state.

- **Semantic memory:** stores high-confidence, durable, non-sensitive user-stated facts, preferences, and project context.
- **Episodic memory:** records successful structured automation actions with their user request and outcome.
- **Local persistence:** uses SQLite from Python's standard library; it does not require MongoDB or a vector database.
- **Memory updates:** a new semantic value with the same key supersedes the active prior value while retaining inactive history.
- **Relevance retrieval:** ranks memories by lexical overlap, importance, and memory type. Only query-relevant entries are added to the LLM/context-interpreter prompt.
- **Expiration:** episodic memories expire after a configurable period (90 days by default); explicit TTLs are supported for other temporary entries.
- **Selective extraction:** an LLM extraction prompt is attempted only for user utterances that look like durable first-person statements. Confidence thresholds, length checks, and sensitive-term filtering gate storage.
- **Memory management API:** the module exposes helpers to list, forget, clear, retrieve, and format memory for context. A dedicated HUD management panel is not yet implemented.

Configuration:

~~~env
JARVIS_MEMORY_ENABLED=1
JARVIS_MEMORY_DB_PATH=data/jarvis_memory.db
JARVIS_MEMORY_AUTO_EXTRACT=1
JARVIS_MEMORY_MIN_CONFIDENCE=0.72
JARVIS_MEMORY_CONTEXT_ITEMS=5
JARVIS_EPISODIC_MEMORY_TTL_DAYS=90
~~~

The local database is covered by the repository's database ignore rules. Back up or delete it separately from MongoDB chat history. Disabling memory with `JARVIS_MEMORY_ENABLED=0` prevents memory reads and writes. Automatic extraction can be disabled independently with `JARVIS_MEMORY_AUTO_EXTRACT=0`.

Memory inspection and cleanup are available to Python callers:

~~~python
from engine.memory import list_memories, forget_memory, clear_memories

memories = list_memories()
forget_memory(key="user.preferred_voice")  # Permanently forget all versions of this fact.
clear_memories(memory_type="episodic")     # Permanently delete all episodic memories.
~~~

There is not yet a HUD control for memory review/cleanup. Use these helpers deliberately: `clear_memories()` without a type deletes all memory records.

**Current boundaries:** retrieval is lexical, not embedding/vector-based; automatic extraction adds an LLM request only for likely durable statements; there is no dedicated UI for reviewing or deleting memories. The wider Phase 8 remains incomplete while conversation summarization, broader follow-up resolution, structured intent detection, failure recovery, provider fallback, and end-to-end validation remain open. Phase 8.3 profile/context changes are implemented in the branch but still require local regression validation.


### Phase 8.3 — Structured User Profile / Preferences / Working Context

The new `engine/user_context.py` module provides a structured profile layer over the existing SQLite memory store.

- Stores profile facts under stable, category-tagged keys: `profile.preference.*`, `profile.communication.*`, `profile.project.*`, and `profile.general.*`.
- Exposes `save_profile_item()`, `get_profile_items()`, and `build_user_profile_context()` for durable profile creation, inspection, and query-relevant retrieval.
- Recognizes compatible existing semantic keys such as `user.preferred_voice`, `user.response_style`, and `project.jarvis.stack` as profile context without migrating or duplicating them.
- Sends only lexically relevant profile items to the contextual interpreter and response prompt. Profile text is labelled as reference data, not instructions; unrelated profile entries should not be injected.
- Keeps temporary selections/clarifications in `engine/interaction_state.py`, separate from durable SQLite profile facts.
- The new `JARVIS_PROFILE_CONTEXT_ITEMS=5` setting caps profile items included per query.
- Regression tests cover profile persistence/categorization, relevance filtering, sensitive/low-confidence rejection, legacy-key compatibility, and interpreter wiring.

**Validation status:** the project owner reports the profile-specific tests, updated full suite, and live preference-retrieval check passing locally on 2026-10-09.


### Phase 8.4 — Conversation Summarization & Context Compression

J.A.R.V.I.S now has a rolling summary layer in `engine/conversation_summary.py`, integrated with `ConversationManager`.

- After the conversation exceeds the configured summary trigger, earlier turns are summarized and the configured recent-turn window is retained verbatim.
- The rolling summary is updated with new older turns, and `build_context()` supplies both the summary and recent turns to the contextual interpreter and response prompt.
- The summary prompt is instructed to preserve goals, key facts, decisions, filenames/paths, constraints, unresolved questions and pending tasks without inventing outcomes or following instructions embedded in the transcript.
- If OmniRoute fails, returns an empty response, or returns an overlong summary, JARVIS falls back to a bounded extractive recap instead of dropping the older turns without a summary.
- Starting a new conversation clears its in-memory summary. Saved conversation loading rebuilds a summary from older loaded turns when the trigger is exceeded.
- Summary is session-memory state, not a new database: when MongoDB history is available, loading a saved conversation can reconstruct it; with no persistence, it does not survive application restart.
- Seven regression tests cover trigger behavior, rolling updates, conversation reset, disabled mode, summary prompt content, and LLM-failure/empty-response fallback.

Configuration:

~~~env
JARVIS_CONVERSATION_SUMMARY_ENABLED=1
JARVIS_SUMMARY_TRIGGER_TURNS=12
JARVIS_CONVERSATION_SUMMARY_MAX_CHARS=1800
JARVIS_SUMMARY_INPUT_MAX_CHARS=12000
~~~

**Validation status:** implementation and regression tests are committed; local focused tests, the complete suite, and long-conversation live continuity checks remain to be run.

---

# 🖥️ 6. Structured Desktop Automation

J.A.R.V.I.S has a structured automation layer based around actions, routing, execution and authorization.

The automation system can handle:

### Applications

Natural-language application commands can launch configured Windows applications, including:

- Chrome
- Edge
- VS Code
- Spotify
- Notepad
- Calculator
- Paint
- File Explorer
- Task Manager
- Command Prompt
- Windows Terminal

Example:

~~~text
"Open VS Code."
"Launch Spotify."
"Start File Explorer."
~~~

---

# 📁 7. Filesystem Automation

The structured filesystem layer supports:

### Files

- Find
- Open
- Create
- Rename
- Move
- Copy
- Delete

### Folders

- Open
- List
- Create
- Rename
- Move
- Delete

### Intelligent matching

File resolution uses ranked matching such as:

1. Exact filename
2. Exact filename stem
3. Substring/stem match

Matching is case-insensitive and can suppress weaker matches when a stronger match is available.

### Multiple-result selection

J.A.R.V.I.S can present multiple matches and understand selections such as:

~~~text
"the first one"
"number two"
"option one"
"second"
"the third file"
~~~

This selection state is designed to connect with the contextual interpretation layer.

---

# 🛡️ 8. Security-Aware Automation

Automation is intentionally separated from conversational generation.

High-risk operations are classified and routed through the authorization layer.

Examples include:

- File/folder deletion.
- Shell/PowerShell execution.
- Process termination.
- System power operations.
- System-setting changes.
- Software installation/uninstallation.

The architecture follows:

~~~text
Natural language
      ↓
Context / Intent
      ↓
AutomationAction
      ↓
Risk classification
      ↓
Authorization gate
      ↓
Executor
~~~

The LLM cannot directly bypass the authorization layer.

For protected actions:

~~~text
Protected request
      ↓
Explicit confirmation
      ↓
Face authentication
      ↓
Execution
~~~

---

# 📱 9. Android / ADB Automation

J.A.R.V.I.S can interact with Android devices through **ADB**.

Supported integrations include:

- Phone calls.
- SMS.
- Device preparation through `device.bat`.
- USB ADB.
- Wireless ADB when the device is configured for it.

This allows desktop voice commands to trigger actions on a connected Android device.

---

# 📲 10. External Application Automation

Existing integrations include:

- YouTube playback.
- WhatsApp messaging.
- WhatsApp calls.
- WhatsApp video calls.
- Browser/application launching.
- Windows application aliases.
- Android/ADB operations.

These are routed through the structured automation system where applicable.

---

# 🔊 11. Local Neural TTS

J.A.R.V.I.S uses **Kokoro-82M** as the primary local neural TTS engine.

Advantages:

- Runs locally after model assets are available.
- No recurring TTS API quota.
- Configurable English voice.
- Configurable Hindi voice.
- Configurable speech speed.
- Sentence-level pause support.
- Interruptible playback infrastructure.
- SAPI5 fallback if Kokoro is unavailable.

Example configuration:

~~~env
JARVIS_TTS_ENABLED=1
JARVIS_TTS_ENGINE=kokoro
JARVIS_TTS_LANGUAGE=auto
JARVIS_TTS_EN_VOICE=bm_george
JARVIS_TTS_HI_VOICE=hm_omega
JARVIS_KOKORO_SPEED=0.92
JARVIS_TTS_SENTENCE_PAUSES=1
~~~

### Voice audition status

A standalone voice-audition helper has been planned, but `tests/voice_audition.py` is **not present in the inspected `test-jarvis` branch snapshot**. The earlier documented command must not be treated as available until the script is added and committed.

---

# 🎭 12. JARVIS Personality

The response layer includes a dedicated JARVIS persona prompt.

The intended delivery is:

- Calm.
- Confident.
- Precise.
- Understated.
- Technically competent.
- Concise by default.
- Professional rather than generic-chatbot-like.
- Occasional subtle dry wit.
- Context-aware.
- Natural use of "Sir" rather than forced repetition.

The persona explicitly avoids generic filler such as:

~~~text
"Sure!"
"Absolutely!"
"I'd be happy to help!"
"Great question!"
"No worries!"
~~~

Failures are intended to communicate:

1. What failed.
2. Why it failed when known.
3. What useful next action is available.

This separates **JARVIS behavior/personality** from the underlying model provider.

---

# 🎨 13. Cinematic HUD

The Eel frontend provides a native-like desktop experience.

Current UI functionality includes:

- Animated startup/loading interface.
- Face-authentication presentation.
- Webcam authentication feedback.
- SiriWave voice visualization.
- Cinematic HUD/orbiting visual design.
- Listening/recognizing/thinking status transitions.
- Main conversation display.
- Markdown-aware assistant responses.
- Response copy controls.
- Conversation/history viewer.
- Settings panel.
- Voice response controls.
- Responsive rendering for long filesystem results.

The frontend is intentionally kept separate from the Python engine so presentation can evolve without rewriting the core automation architecture.

---

# 🏗️ Architecture

~~~text
                    ┌──────────────────────┐
                    │   Porcupine Hotword  │
                    │       Process        │
                    └──────────┬───────────┘
                               │
                               ▼
                     JARVIS Main Process
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
      Eel HUD              Speech/STT         Authentication
          │                    │                    │
          │              Faster-Whisper             ├── Face
          │                    │                    └── Voice
          │                    ▼
          │            Context Interpreter
          │                    │
          │              ┌─────┴─────┐
          │              ▼           ▼
          │        Conversation   Automation
          │              │           │
          │              │      AutomationAction
          │              │           │
          │              │      Security Gate
          │              │           │
          │              │        Executor
          │              │           │
          │              │     ┌─────┼──────┐
          │              │     ▼     ▼      ▼
          │              │   Files  Apps   ADB
          │              │
          │              ▼
          │          OmniRoute LLM
          │
          ▼
       JARVIS HUD
          │
          ▼
      Kokoro TTS
          │
          ▼
       Audio Output
~~~

---

# 📂 Project Structure

~~~text
J.A.R.V.I.S/
│
├── engine/
│   ├── auth/
│   │   ├── recognizer.py
│   │   ├── voice_auth.py
│   │   ├── capture_samples.py
│   │   └── trainer.py
│   │
│   ├── automation/
│   │   ├── actions.py
│   │   ├── applications.py
│   │   ├── dialogue.py
│   │   ├── executor.py
│   │   ├── filesystem.py
│   │   ├── router.py
│   │   └── security.py
│   │
│   ├── command.py
│   ├── context_interpreter.py
│   ├── conversation.py
│   ├── conversation_summary.py
│   ├── interaction_state.py
│   ├── memory.py
│   ├── user_context.py
│   ├── llm_client.py
│   ├── persona.py
│   ├── stt.py
│   └── tts.py
│
├── tests/
│   ├── test_context_interpreter.py
│   ├── test_conversation_summarization.py
│   ├── test_dialogue_selection.py
│   ├── test_filesystem_matching.py
│   ├── test_memory.py
│   ├── test_open_file_routing.py
│   ├── test_persona_tts.py
│   ├── test_security_authorization.py
│   └── test_user_context.py
│
├── www/
│   ├── index.html
│   ├── controller.js
│   └── style.css
│
├── main.py
├── run.py
├── device.bat
├── requirements.txt
├── .env.example
└── JARVIS_ROADMAP.md
~~~

---

# ⚙️ Installation

## Requirements

- Windows 10/11
- Python 3.11 recommended
- Git
- Webcam
- Microphone
- Internet access for OmniRoute-backed LLM requests and optional Google STT fallback
- ADB for Android automation
- MongoDB optional for persistent conversation history
- CUDA-capable GPU optional for accelerated ML workloads

## Clone

~~~bash
git clone https://github.com/AbhiDevLab/J.A.R.V.I.S.git
cd J.A.R.V.I.S
~~~

## Virtual environment

~~~bash
python -m venv envjarvis
.\\envjarvis\\Scripts\\activate
~~~

## Dependencies

Install the packages listed in `requirements.txt`.

The current environment includes dependencies for:

- Eel
- Faster-Whisper
- SpeechRecognition / PyAudio
- Kokoro
- soundfile
- espeak-ng loader
- pyttsx3
- pygame
- PyTorch / TorchVision
- FaceNet / facenet-pytorch
- OpenCV
- Pillow / NumPy
- pyautogui
- pywhatkit
- Porcupine
- requests
- optional pymongo

---

# 🔧 Environment Configuration

Create `.env` from `.env.example`.

## OmniRoute

~~~env
LLM_PROVIDER=omniroute
OMNIROUTE_BASE_URL=http://localhost:20128/v1
OMNIROUTE_API_KEY=your_omniroute_api_key
OMNIROUTE_MODEL=your_model_or_team
OMNIROUTE_TIMEOUT=180
~~~

J.A.R.V.I.S communicates with OmniRoute locally. The configured OmniRoute model can be a single model or a routing/team configuration.

## Authentication

~~~env
JARVIS_AUTH_ID=1
JARVIS_AUTH_FRAMES=3
JARVIS_AUTH_TIMEOUT=20
JARVIS_AUTH_THRESHOLD=0.8
JARVIS_AUTH_OVERLAY_SECONDS=4
~~~

## Voice authentication

~~~env
JARVIS_VOICE_ENABLED=1
JARVIS_VOICE_PHRASE=genius billionaire playboy philanthropist
JARVIS_VOICE_TIMEOUT=20
~~~

## Speech recognition

~~~env
JARVIS_STT_ENABLED=1
JARVIS_STT_MODEL=small
JARVIS_STT_DEVICE=auto
JARVIS_STT_COMPUTE_TYPE=auto
JARVIS_STT_BEAM_SIZE=5
JARVIS_STT_LANGUAGE_DETECTION_SEGMENTS=2
JARVIS_STT_FALLBACK_GOOGLE=1
~~~

## TTS

~~~env
JARVIS_TTS_ENABLED=1
JARVIS_TTS_ENGINE=kokoro
JARVIS_TTS_LANGUAGE=auto
JARVIS_TTS_EN_VOICE=bm_george
JARVIS_TTS_HI_VOICE=hm_omega
JARVIS_KOKORO_SPEED=0.92
JARVIS_TTS_SENTENCE_PAUSES=1
~~~

## Conversation

~~~env
MONGODB_URI=mongodb://127.0.0.1:27017/jarvis
JARVIS_CHAT_COLLECTION=chats
JARVIS_CONTEXT_TURNS=8
~~~

> Never commit real API keys, `.env`, biometric samples, embeddings, private databases, or test audio.

---

# ▶️ Running J.A.R.V.I.S

Full mode:

~~~bash
python run.py
~~~

GUI/main process:

~~~bash
python main.py
~~~

When `run.py` is used, the application manages the main JARVIS process and hotword listener.

---

# 🧪 Testing

The current checked-in test modules include:

- `tests/test_context_interpreter.py`
- `tests/test_conversation_summarization.py`
- `tests/test_dialogue_selection.py`
- `tests/test_filesystem_matching.py`
- `tests/test_memory.py`
- `tests/test_persona_tts.py`
- `tests/test_security_authorization.py`
- `tests/test_open_file_routing.py`
- `tests/test_user_context.py`

Run the full suite from the repository root:

~~~bash
python -m pytest -v
~~~

Historical checkpoints: Phase 8.1 hardening reported `53 passed, 6 dependency warnings`; the file-open routing fix brought the reported full suite to 56 passing tests; and the Phase 8.3 profile/context changes brought the reported full suite to 63 passing tests. Phase 8.4 adds seven new summarization tests and is awaiting local validation.

The project owner reports that the file-open regression tests and live explicit-path open passed, and that the complete suite passed after Phase 8.3 changes (63 tests). Phase 8.4 adds seven conversation-summarization tests; run the focused tests and full suite locally before treating Phase 8.4 as validated.

~~~bash
python -m pytest -v tests/test_conversation_summarization.py
python -m pytest -v
~~~

The prior automated suite covers contextual interpretation, memory persistence/retrieval/update/expiry, dialogue selection, filesystem matching, persona/TTS behavior, and authorization. Live voice and desktop end-to-end validation remains separate; the project owner reports Phase 7.3 was completed locally.

---

# 🧪 Development Workflow

The architecture is designed so individual layers can be tested independently.

~~~text
Unit / Regression Tests
        ↓
Component Tests
        ↓
Voice / STT Audition
        ↓
Live JARVIS Test
        ↓
End-to-End Automation Validation
~~~

This avoids using the entire application as the only test harness.

---

# 🗺️ Current Development Roadmap

The roadmap is maintained in `JARVIS_ROADMAP.md`.

Current branch assessment:

~~~text
Phase 6
  ✅ Conversational System
        ↓
Phase 7
  ✅ Desktop Automation / Agent
      ├─ 7.1 ✅ Secure automation foundation
      ├─ 7.2 ✅ Desktop application control
      └─ 7.3 ✅ Live E2E validation reported complete by owner
        ↓
Phase 8
  🟡 Contextual foundation exists; overall phase incomplete
      ├─ 8.1 ✅ Context interpreter + file-open path verified by owner; legacy routes still need integration
      ├─ 8.2 ✅ Persistent memory implemented; included in passing 56-test suite
      ├─ 8.3 ✅ Structured profile context implemented and validated by owner
      ├─ 8.4 🟡 Rolling conversation summarization implemented; local validation pending
      ├─ 8.5 ⏳ Contextual follow-ups across actions
      ├─ 8.6 ⏳ Smarter structured intent detection
      ├─ 8.7 ⏳ Error recovery
      ├─ 8.8 ⏳ Runtime provider/model fallback
      └─ 8.9 ⏳ Full integration and E2E validation
        ↓
Phase 9
  ⏳ Advanced Voice + Vision
        ↓
Phase 10
  ⏳ AI Provider / Model Configuration
        ↓
Phase 11
  ⏳ UI + Experience Polish
        ↓
Phase 12
  ⏳ Production / Release
~~~

The Phase 8 objective is:

> Give JARVIS the ability to infer what the user means from imperfect speech, conversation history, memory, and current interaction state.

The codebase contains a contextual interpreter, recent-turn conversation context, temporary interaction state, SQLite-backed long-term memory, and a structured profile/preferences context layer. The project owner reports the file-open fix and 56-test suite passed locally before the new Phase 8.3 profile changes; the added profile tests still require local validation.

### Remaining Phase 8 work

- Some legacy application, YouTube, and messaging routes are not yet unified under the same structured action-history path.
- User profile/preferences/project context is now passed selectively into interpretation and response prompts; its seven new tests await local validation.
- Conversation summarization, broader contextual reference resolution, structured intent detection, intelligent failure recovery, runtime provider/model fallback, and final integration validation remain open.

Phase 7.3 live validation and the 56-test pre-Phase-8.3 suite are recorded as owner-reported results. The Phase 8.3 focused tests, full suite, and live preference-retrieval check are reported passing by the project owner. The Phase 8.4 summary tests are not yet locally validated.

---

# 💼 Portfolio / Project Showcase Reference

The following describes the project accurately without reducing it to a simple chatbot:

### Project type

**AI-powered desktop voice assistant / intelligent automation agent**

### Core technologies

**Python, Eel, PyTorch, FaceNet, MTCNN, Faster-Whisper, Kokoro TTS, OmniRoute, MongoDB, SQLite, OpenCV, PyAutoGUI, ADB, Porcupine, HTML/CSS/JavaScript**

### Strong technical points

- Designed a modular desktop AI assistant architecture in Python.
- Integrated computer vision-based face authentication using FaceNet embeddings.
- Implemented local speech recognition using Faster-Whisper with fallback handling.
- Integrated local neural TTS using Kokoro-82M with configurable voices and SAPI5 fallback.
- Built an OpenAI-compatible OmniRoute LLM client for provider/model abstraction.
- Implemented conversation IDs, recent context management and optional MongoDB persistence.
- Built a contextual interpretation layer that corrects obvious STT errors and resolves conversational references.
- Developed structured desktop automation for applications and filesystem operations.
- Implemented ranked file matching and natural-language multi-result selection.
- Added deterministic authorization gates for high-risk actions.
- Integrated Android automation through ADB.
- Built a cinematic Eel-based HUD for voice interaction and conversational feedback.
- Added regression tests for contextual interpretation, persistent memory lifecycle/retrieval, secure authorization, filesystem routing, persona/TTS behavior, and structured profile context.

### Portfolio-friendly one-line description

> **J.A.R.V.I.S is a modular Python-based desktop AI assistant that combines multimodal authentication, local speech/TTS, OmniRoute-powered conversational intelligence, contextual interpretation, secure desktop automation, Android/ADB control, and a cinematic Eel HUD.**

### What makes the project technically interesting

The main engineering focus is not simply calling an LLM. J.A.R.V.I.S separates:

~~~text
Perception
→ Interpretation
→ Conversation / Intent
→ Deterministic Automation
→ Security
→ Execution
→ Voice / UI Feedback
~~~

This allows the system to use LLMs for **language understanding without allowing the model to directly bypass deterministic security and execution boundaries**.

---

# ⚠️ Current Limitations

- Windows-focused implementation.
- Some automation depends on installed applications and local paths.
- Android functionality requires ADB and a configured device.
- Google STT fallback requires internet access.
- OmniRoute must be available for conversational LLM functionality.
- Current LLM requests are non-streaming.
- Phase 8.2 memory is implemented using local SQLite with lexical relevance retrieval; embedding-based retrieval and a memory-management UI remain future work.
- Phase 8.3 introduces category-tagged user profile/preferences/project context stored in the existing SQLite memory layer. Only query-relevant profile records are injected; temporary clarification/selection state remains in `engine/interaction_state.py` and is not persisted as a profile fact.
- Raw transcript and interpreted query are saved as separate fields on MongoDB conversational records when persistence is available; structured automation action history is not yet unified across every legacy route.
- Phase 7.3 live validation was reported as complete by the project owner; the roadmap records that report, but this audit session did not independently rerun local live checks.
- Kokoro's first initialization can take longer because the local pipeline/model is loaded and cached.
- Full provider/model configuration remains planned for a later phase.

---

# 🔒 Security & Privacy

Keep these out of version control:

- `.env`
- API keys
- Face samples
- Face embeddings
- Runtime databases
- Private conversation data
- Test audio
- Virtual environments
- Logs/caches

J.A.R.V.I.S is currently designed as a **personal/local Windows desktop application**, not a multi-user server.

---

# 📌 Development Philosophy

The project follows several architectural principles:

1. **LLMs interpret; deterministic code executes.**
2. **Security-sensitive actions fail closed.**
3. **Speech recognition is treated as an imperfect input signal.**
4. **Conversation context is separate from long-term memory.**
5. **UI, voice, automation and intelligence are modular components.**
6. **Features are considered complete only after regression/live validation.**
7. **Local-first components are preferred where practical.**

---

# 📄 License

See the repository for the current license information.

---

**J.A.R.V.I.S — perception, reasoning, conversation and action in one personal desktop system.**
