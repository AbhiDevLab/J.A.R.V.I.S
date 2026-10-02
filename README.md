# J.A.R.V.I.S — Just A Rather Very Intelligent System

> **Windows desktop AI assistant • Python • Eel • Computer vision • Voice • Automation • Conversational AI**

J.A.R.V.I.S is a Windows-focused personal desktop AI assistant designed to combine **natural voice interaction, biometric authentication, desktop automation, conversational intelligence, and a cinematic HUD-style interface** in one local application.

This `master` branch documents the established/stable implementation. The more advanced experimental development work lives on the **`test-jarvis`** branch.

## Project at a Glance

| Area | Capability |
|---|---|
| Platform | Windows 10/11 |
| Language | Python |
| UI | Eel + HTML/CSS/JavaScript |
| Authentication | Local face authentication + voice fallback |
| Speech | SpeechRecognition / local speech pipeline |
| TTS | Local/Windows speech engines depending on configuration |
| AI | Conversational LLM integration |
| Automation | Windows apps, web services, Android/ADB |
| Storage | SQLite runtime data + optional MongoDB chat history |
| Architecture | Separate GUI/main and hotword processes |

## Core Features

### 🔐 Authentication

- Webcam-based face authentication.
- Configurable authentication threshold, frame count and timeout.
- Voice phrase fallback when face authentication fails or is unavailable.
- Local authentication data can remain on the machine.

### 🎙️ Voice Interaction

- Microphone-based voice commands.
- Hotword activation using Porcupine.
- Voice fallback authentication.
- Windows speech/TTS fallback support.
- Voice interaction is integrated with the main JARVIS HUD.

### 🤖 Conversational AI

J.A.R.V.I.S can handle general natural-language questions through its configured conversational AI provider.

Examples:

- "What is the capital of France?"
- "Explain binary search."
- "Summarize this concept."
- "Help me troubleshoot this error."

### 🖥️ Desktop Automation

The assistant can route natural-language commands to local actions such as:

- Launching Windows applications.
- Opening websites.
- YouTube playback.
- WhatsApp messaging/calls/video calls.
- Android actions through ADB.
- Other locally configured application commands.

### 🎨 Cinematic HUD

The Eel frontend provides an app-style desktop experience with:

- Animated startup/loading UI.
- Face-authentication interface.
- SiriWave-style voice visualization.
- JARVIS HUD/orbiting visual presentation.
- Voice/listening status feedback.
- Chat interface and conversation display.

## Architecture

~~~text
Hotword Process
      │
      ▼
  Activation
      │
      ▼
Main J.A.R.V.I.S Process
      │
      ├── Eel HUD / Web UI
      │
      ├── Authentication
      │      ├── Face Authentication
      │      └── Voice Fallback
      │
      ├── Speech Recognition
      │
      ├── Command Router
      │      ├── Windows Apps
      │      ├── Web / YouTube
      │      ├── WhatsApp
      │      └── Android / ADB
      │
      └── Conversational AI
             │
             └── Optional MongoDB History
~~~

## Installation

### Requirements

- Windows 10/11
- Python 3.8+; Python 3.11 is recommended
- Git
- Webcam
- Microphone
- Internet connection for cloud-backed speech/AI features
- ADB + Android device for optional Android automation

### Clone

~~~bash
git clone https://github.com/AbhiDevLab/J.A.R.V.I.S.git
cd J.A.R.V.I.S
~~~

### Virtual environment

~~~bash
python -m venv envjarvis
.\\envjarvis\\Scripts\\activate
~~~

### Dependencies

Install the packages from `requirements.txt`. Some Windows audio/ML packages may require additional local setup.

Optional MongoDB support:

~~~bash
pip install pymongo
~~~

## Environment Configuration

Copy `.env.example` to `.env` and configure the required values.

Typical authentication configuration:

~~~env
JARVIS_AUTH_ID=1
JARVIS_AUTH_FRAMES=3
JARVIS_AUTH_TIMEOUT=20
JARVIS_AUTH_THRESHOLD=0.9
JARVIS_AUTH_OVERLAY_SECONDS=4

JARVIS_VOICE_ENABLED=1
JARVIS_VOICE_PHRASE=genius billionaire playboy philanthropist
JARVIS_VOICE_TIMEOUT=20
~~~

Optional MongoDB:

~~~env
MONGODB_URI=mongodb://127.0.0.1:27017/jarvis
JARVIS_CHAT_COLLECTION=chats
~~~

> Never commit a real `.env`, API keys, biometric samples, embeddings, or other private runtime data.

## Face Enrollment

Capture face samples:

~~~bash
python engine/auth/capture_samples.py --label YourName --id 1 --count 50
~~~

Generate the local face gallery/embeddings:

~~~bash
python engine/auth/trainer.py
~~~

Keep biometric samples and generated embeddings local.

## Running

Full application:

~~~bash
python run.py
~~~

Main GUI process:

~~~bash
python main.py
~~~

## Example Commands

~~~text
open notepad
open vscode
play Bohemian Rhapsody on youtube
send message to Mom Hello
phone call Dad
what is the capital of France?
~~~

## Android / ADB

Android automation is optional.

A connected Android device can be used for actions such as:

- Phone calls
- SMS
- Device preparation through ADB

Wireless ADB can also be used when the Android device is configured for it.

## Development Branch

The **`test-jarvis`** branch is the active development branch for the next-generation J.A.R.V.I.S architecture.

It extends the established system with:

- Structured desktop automation.
- Filesystem search and operations.
- Deterministic security/authorization gates.
- Faster-Whisper local STT.
- Kokoro local neural TTS.
- OmniRoute-based provider-neutral LLM access.
- Conversation context management.
- Contextual interpretation of imperfect speech.
- JARVIS-specific response/personality prompting.
- Improved English/Hindi language handling.
- Regression testing for automation, security, context and TTS.

See the `test-jarvis` README and `JARVIS_ROADMAP.md` for the current development state.

## Portfolio-Relevant Technical Highlights

J.A.R.V.I.S demonstrates practical integration of:

- **Python application architecture**
- **Computer vision and face embeddings**
- **Speech recognition**
- **Neural text-to-speech**
- **LLM integration through an OpenAI-compatible API**
- **Natural-language command routing**
- **Desktop automation**
- **ADB/mobile automation**
- **Eel-based frontend/backend communication**
- **MongoDB conversation persistence**
- **Security-aware action execution**
- **Automated regression testing**
- **Multi-process application design**

## Limitations

- Primarily designed for Windows.
- Some actions depend on installed applications and local paths.
- Android automation requires ADB and a configured device.
- Internet may be required for selected speech/AI integrations.
- The application is intended for personal/local desktop use rather than multi-user server deployment.

## License

See the repository for the current license information.

---

**J.A.R.V.I.S — a personal desktop AI assistant built to understand, speak, and interact with the user's computer.**
