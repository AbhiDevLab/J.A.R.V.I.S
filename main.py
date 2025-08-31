import os
import eel
import subprocess
from engine.gemini_client import init_gemini, is_available
from engine.auth import recognize
from engine.features import *
from engine.command import *


# try importing python-dotenv in a linter-friendly way
try:
    from dotenv import load_dotenv  # type: ignore
    _has_dotenv = True
except Exception:
    _has_dotenv = False

# call load_dotenv only if available
if _has_dotenv:
    load_dotenv()
else:
    # avoid noisy printing at import time during multiprocessing; just note the state
    _dotenv_missing = True

def start():
    # If dotenv was missing earlier, you can optionally print a hint now (only when start runs)
    if globals().get('_dotenv_missing', False):
        print("python-dotenv not found; environment variables will be read from the OS. Install with `pip install python-dotenv` if needed.")

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    
    # Always initialize the global gemini_client object so it's not None later.
    # GeminiClient will set itself as 'unavailable' when google-generativeai is not installed.
    init_gemini(api_key)
    
    eel.init("www")

    playAssistantSound()
    @eel.expose
    def init():    
        subprocess.call([r'device.bat'])
        eel.hideLoader()
        speak("Ready for Face Authentication")
        flag = recognize.AuthenticateFace()
        if flag == 1:
            eel.hideFaceAuth()
            speak("Face Authentication Successful. System is fully operational now.")
            eel.hideFaceAuthSuccess()
            speak("Welcome Back Sir, it's a pleasure to see you working!")
            eel.hideStart()
            playAssistantSound()
        else:
            speak("Face Authentication Unsuccessful. Access Denied!")

    os.system('start brave.exe --app="http://localhost:8000/index.html"')

    eel.start('index.html', mode=None, host='localhost', block=True)