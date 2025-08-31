# JARVIS (Python + Eel)

This is a local voice assistant with a web UI powered by Python + Eel. It listens to your voice or typed input, executes commands (open apps, YouTube, WhatsApp actions), and can answer general questions using a local LLM (via Ollama, default model: `mistral`).

## Does it run like real-time ChatGPT?
- Short answer: It’s near real-time for voice use, but not exactly the same as ChatGPT’s streaming UI.
- Details:
  - Voice flow: speech -> recognition -> send to LLM -> text-to-speech. The model response is currently requested non-streaming (final text is spoken once received). Latency depends on your microphone, speech recognition, and your local model’s speed.
  - If you want token-by-token streaming like ChatGPT, you’d need to adapt `engine/ollama_client.py` and the UI to handle streaming and progressive TTS. The current setup favors a single final response for a smooth TTS experience.

## Requirements
- Windows (project is configured for Windows shortcuts, SAPI5 TTS, etc.)
- Python 3.10+ recommended
- Optional: Brave browser. If Brave isn’t installed, your default browser will open automatically.
- Optional: Ollama running locally for the LLM (default model `mistral`): https://ollama.com

## Quick Start (Windows, PowerShell)

1. Create and activate a virtual environment (recommended):
   - Python venv (PowerShell):
     - `python -m venv envjarvis`
     - `./envjarvis/Scripts/Activate.ps1`

2. Install dependencies:
   - Core libs used by this project include: `eel`, `pyttsx3`, `SpeechRecognition`, `pyaudio`, `playsound`, `pyautogui`, `pywhatkit`, `pvporcupine`, `requests`, and optionally `pymongo`.
   - Install them:
     - `pip install eel pyttsx3 SpeechRecognition pyaudio playsound pyautogui pywhatkit pvporcupine requests pymongo`
   - Note: `pyaudio` can be tricky on Windows. If you hit issues, search for prebuilt wheels for your Python version.

3. (Optional) Start Ollama for local LLM answers:
   - Install Ollama: https://ollama.com
   - In PowerShell, you can point to your models directory if needed and start the server:
     - `# Optional: set model dir`
     - `$env:OLLAMA_MODELS = 'F:\\.ollama'`
     - `ollama serve`
   - Pull a model (default used here is `mistral`):
     - `ollama pull mistral`
   - The code expects Ollama at `http://localhost:11434` by default. You can override via env var `OLLAMA_HOST`.

4. Run JARVIS:
   - To run the UI + assistant only:
     - `python main.py`
   - To run both the assistant and the hotword listener in parallel:
     - `python run.py`

5. Use the app:
   - The web UI will open at `http://localhost:8000/index.html` (Brave app window if detected, otherwise your default browser).
   - Click the mic button or type a message, then press Send. You can also toggle the chat off-canvas to see message history in the session UI.

## Notes & Tips
- Hotword: The `run.py` process starts a Porcupine listener for keywords ("jarvis", "alexa"). It simulates the Win+J shortcut via `pyautogui` when activated.
- WhatsApp actions: The code opens `whatsapp://` links via Windows `start`, then navigates using `pyautogui`. Ensure WhatsApp Desktop is installed and logged in.
- MongoDB (optional): If you want chat history in MongoDB, set `MONGODB_URI` (or `MONGO_URI`) in your environment or LibreChat/.env. Install `pymongo`. Otherwise, the mongo calls are no-ops.
- Changing the model: Set env var `JARVIS_MODEL` to a different Ollama model name. For example: `$env:JARVIS_MODEL = 'llama3:8b'`.
- Changing assistant name: See `engine/config.py`.

## Troubleshooting
- Audio input issues: Check your microphone permissions and default device. `SpeechRecognition` uses the default input.
- `pyaudio` install errors: Try a prebuilt wheel matching your Python version/arch.
- Browser doesn’t open: The app will try Brave first; if not found, it opens your default browser. You can always navigate to `http://localhost:8000/index.html` manually once `main.py` is running.
- Ollama not responding: Ensure `ollama serve` is running and you have pulled the model (`ollama pull mistral`). You can change the host with `OLLAMA_HOST` env var.

## FAQ
- Can I use npm run dev/frontend/backend?
  - No. This isn’t a Node app. There’s no `package.json`. Use Python commands as shown above.

- Is it like ChatGPT in real-time?
  - Functionally similar as a conversational assistant, but the UI doesn’t display token-by-token streaming. It returns a full response and speaks it. You can extend it for streaming if desired.
