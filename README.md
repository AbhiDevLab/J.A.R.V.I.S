# JARVIS (Python + Eel)

This is a local voice assistant with a web UI powered by Python + Eel. It listens to your voice or typed input, executes commands (open apps, YouTube, WhatsApp actions), and can answer general questions using a local LLM (via Ollama, default model: `mistral`).

## Does it run like real-time ChatGPT?
- Short answer: It’s near real-time for voice use, but not exactly the same as ChatGPT’s streaming UI.
- Details:
  - Voice flow: speech -> recognition -> send to LLM -> text-to-speech. The model response is currently requested non-streaming (final text is spoken once received). Latency depends on your microphone, speech recognition, and your local model’s speed.
  - If you want token-by-token streaming like ChatGPT, you’d need to adapt `engine/ollama_client.py` and the UI to handle streaming and progressive TTS. The current setup favors a single final response for a smooth TTS experience.
This is a local voice assistant with a web UI powered by Python + Eel. It listens to your voice or typed input, executes commands (open apps, YouTube, WhatsApp actions), and can answer general questions using a local or cloud LLM. The code is configured to use Google Generative AI (Gemini) by default in `engine/gemini_client.py` but can be adapted to other local model hosts.

## Requirements
- Optional: Brave browser. If Brave isn’t installed, your default browser will open automatically.

## Quick Start (Windows, PowerShell)
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

## Troubleshooting

## FAQ
  - No. This isn’t a Node app. There’s no `package.json`. Use Python commands as shown above.

  - Functionally similar as a conversational assistant, but the UI doesn’t display token-by-token streaming. It returns a full response and speaks it. You can extend it for streaming if desired.
