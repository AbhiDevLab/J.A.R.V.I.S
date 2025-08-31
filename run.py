import multiprocessing
import subprocess
import time
import os
import sys
from pathlib import Path

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

# make sure GEMINI_API_KEY exists so child won't crash with ValueError
if not os.getenv('GEMINI_API_KEY'):
    print("ERROR: GEMINI_API_KEY not found. Set it in the OS environment or create a .env file with GEMINI_API_KEY=<your_key>")
    sys.exit(1)

# To run Jarvis
def startJarvis():
    # Code for process 1
    print("Process 1 is running...")
    from main import start
    start()

# To run hotword
def listenHotword():
    # Code for process 2
    print("Process 2 is running...")
    from engine.features import hotword
    hotword() 

# Start all processes
if __name__ == "__main__":
    # Start the existing processes
    p1 = multiprocessing.Process(target=startJarvis)
    p2 = multiprocessing.Process(target=listenHotword)
    p1.start()
    p2.start()
    
    # Wait for the main Jarvis process to complete
    p1.join()
    
    # Terminate other processes when Jarvis stops
    if p2.is_alive():
        p2.terminate()
        p2.join()
    print("System Stop")