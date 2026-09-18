import pyttsx3
import speech_recognition as sr
import eel

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
    engine = pyttsx3.init('sapi5')
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[0].id)
    engine.setProperty('rate', 174)

    # Send assistant reply once to the UI (receiverText). Avoid duplicate DisplayMessage here.
    if display:
        _safe_display('receiverText', text)

    # speak aloud
    # Mark JARVIS as speaking so the hotword process knows
    # that "Jarvis" should be treated as an interruption signal.
    if _speaking_event is not None:
        _speaking_event.set()

    try:
        engine.say(text)
        engine.runAndWait()
    finally:
        if _speaking_event is not None:
            _speaking_event.clear()

# @eel.expose #for main.js file to access functions of backend
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
    return_to_oval = True

    if message == 1:
        query = takecommand()
        print(f"Recognized query: {query}")
        _safe_display('senderText', query)
    else:
        query = message
        _safe_display('senderText', query)
    try:
        if query == "":
            speak("I didn't catch that. Please try again.")
            return
        
        if "open" in query:
            from engine.features import openCommand
            openCommand(query)
        
        elif "youtube" in query:
            from engine.features import PlayYoutube
            PlayYoutube(query) 
        
        elif "send message" in query or "phone call" in query or "video call" in query:
            from engine.features import findContact, whatsApp, makeCall, sendMessage
            contact_no, name = findContact(query)
            if (contact_no != 0):
                speak("Sir, Which mode you would like to use WhatsApp or Mobile ?")
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
                message=""
                if "send message" in query:
                    message = 'message'
                    speak("What message to send, Sir?")
                    query=takecommand()
                
                elif "phone call" in query:
                    message = 'call'
                else:
                    message = 'video call'

                whatsApp(contact_no, query, message, name)

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
            # TTS still speaks the exact same response, but receiverText()
            # does not receive a second duplicate copy.
            _safe_display(
                'assistantResponse',
                response
            )

            # Return to the main JARVIS HUD immediately.
            # Do this BEFORE TTS because speak() blocks while
            # pyttsx3.runAndWait() is speaking the response.
          # Keep the response on the SiriWave screen.
            return_to_oval = False

            speak(
                response,
                display=False
            )
        
    except Exception as e:
        print(f"Error in allCommands: {e}")
        speak("There was an error processing your command")
    
    if return_to_oval:
        _safe_display('ShowHood')