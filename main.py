import os
import eel
import subprocess

from engine.gemini_client import init_gemini, is_available
from engine.auth import recognizer as recognize
from engine.features import *
from engine.command import *

# Try importing python-dotenv in a linter-friendly way
try:
    from dotenv import load_dotenv  # type: ignore
    _has_dotenv = True
except Exception:
    _has_dotenv = False

# Call load_dotenv only if available
if _has_dotenv:
    load_dotenv()
else:
    # Avoid noisy printing at import time during multiprocessing;
    # just note the state.
    _dotenv_missing = True


def start(
    interrupt_event=None,
    speaking_event=None,
    mic_busy_event=None
    ):
    
    # Configure shared audio state for command.py.
    from engine.command import configure_audio_control

    configure_audio_control(
        interrupt_event=interrupt_event,
        speaking_event=speaking_event,
        mic_busy_event=mic_busy_event,
    )
    
    # If dotenv was missing earlier, print a hint only when start runs.
    if globals().get('_dotenv_missing', False):
        print(
            "python-dotenv not found; environment variables will be read "
            "from the OS. Install with `pip install python-dotenv` if needed."
        )

    api_key = os.getenv('GEMINI_API_KEY')

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found in environment variables"
        )

    # Always initialize the global gemini_client object so it's not None later.
    # GeminiClient will set itself as 'unavailable' when
    # google-generativeai is not installed.
    init_gemini(api_key)

    eel.init("www")

    playAssistantSound()

    @eel.expose
    def init():
        # Run the device setup batch file if it exists.
        project_root = os.path.dirname(os.path.abspath(__file__))
        device_bat = os.path.join(project_root, "device.bat")

        if os.path.isfile(device_bat):
            try:
                subprocess.call(
                    ["cmd", "/c", device_bat],
                    cwd=project_root
                )
            except Exception as e:
                print("Device batch file error:", e)
        else:
            print("device.bat not found; continuing without device setup.")

        # Show the face-authentication UI.
        eel.hideLoader()

        speak("Ready for Face Authentication")

        # Send frames from the SAME OpenCV camera used by
        # recognizer.AuthenticateFace() to the Eel frontend.
        def send_webcam_frame(jpg_base64, status, score=None):
            try:
                eel.updateWebcamFrame(
                    jpg_base64,
                    status,
                    score
                )()
            except Exception as e:
                print("Webcam UI update error:", e)

        # Start face authentication and provide the callback so the
        # recognizer can stream its live camera frames to the UI.
        flag = recognize.AuthenticateFace(
            frame_callback=send_webcam_frame
        )

        if flag == 1:
            eel.hideFaceAuth()

            speak(
                "Face Authentication Successful. "
                "System is fully operational now."
            )

            eel.hideFaceAuthSuccess()

            speak(
                "Welcome Back Sir, it's a pleasure to see you working!"
            )

            eel.hideStart()
            playAssistantSound()

        else:
            # Fallback to voice activation phrase (only if enabled).
            voice_enabled = os.getenv(
                'JARVIS_VOICE_ENABLED',
                '0'
            )

            if str(voice_enabled).lower() in (
                '1',
                'true',
                'yes'
            ):
                speak(
                    "Face Authentication Unsuccessful. "
                    "Trying voice fallback..."
                )

                try:
                    from engine.auth.voice_auth import listen_for_phrase

                    # Pass configured phrase and timeout from env via
                    # the function defaults.
                    voice_ok = listen_for_phrase()

                except Exception as e:
                    voice_ok = False
                    print(
                        'Voice fallback error:',
                        e
                    )

                if voice_ok:
                    eel.hideFaceAuth()

                    speak(
                        "Voice authentication successful. "
                        "System unlocked."
                    )

                    eel.hideFaceAuthSuccess()
                    eel.hideStart()
                    playAssistantSound()

                else:
                    speak(
                        "Authentication failed. "
                        "Access Denied!"
                    )

                    # Show Try Again button so user can trigger
                    # voice auth manually.
                    try:
                        eel.showTryAgain()
                    except Exception:
                        pass

            else:
                speak(
                    "Authentication failed. "
                    "Voice fallback is disabled."
                )

    @eel.expose
    def retryVoiceAuth():
        """Called from the UI when the user clicks 'Try Again'.
        Runs the voice fallback flow.
        """
        try:
            eel.hideTryAgain()()
        except Exception:
            pass

        speak(
            "Listening for voice activation phrase..."
        )

        try:
            from engine.auth.voice_auth import listen_for_phrase

            voice_ok = listen_for_phrase()

        except Exception as e:
            voice_ok = False
            print(
                'Voice fallback error (retry):',
                e
            )

        if voice_ok:
            try:
                eel.hideFaceAuth()
                eel.hideFaceAuthSuccess()
                eel.hideStart()
            except Exception:
                pass

            speak(
                "Voice authentication successful. "
                "System unlocked."
            )

            playAssistantSound()
            return True

        else:
            speak("Access Denied")

            try:
                eel.showTryAgain()()
            except Exception:
                pass

            return False

    os.system(
        'start brave.exe '
        '--app="http://localhost:8000/index.html"'
    )

    eel.start(
        'index.html',
        mode=None,
        host='localhost',
        block=True
    )


if __name__ == "__main__":
    start()