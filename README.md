# J.A.R.V.I.S (Just A Rather Very Intelligent System)

![J.A.R.V.I.S Logo](<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/0874993d-61b5-4c36-bacb-eeb86f1170af" />)

A Windows-centric Python desktop voice assistant with face authentication, voice fallback, local automation, and Gemini-powered conversational AI. Built with Python + Eel for a native-like web UI.

## ✨ Features

- **Face Authentication** using Faster R-CNN detection and FaceNet embeddings
- **Voice Fallback** (Google Speech Recognition) when face auth fails or is disabled
- **Hotword Detection** (Porcupine) for "Jarvis" / "Alexa" to activate via Win+J
- **Command Execution**:
  - Open local applications & websites (configured via SQLite)
  - YouTube playback (`play <search>`)
  - WhatsApp messaging/calls/video (via URL scheme + pyautogui)
  - Android automation via ADB (call/SMS)
- **Conversational AI**: General queries handled by Google Gemini (`gemini-2.5-flash-lite`)
- **Optional Chat History**: MongoDB persistence for user/assistant turns
- **Rich UI**: Animated loader, SiriWave visualization, orbiting hood, off‑canvas chat
- **Cross‑process Architecture**: Separate processes for GUI and hotword listener

## 🏗️ Architecture

```mermaid
flowchart TD
    A[Hotword Process] -->|Detects "jarvis"/"alexa"| B(Win+J Shortcut)
    B --> C[Main Process]
    C --> D{Eel + Frontend}
    D -->|loads| E[www/index.html]
    D -->|exposes| F[Python Bindings]
    F --> G[Face Authentication]
    F --> H[Voice Fallback]
    F --> I[Command Router]
    I --> J[Open Apps/Websites]
    I --> K[YouTube]
    I --> L[WhatsApp/Android]
    I --> M[Gemini LLM]
    M -->|Optional| N[(MongoDB Chat Log)]
    G -->|Success| O[Assistant Ready]
    H -->|Success| O
    style A fill:#f9f,stroke:#333,stroke-width:2px
    style C fill:#bbf,stroke:#333,stroke-width:2px
```

## 📦 Installation

### Prerequisites
- Windows 10/11
- Python 3.8+ (tested with 3.11)
- Git
- [Brave Browser](https://brave.com/) (optional; falls back to default browser)
- Android Debug Bridge (ADB) for mobile features (optional)
- Webcam & microphone

### 1. Clone the repository
```bash
git clone https://github.com/your-username/J.A.R.V.I.S.git
cd J.A.R.V.I.S
```

### 2. Set up a virtual environment (recommended)
```bash
python -m venv envjarvis
.\envjarvis\Scripts\activate
```

### 3. Install dependencies
> **Note**: The current `requirements.txt` is **incomplete**. Install the following packages manually:

```bash
pip install eel pyttsx3 SpeechRecognition pyaudio playsound pyautogui pywhatkit pvporcupine requests
pip install torch torchvision facenet-pytorch opencv-python pillow numpy
# Optional: for MongoDB chat history
pip install pymongo
# Optional: for voice dependency helper (Windows)
pip install pipwin
```

### 4. Configure environment
Copy `.env.example` to `.env` and fill in your values:

```env
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Face Auth (tune as needed)
JARVIS_AUTH_ID=1
JARVIS_AUTH_FRAMES=3
JARVIS_AUTH_TIMEOUT=20
JARVIS_AUTH_THRESHOLD=0.9
JARVIS_AUTH_OVERLAY_SECONDS=4

# Voice Fallback
JARVIS_VOICE_ENABLED=1
JARVIS_VOICE_PHRASE=genius billionaire playboy philanthropist
JARVIS_VOICE_TIMEOUT=20

# Optional MongoDB
# MONGODB_URI=mongodb://localhost:27017/jarvis
# JARVIS_DB_NAME=jarvis
# JARVIS_CHAT_COLLECTION=chats
```

> **Never commit your real `.env`**. Keep it private.

### 5. Enroll your face (one‑time)
Run the sample capture script to collect training images:

```bash
python engine/auth/capture_samples.py --label YourName --id 1 --count 50
```

Then generate the embeddings:

```bash
python engine/auth/trainer.py
```

This creates `engine/auth/trainer/embeddings.pkl`.

### 6. Launch J.A.R.V.I.S
```bash
# Start both GUI and hotword listener
python run.py
```
or
```bash
# Start GUI only (hotword must be triggered manually via Win+J)
python main.py
```

The assistant will open in a Brave app window (or default browser) at `http://localhost:8000/index.html`.

## 🚀 Usage

1. **Hotword**: Say “Jarvis” or “Alexa” to activate via Win+J shortcut.
2. **UI Interaction**:
   - Click the mic button or press `Ctrl+J` to voice‑command.
   - Type in the chat box and press Enter or Send.
3. **Authentication**:
   - Face authentication runs automatically on start.
   - If it fails (or is disabled), voice fallback listens for the phrase set in `JARVIS_VOICE_PHRASE`.
   - Use the “Try Again” button in the UI to retry voice fallback.
4. **Example Commands**:
   - `open notepad`
   - `play Bohemian Rhapsody on youtube`
   - `send message to Mom Hello`
   - `phone call Dad`
   - `what is the capital of France?` → Gemini responds

## ⚙️ Configuration

Adjust behavior via environment variables in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | *(required)* |
| `JARVIS_AUTH_ID` | Numeric ID of the authorized person | `1` |
| `JARVIS_AUTH_FRAMES` | Consecutive positive frames needed for auth | `3` |
| `JARVIS_AUTH_TIMEOUT` | Seconds to attempt face auth before fallback | `20` |
| `JARVIS_AUTH_THRESHOLD` | Cosine similarity threshold (0‑1) | `0.9` |
| `JARVIS_AUTH_OVERLAY_SECONDS` | Overlay display time after success/failure | `4` |
| `JARVIS_VOICE_ENABLED` | Enable voice fallback (`1`/`0`) | `1` |
| `JARVIS_VOICE_PHRASE` | Phrase for voice fallback (lower‑case, no punctuation) | `genius billionaire playboy philanthropist` |
| `JARVIS_VOICE_TIMEOUT` | Seconds to listen for voice phrase | `20` |
| `MONGODB_URI` | MongoDB connection string | *(optional)* |
| `JARVIS_DB_NAME` | Database name for chat history | `jarvis` |
| `JARVIS_CHAT_COLLECTION` | Collection name for chat history | `chats` |

## 🖼️ Screenshots

> **No authentic screenshots are currently committed to the repository.**  
> To enrich this README, capture the following:
> 1. Animated loader / face‑auth Lottie screen
> 2. Main interface: orbiting hood, text input, mic/send/chat buttons
> 3. SiriWave voice‑listening visualization
> 4. Off‑canvas chat with a real user/assistant exchange
> 5. (Optional) OpenCV face‑authentication overlay window

Place any captured screenshots under `docs/` or `assets/screenshots/` and reference them here.

## 🔒 Limitations & Notes

- **Windows‑only**: Relies on `os.startfile`, `pyautogui` Win+J, Brave, SAPI5, and ADB paths.
- **Internet Required**: Voice fallback uses Google Speech Recognition; Gemini queries need internet.
- **Face Auth Privacy**: Biometric samples (`engine/auth/samples/`) and embeddings (`engine/auth/trainer/embeddings.pkl`) are **local only** and must remain private.
- **.gitignore**: Ensure the following are **not** committed:
  - `.env` (real API key)
  - `engine/auth/samples/`
  - `engine/auth/trainer/`
  - `jarvis.db` (SQLite runtime)
  - `*.wav`, `*.mp3` (test audio)
  - Virtual environments, IDE folders, logs, caches
- **Dependencies**: The bundled `requirements.txt` omits several core packages (see Installation). Install the full list above.
- **device.bat**: A helper script that prepares ADB over TCP; if missing or failing, the app will still launch but Android features won’t work. Verify ADB is installed and a device is connected.

## 🐞 Troubleshooting

| Symptom | Fix |
|---------|-----|
| `FileNotFoundError: device.bat` | Ensure `device.bat` exists at project root. It may require adjusting the working directory when launched from a shortcut. |
| Voice auth repeatedly “Access Denied” | Confirm `JARVIS_VOICE_PHRASE` matches exactly what you speak (lowercase, no punctuation). Use the console output to compare. |
| Missing module `cv2` or `PIL` | Install `opencv-python` and `pillow`. |
| `pipwin not found` on Windows | Install via `pip install pipwin` then retry PyAudio install. |
| Gemini returns “not available” | Install `google-generativeai` and verify `GEMINI_API_KEY` is set. |
| Hotkey (Win+J) does nothing | Ensure the hotword process is running (`python run.py`) and Porcupine initialized correctly. |
| WhatsApp/Website fails to open | Verify default browser or Brave is installed and accessible. |

## 📚 Related Projects

- [Eel](https://github.com/ChrisKnott/Eel) – Python‑HTML/JS bridge
- [Porcupine](https://picovoice.ai/) – Wake word engine
- [FaceNet](https://github.com/timesler/facenet-pytorch) – Face embeddings
- [Google Gemini](https://ai.google.dev/gemini-api) – Generative AI model

## 📄 License

This project is provided as‑is. See the repository for any license information.

---

*Made with ❤️ for the desktop assistant enthusiasts.*
