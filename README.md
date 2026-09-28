# J.A.R.V.I.S (Just A Rather Very Intelligent System)

A Windows-centric Python desktop voice assistant built with **Python + Eel**, combining face authentication, voice fallback, local desktop automation, conversational AI, speech recognition, neural TTS, hotword activation, and a cinematic HUD interface.

## ✨ Current Features

### 🔐 Authentication & Security

- **Face authentication** using Faster R-CNN face detection, FaceNet embeddings (InceptionResnetV1), and MTCNN-assisted face processing.
- Configurable similarity threshold and consecutive-frame verification.
- **Voice authentication fallback** when face authentication fails.
- High-risk local actions require **two authentication steps only**:
  1. Explicit spoken confirmation
  2. Successful face authentication
- High-risk actions fail closed when authorization fails.
- Authentication samples and generated face embeddings are kept local and ignored by Git.

### 🎙️ Speech & Voice

- Local speech transcription with **Faster-Whisper** when available.
- Google Speech Recognition fallback.
- Automatic English/Hindi detection for supported speech.
- Neural TTS using **Edge TTS** with SAPI5 fallback.
- Configurable English/Hindi voices, rate, volume, and pitch.
- Interruptible TTS infrastructure so the hotword system can detect an interruption while JARVIS is speaking.
- Hotword activation through **Porcupine**.
- Shared microphone/process coordination between hotword detection and speech recognition.

### 🤖 Conversational AI

- Provider-neutral LLM client using **OmniRoute**.
- OpenAI-compatible /chat/completions interface.
- Configurable OmniRoute model/team.
- Conversation context manager with configurable recent-turn memory.
- Optional MongoDB persistence for conversation history.
- Conversation history can be loaded into the UI.
- New-conversation support.
- Non-streaming LLM responses are currently used by JARVIS.

### 🖥️ Desktop Automation

JARVIS has a structured automation layer under engine/automation/.

- Command routing into structured AutomationAction objects.
- Application resolution with aliases for common Windows applications.
- File/folder search with ranked matching:
  - exact filename
  - exact filename stem
  - substring stem
- Case-insensitive file matching.
- Multiple-match selection using spoken numbering/ordinal forms.
- File operations:
  - open
  - create
  - rename
  - move
  - copy
  - delete
- Folder operations:
  - open
  - create
  - rename
  - move
  - delete
  - list
- High-risk actions such as deletion are passed through the authorization gate before execution.
- Authorized shell-command execution is available through the structured automation layer.

### 📱 External & Application Automation

- Windows application launching.
- Browser/application aliases for common applications including Chrome, Edge, VS Code, Spotify, Explorer, Terminal, Notepad, Calculator, Paint, Task Manager, and Command Prompt.
- YouTube playback through pywhatkit.
- WhatsApp messaging/calling/video-call automation.
- Android automation through ADB for calls and SMS.
- Optional device.bat startup integration for Android device preparation.

### 🎨 JARVIS HUD

- Eel-based native-like web interface.
- Animated loader and authentication UI.
- Live webcam feed during face authentication.
- SiriWave voice visualization.
- Cinematic HUD/orbiting interface.
- Smooth status-text transitions for Listening, Recognizing, Thinking, and other transient states.
- User speech is surfaced directly through the main HUD text rather than a separate transcript card.
- Markdown-aware assistant response cards.
- Response copy controls.
- Conversation/history viewer.
- Settings panel for voice responses and response language.
- Responsive multiline rendering for filesystem results and long text.

## 🏗️ Architecture

~~~mermaid
flowchart TD
    A[Porcupine Hotword Process] -->|Jarvis detected| B[Win+J activation]
    B --> C[JARVIS Main Process]

    C --> D[Eel Web UI]
    D --> E[HUD / SiriWave / Chat]

    C --> F[Authentication]
    F --> F1[Face Authentication]
    F --> F2[Voice Fallback]

    C --> G[Speech Recognition]
    G --> G1[Faster-Whisper]
    G --> G2[Google STT fallback]

    C --> H[Command Router]
    H --> I[AutomationAction]

    I --> J[Security Gate]
    J --> K[Executor]

    K --> K1[Files / Folders]
    K --> K2[Windows Applications]
    K --> K3[ADB / Android]
    K --> K4[WhatsApp / YouTube]

    C --> L[OmniRoute LLM]
    L --> M[Conversation Manager]
    M --> N[(Optional MongoDB)]
~~~

### Main project structure

~~~text
J.A.R.V.I.S/
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
│   ├── conversation.py
│   ├── features.py
│   ├── llm_client.py
│   ├── settings_store.py
│   ├── stt.py
│   └── tts.py
│
├── www/
│   ├── index.html
│   ├── controller.js
│   └── style.css
│
├── main.py
├── run.py
├── device.bat
└── requirements.txt
~~~

## 📦 Requirements

### Platform

- Windows 10/11
- Python 3.11 recommended
- Git
- Webcam
- Microphone
- Internet connection for Google STT fallback, Edge TTS, and OmniRoute-backed LLM requests
- Brave Browser is recommended for the app-style frontend, although the browser launch can be adjusted.

### Optional hardware/software

- Android phone + ADB for Android automation
- MongoDB for persistent conversation history
- CUDA-capable GPU can be useful for face/STT workloads

## 🚀 Installation

### 1. Clone the repository

~~~bash
git clone https://github.com/AbhiDevLab/J.A.R.V.I.S.git
cd J.A.R.V.I.S
~~~

### 2. Create the virtual environment

~~~bash
python -m venv envjarvis
.\envjarvis\Scripts\activate
~~~

### 3. Install dependencies

Install the packages listed in requirements.txt.

Some Windows/audio/ML packages may require additional setup depending on the local Python installation.

For the current feature set, the environment includes packages for:

- Eel
- SpeechRecognition / PyAudio
- Faster-Whisper
- Edge TTS
- pyttsx3
- pygame
- OpenCV
- PyTorch / TorchVision
- FaceNet / facenet-pytorch
- NumPy / Pillow
- pyautogui
- pywhatkit
- Porcupine
- requests
- optional pymongo

## ⚙️ Environment Configuration

Create a local .env file from .env.example.

### OmniRoute

~~~env
LLM_PROVIDER=omniroute
OMNIROUTE_API_KEY=your_key
OMNIROUTE_BASE_URL=http://localhost:20128/v1
OMNIROUTE_MODEL=Teamax
OMNIROUTE_TIMEOUT=180
~~~

run.py checks whether OmniRoute is already responding. If it is not running, JARVIS attempts to start the local omniroute process automatically and waits for it to become available.

### Face authentication

~~~env
JARVIS_AUTH_ID=1
JARVIS_AUTH_FRAMES=3
JARVIS_AUTH_TIMEOUT=20
JARVIS_AUTH_THRESHOLD=0.9
JARVIS_AUTH_OVERLAY_SECONDS=4
JARVIS_AUTH_WEBCAM_FPS=15
~~~

### Voice authentication

~~~env
JARVIS_VOICE_ENABLED=1
JARVIS_VOICE_PHRASE=genius billionaire playboy philanthropist
JARVIS_VOICE_TIMEOUT=20
~~~

### Speech recognition

The STT layer can use local Faster-Whisper first and Google Speech Recognition as a fallback when enabled by configuration.

### TTS

Relevant settings include:

~~~env
JARVIS_TTS_ENABLED=1
JARVIS_TTS_LANGUAGE=auto
JARVIS_TTS_EN_VOICE=en-US-GuyNeural
JARVIS_TTS_HI_VOICE=hi-IN-MadhurNeural
JARVIS_TTS_RATE=-5%
JARVIS_TTS_VOLUME=+0%
JARVIS_TTS_PITCH=-2Hz
~~~

### Conversation persistence

MongoDB is optional:

~~~env
MONGODB_URI=your_mongodb_connection_string
JARVIS_DB_NAME=jarvis
JARVIS_CHAT_COLLECTION=chats
JARVIS_CONTEXT_TURNS=8
~~~

If MongoDB is unavailable, the active session can continue using in-memory conversation context.

> **Never commit your real .env file or API keys.**

## 👤 Face Enrollment

Face authentication uses locally generated embeddings.

Capture samples:

~~~bash
python engine/auth/capture_samples.py --label YourName --id 1 --count 50
~~~

Generate the gallery:

~~~bash
python engine/auth/trainer.py
~~~

The generated authentication data remains local and is ignored by Git.

## ▶️ Running J.A.R.V.I.S

### Full mode

Starts the main JARVIS process and the separate hotword process:

~~~bash
python run.py
~~~

### GUI/main process only

~~~bash
python main.py
~~~

The application serves the Eel frontend locally and opens it in an app-style browser window.

## 🎤 Typical Interaction

### Startup

~~~text
Launch
  ↓
Face authentication
  ↓
Voice fallback if face authentication fails
  ↓
System unlocked
~~~

### Voice command

~~~text
Listening...
  ↓
Recognizing...
  ↓
Recognized user speech
  ↓
Command routing / LLM
  ↓
Thinking...
  ↓
Response
~~~

### High-risk automation

~~~text
User requests protected action
  ↓
Voice confirmation
  ↓
Face authentication
  ↓
Action execution
~~~

There is intentionally **no third confirmation step**.

## 🧪 Tests

The repository contains a local test suite covering the current filesystem matching and authorization behavior.

Run:

~~~bash
python -m unittest discover -s tests -v
~~~

The current local test set covers:

- exact filename matching
- exact stem matching
- substring matching
- case-insensitive matching
- maximum result limits
- suppression of weaker matches when stronger matches exist
- failed face authorization
- failed voice confirmation
- successful voice-confirmation + face-auth authorization

## 🔒 Security & Privacy

J.A.R.V.I.S can interact with the local Windows environment, so security boundaries are important.

The following are intentionally treated as high-risk operations:

- deleting files/folders
- deleting multiple matches
- shell/PowerShell execution
- process termination
- system power operations
- system-setting modifications
- software installation/uninstallation

Authentication data, runtime databases, environment variables, audio files, virtual environments, and other local/private artifacts should remain outside version control.

The project is currently designed for **personal/local Windows use**, not as a multi-user server application.

## ⚠️ Current Limitations

- Windows-focused implementation.
- Some automation integrations depend on the local Windows installation and application paths.
- Android features require ADB and a connected/configured device.
- Google STT fallback requires internet access.
- Edge TTS requires internet access.
- OmniRoute must be available for conversational LLM functionality.
- The current LLM request path is non-streaming.
- Speech recognition currently displays the recognized utterance after the transcription result is available; true token/word-level live STT is not yet implemented.
- Some legacy integrations remain in engine/features.py while the newer structured automation layer is being consolidated.

## 🛠️ Development Status

The core J.A.R.V.I.S system is functional, with the current development focus on:

- HUD/voice-recognition animation polish
- end-to-end automation reliability
- hotword/TTS interruption reliability
- consolidation of legacy and structured automation paths
- broader regression coverage
- dependency/documentation cleanup
- optional future live/interim speech recognition

## 📄 License

See the repository for the current license information.

---

*J.A.R.V.I.S — a personal desktop voice assistant built for Windows.*
