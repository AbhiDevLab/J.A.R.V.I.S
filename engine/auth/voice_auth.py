"""Voice fallback authentication.

Reads configuration from environment variables when available:
  - JARVIS_VOICE_ENABLED (1/0)
  - JARVIS_VOICE_PHRASE (string)
  - JARVIS_VOICE_TIMEOUT (int seconds)

Listens on the default microphone and attempts to recognize the activation
phrase using the SpeechRecognition library (Google Web Speech API). This is
meant as a fallback and requires internet access for the default recognizer.
"""
import os
import time
import speech_recognition as sr


DEFAULT_PHRASE = "genius, billionaire, playboy, philanthropist"


def listen_for_phrase(timeout: int | None = None, phrase: str | None = None) -> bool:
    """Listen for the phrase and return True if detected within timeout seconds.

    If `timeout` or `phrase` is None, values are read from environment:
    `JARVIS_VOICE_TIMEOUT` and `JARVIS_VOICE_PHRASE` respectively.
    """
    # read defaults from environment when not provided
    try:
        if timeout is None:
            timeout = int(os.getenv('JARVIS_VOICE_TIMEOUT', '6'))
    except Exception:
        timeout = 6

    if phrase is None:
        phrase = os.getenv('JARVIS_VOICE_PHRASE', DEFAULT_PHRASE)

    r = sr.Recognizer()
    try:
        mic = sr.Microphone()
    except Exception as e:
        print('Microphone not available:', e)
        return False

    print(f'Listening for voice-auth phrase ("{phrase}") for up to {timeout}s...')
    start = time.time()
    # keep attempting until the overall timeout expires
    while time.time() - start < timeout:
        remaining = max(1, int(timeout - (time.time() - start)))
        attempt_timeout = min(4, remaining)
        with mic as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = r.listen(source, timeout=attempt_timeout, phrase_time_limit=attempt_timeout)
            except sr.WaitTimeoutError:
                print('No speech detected (attempt timeout)')
                continue

        try:
            text = r.recognize_google(audio)
            text_clean = text.strip().lower()
            print('Heard:', text_clean)
            if text_clean == phrase.lower():
                return True
            else:
                # wrong phrase — announce access denied and keep listening
                print('Access Denied (wrong phrase)')
                try:
                    # import speak lazily to avoid heavy deps at module import
                    from engine.command import speak
                    speak('Access Denied')
                except Exception:
                    # fallback to simple print if speech fails
                    pass
                continue
        except sr.UnknownValueError:
            print('Could not understand audio (unknown)')
            continue
        except sr.RequestError as e:
            print('Speech recognition request failed:', e)
            return False

    print('Voice auth timed out')
    return False
