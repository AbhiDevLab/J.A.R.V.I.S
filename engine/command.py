import pyttsx3
import speech_recognition as sr
import eel
import time

# Shared process-safe audio control events.
_interrupt_event = None
_speaking_event = None
_mic_busy_event = None


def configure_audio_control(
    interrupt_event=None,
    speaking_event=None,
    mic_busy_event=None,
):
    """Configure shared audio-control events supplied by run.py."""
    global _interrupt_event
    global _speaking_event
    global _mic_busy_event

    _interrupt_event = interrupt_event
    _speaking_event = speaking_event
    _mic_busy_event = mic_busy_event


def _safe_display(fn, *args, **kwargs):
    try:
        f = getattr(eel, fn, None)
        if f:
            # call without waiting (fire-and-forget)
            f(*args, **kwargs)
    except Exception:
        # swallow UI errors so speak/takecommand don't crash when UI isn't ready
        pass


def speak(text, display=True):
    """
    Speak text through SAPI5 and allow the hotword process to interrupt it.

    Returns:
        True  -> speech was interrupted by the JARVIS hotword.
        False -> speech completed normally.
    """
    engine = pyttsx3.init('sapi5')
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[0].id)
    engine.setProperty('rate', 174)

    # Clear any stale interruption request left by an earlier speech cycle.
    if _interrupt_event is not None:
        _interrupt_event.clear()

    # Send assistant reply once to the UI (receiverText). Avoid duplicate
    # DisplayMessage calls here.
    if display:
        _safe_display('receiverText', text)

    if _speaking_event is not None:
        _speaking_event.set()

    interrupted = False
    loop_started = False

    try:
        engine.say(text)

        # Use pyttsx3's external loop so this thread can check the shared
        # interrupt event while SAPI5 is speaking. This keeps engine.stop()
        # on the same thread as the engine itself.
        engine.startLoop(False)
        loop_started = True

        while engine.isBusy():
            if (
                _interrupt_event is not None
                and _interrupt_event.is_set()
            ):
                interrupted = True
                print("JARVIS speech interrupted.")

                try:
                    engine.stop()
                except Exception as e:
                    print("TTS stop error:", e)

                # Pump SAPI5 events until the stop has actually completed.
                while engine.isBusy():
                    engine.iterate()
                    time.sleep(0.01)

                break

            engine.iterate()
            time.sleep(0.01)

    finally:
        if loop_started:
            try:
                engine.endLoop()
            except Exception:
                pass

        if _speaking_event is not None:
            _speaking_event.clear()

        if _interrupt_event is not None:
            _interrupt_event.clear()

    return interrupted


def takecommand():
    r = sr.Recognizer()

    if _mic_busy_event is not None:
        _mic_busy_event.set()

    try:
        with sr.Microphone() as source:
            print("Listening ....")
            _safe_display(
                'DisplayMessage',
                "Listening ...."
            )

            r.pause_threshold = 1
            r.adjust_for_ambient_noise(source)

            audio = r.listen(
                source,
                10,
                6
            )

        try:
            print('Recognizing ....')

            _safe_display(
                'DisplayMessage',
                "Recognizing ...."
            )

            query = r.recognize_google(
                audio,
                language='en-in'
            )

            print(f"User Said: {query}")

            _safe_display(
                'DisplayMessage',
                query
            )

        except Exception:
            return ""

        return query.lower()

    finally:
        if _mic_busy_event is not None:
            _mic_busy_event.clear()


@eel.expose
def allCommands(message=1):
    # Initial query comes either from the microphone or the text box.
    if message == 1:
        query = takecommand()
        print(f"Recognized query: {query}")
    else:
        query = message

    # Phase 3 conversation loop:
    #
    # A normal command runs once and returns to the Oval HUD.
    #
    # If a Gemini response is interrupted by saying "Jarvis", the loop
    # immediately listens for the next query and processes it without
    # requiring another hotword activation.
    while True:
        if query:
            _safe_display('senderText', query)

        try:
            if query == "":
                speak("I didn't catch that. Please try again.")
                break

            if "open" in query:
                from engine.features import openCommand
                openCommand(query)

            elif "youtube" in query:
                from engine.features import PlayYoutube
                PlayYoutube(query)

            elif (
                "send message" in query
                or "phone call" in query
                or "video call" in query
            ):
                from engine.features import (
                    findContact,
                    whatsApp,
                    makeCall,
                    sendMessage,
                )

                contact_no, name = findContact(query)

                if contact_no != 0:
                    speak(
                        "Sir, Which mode you would like to use WhatsApp or Mobile ?"
                    )
                    preference = takecommand()
                    print(preference)

                if "mobile" in preference:
                    if "send message" in query or "send sms" in query:
                        speak("What message to send, Sir?")
                        message = takecommand()
                        sendMessage(message, contact_no, name)

                    elif "phone call" in query:
                        makeCall(name, contact_no)

                    else:
                        speak("Please try again")

                elif "WhatsApp" in preference:
                    message = ""

                    if "send message" in query:
                        message = 'message'
                        speak("What message to send, Sir?")
                        query = takecommand()

                    elif "phone call" in query:
                        message = 'call'

                    else:
                        message = 'video call'

                    whatsApp(
                        contact_no,
                        query,
                        message,
                        name
                    )

            else:
                from engine.gemini_client import gemini_client
                from engine.mongo_store import save_chat_turn

                print("🤖 Sending to Gemini... ✨")

                # Show a clean processing state instead of exposing the internal prompt.
                _safe_display('DisplayMessage', "Thinking...")

                enhanced_prompt = f"""
        You are JARVIS, a polished desktop AI assistant.

        Answer the user's query directly, accurately, and conversationally.

        Formatting rules:
        - Return clean Markdown.
        - Use headings only when the answer has multiple logical sections.
        - Use bullet points or numbered lists when they improve readability.
        - Use **bold** for important terms.
        - Use `inline code` for commands, filenames, functions, variables, or technical identifiers.
        - Use fenced code blocks with a language identifier for code.
        - Use tables when comparing multiple items.
        - Keep simple questions concise.
        - For technical questions, organize the answer clearly and provide examples when useful.
        - Do not put the entire answer inside a code block.
        - Do not mention these formatting instructions.
        - Do not add unnecessary meta commentary.

        User Query:
        {query}

        JARVIS:
        """

                response = gemini_client.ask_gemini(enhanced_prompt)

                print("Gemini:", response)

                try:
                    save_chat_turn(
                        query,
                        response,
                        model="gemini-2.5-flash-lite"
                    )
                except Exception as e:
                    print(f"Database save error: {e}")

                # Display the response through the rich frontend renderer.
                # TTS speaks the exact same response.
                _safe_display(
                    'assistantResponse',
                    response
                )

                # Keep the response visible while JARVIS is speaking.
                # If the user says "Jarvis", speak() stops and returns True.
                interrupted = speak(
                    response,
                    display=False
                )

                if interrupted:
                    print(
                        "Speech was interrupted by the JARVIS hotword."
                    )

                    # Return to the normal HUD before listening again.
                    _safe_display('ShowHood')

                    # Give the hotword process a moment to notice
                    # mic_busy_event and release its Portaudio stream.
                    time.sleep(0.15)

                    print("Listening for the next query...")
                    _safe_display(
                        'DisplayMessage',
                        "Listening for your next query..."
                    )

                    query = takecommand()

                    if query == "":
                        speak(
                            "I didn't catch that. Please try again."
                        )
                        break

                    # Continue this same allCommands call with the new query.
                    continue

                print("Speech completed normally.")

            # Non-interrupted commands end the current interaction.
            break

        except Exception as e:
            print(f"Error in allCommands: {e}")
            speak("There was an error processing your command")
            break

    # Always return to the normal JARVIS HUD once the interaction ends.
    _safe_display('ShowHood')


if __name__ == "__main__":
    pass
