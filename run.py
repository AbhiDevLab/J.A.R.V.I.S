import multiprocessing
import subprocess
import time
import requests
import os
import sys
from pathlib import Path
import cv2
from PIL import Image

# face recognizer (imported lazily in authenticate to avoid heavy imports on every run)

# Ensure the running interpreter's site-packages is on sys.path early so spawned children can import packages
try:
    import sysconfig, site as _site  # type: ignore
    site_packages = sysconfig.get_paths().get('purelib') or (_site.getsitepackages()[0] if _site.getsitepackages() else None)
    if site_packages and site_packages not in sys.path:
        sys.path.insert(0, site_packages)
except Exception:
    # best-effort only; continue even if we can't compute site-packages
    pass

def _load_env_file(path: Path):
    if not path.is_file():
        return
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip().strip('\'"')
            if key and val and key not in os.environ:
                os.environ[key] = val

def ensure_env_loaded():
    # try python-dotenv first
    try:
        from dotenv import load_dotenv  # type: ignore
        # load .env from project root (this file's parent)
        load_dotenv(dotenv_path=Path(__file__).parent / '.env')
        return
    except Exception:
        # fallback: parse .env manually
        _load_env_file(Path(__file__).parent / '.env')

# Ensure environment variables are loaded before creating child processes
ensure_env_loaded()

# Make sure OmniRoute is configured before starting child processes.
required_omniroute_vars = (
    "OMNIROUTE_API_KEY",
    "OMNIROUTE_BASE_URL",
    "OMNIROUTE_MODEL",
)

missing_omniroute_vars = [
    name
    for name in required_omniroute_vars
    if not os.getenv(name)
]

if missing_omniroute_vars:
    print(
        "ERROR: Missing OmniRoute environment variables: "
        + ", ".join(missing_omniroute_vars)
    )
    sys.exit(1)

def ensure_omniroute():
    """Ensure the local OmniRoute server is running."""
    base_url = os.getenv(
        "OMNIROUTE_BASE_URL",
        "http://localhost:20128/v1"
    ).rstrip("/")

    health_url = f"{base_url}/models"

    # Check whether OmniRoute is already running.
    try:
        requests.get(health_url, timeout=2)
        print("✓ OmniRoute is already running.")
        return
    except requests.RequestException:
        pass

    # OmniRoute is not running, so start it.
    print("🧠 OmniRoute is not running. Starting OmniRoute...")

    try:
        subprocess.Popen(
            ["omniroute"],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    except FileNotFoundError:
        print("❌ Could not find 'omniroute' in PATH.")
        print("   Make sure OmniRoute can be started by typing:")
        print("   omniroute")
        sys.exit(1)
    except Exception as exc:
        print(f"❌ Failed to start OmniRoute: {exc}")
        sys.exit(1)

    # Wait for the server to become available.
    print("⏳ Waiting for OmniRoute server...")

    for _ in range(30):
        try:
            requests.get(health_url, timeout=2)
            print("✓ OmniRoute server is ready.")
            return
        except requests.RequestException:
            time.sleep(1)

    print("❌ OmniRoute did not become ready within 30 seconds.")
    sys.exit(1)

# To run Jarvis
def startJarvis(
    interrupt_event,
    speaking_event,
    mic_busy_event,
):
    print("Process 1 is running...")

    from main import start

    start(
        interrupt_event=interrupt_event,
        speaking_event=speaking_event,
        mic_busy_event=mic_busy_event,
    )

# To run hotword
def listenHotword(
    interrupt_event,
    speaking_event,
    mic_busy_event,
):
    print("Process 2 is running...")

    from engine.features import hotword

    hotword(
        interrupt_event=interrupt_event,
        speaking_event=speaking_event,
        mic_busy_event=mic_busy_event,
    )

# Start all processes
if __name__ == "__main__":
    
    ensure_omniroute()
    # Shared process-safe audio control signals.
    #
    # interrupt_event:
    #   Hotword process sets this when "Jarvis" is detected
    #   while JARVIS is speaking.
    #
    # speaking_event:
    #   Main process sets this while TTS is speaking.
    #
    # mic_busy_event:
    #   Main process sets this while SpeechRecognition owns
    #   the microphone for a user query.
    interrupt_event = multiprocessing.Event()
    speaking_event = multiprocessing.Event()
    mic_busy_event = multiprocessing.Event()

    # Start GUI / main JARVIS process.
    p1 = multiprocessing.Process(
        target=startJarvis,
        args=(
            interrupt_event,
            speaking_event,
            mic_busy_event,
        ),
    )

    # Start hotword listener process.
    p2 = multiprocessing.Process(
        target=listenHotword,
        args=(
            interrupt_event,
            speaking_event,
            mic_busy_event,
        ),
    )

    p1.start()
    p2.start()

    # Wait for the main Jarvis process to complete.
    p1.join()

    # Terminate the hotword process when Jarvis stops.
    if p2.is_alive():
        p2.terminate()
        p2.join()

    print("System Stop")