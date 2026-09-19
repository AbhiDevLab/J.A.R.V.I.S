import os
import speech_recognition as sr
import eel

from engine.tts import speak as _tts_speak
from engine.stt import detect_text_language, transcribe_audio
from engine.llm_client import ask_llm
from engine.conversation import get_conversation_manager

from engine.settings_store import (
    load_settings,
    update_settings,
)

conversation_manager = get_conversation_manager()

@eel.expose
def getSettings():
    """Return persistent JARVIS user settings."""
    try:
        return load_settings()

    except Exception as exc:
        print(
            f"Settings API error: {exc}"
        )

        return {
            "voice_enabled": True,
            "response_language": "auto",
        }


@eel.expose
def saveSettings(settings):
    """Persist user settings and return the saved state."""
    try:
        if not isinstance(settings, dict):
            return {
                "success": False,
                "settings": load_settings(),
            }

        saved =  update_settings(settings)

        return {
            "success": True,
            "settings": saved,
        }

    except Exception as exc:
        print(
            f"Settings save API error: {exc}"
        )

        return {
            "success": False,
            "settings": load_settings(),
        }

@eel.expose
def getConversationHistory(limit=20):
    """Return recent saved conversations for the history UI."""
    try:
        from engine.conversation import list_saved_conversations

        return list_saved_conversations(limit)

    except Exception as exc:
        print(
            f"Conversation history error: {exc}"
        )
        return []


@eel.expose
def loadConversation(conversation_id):
    """
    Load a saved conversation into the active JARVIS session.

    Returns the complete saved conversation for the frontend
    while ConversationManager keeps only recent turns for LLM context.
    """
    try:
        from engine.conversation import (
            load_conversation,
            load_saved_conversation,
        )

        if not conversation_id:
            return {
                "success": False,
                "conversation_id": "",
                "messages": [],
            }

        loaded = load_conversation(
            conversation_id
        )

        if not loaded:
            return {
                "success": False,
                "conversation_id": conversation_id,
                "messages": [],
            }

        turns = load_saved_conversation(
            conversation_id
        )

        messages = []

        for turn in turns:
            user_text = turn.get(
                "user_text",
                "",
            )

            assistant_text = turn.get(
                "assistant_text",
                "",
            )

            if user_text:
                messages.append(
                    {
                        "role": "user",
                        "content": str(user_text),
                    }
                )

            if assistant_text:
                messages.append(
                    {
                        "role": "assistant",
                        "content": str(assistant_text),
                    }
                )

        return {
            "success": True,
            "conversation_id": conversation_id,
            "messages": messages,
        }

    except Exception as exc:
        print(
            f"Conversation load API error: {exc}"
        )

        return {
            "success": False,
            "conversation_id": conversation_id or "",
            "messages": [],
        }


@eel.expose
def startNewConversation():
    """Start a completely new active JARVIS conversation."""
    try:
        conversation_id = (
            conversation_manager.start_new_conversation()
        )

        return {
            "success": True,
            "conversation_id": conversation_id,
            "messages": [],
        }

    except Exception as exc:
        print(
            f"New conversation error: {exc}"
        )

        return {
            "success": False,
            "conversation_id": "",
            "messages": [],
        }

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
            f(*args, **kwargs)
    except Exception:
        # swallow UI errors so speak/takecommand don't crash when UI isn't ready
        pass


def speak(
    text,
    display=True,
    language=None,
    respect_voice_setting=False
):
    """Speak text through TTS when voice responses are enabled."""
    if display:
        _safe_display(
            "receiverText",
            text,
        )

    if respect_voice_setting:
        settings = load_settings()

    if not settings.get(
        "voice_enabled",
        True,
    ):
        return False

    return _tts_speak(
        text,
        language=language,
        interrupt_event=_interrupt_event,
        speaking_event=_speaking_event,
    )

def takecommand(return_language=False):
    """Capture one utterance and automatically detect English/Hindi.

    Existing callers can keep using takecommand() -> string.
    The conversation flow can use takecommand(return_language=True) ->
    (query, detected_language).
    """
    r = sr.Recognizer()

    if _mic_busy_event is not None:
        _mic_busy_event.set()

    try:
        with sr.Microphone() as source:
            print("Listening ....")
            _safe_display("DisplayMessage", "Listening ....")

            r.pause_threshold = 1
            r.adjust_for_ambient_noise(source)
            audio = r.listen(source, 10, 6)

        print("Recognizing ....")
        _safe_display("DisplayMessage", "Recognizing ....")

        query, language, confidence = transcribe_audio(audio)

        if not query:
            if return_language:
                return "", ""
            return ""

        if language not in {"en", "hi"}:
            print(
                f"Detected unsupported language: {language or 'unknown'}"
            )
            speak(
                "I currently support English and Hindi.",
                language="en",
            )
            if return_language:
                return "", ""
            return ""

        print(f"User Said: {query}")
        print(
            f"Speech language: {language} "
            f"(confidence={confidence:.2f})"
        )
        _safe_display("DisplayMessage", query)

        if return_language:
            return query.lower(), language

        return query.lower()

    except Exception as e:
        print("Speech recognition error:", e)
        if return_language:
            return "", ""
        return ""

    finally:
        if _mic_busy_event is not None:
            _mic_busy_event.clear()


def _language_name(language):
    if language == "hi":
        return "Hindi"
    return "English"


@eel.expose
def allCommands(message=1):
    # Initial query comes either from the microphone or the text box.
    if message == 1:
        query, query_language = takecommand(return_language=True)
        print(f"Recognized query: {query}")
    else:
        query = message
        query_language = detect_text_language(str(query))

    # Phase 3/5 conversation loop:
    # If an LLM response is interrupted by saying "Jarvis", the loop
    # listens for the next query and continues without another activation.
    while True:
        if query:
            _safe_display("senderText", query)

        try:
            if query == "":
                speak(
                    "I didn't catch that. Please try again.",
                    language="en",
                )
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
                        message = "message"
                        speak("What message to send, Sir?")
                        query = takecommand()
                    elif "phone call" in query:
                        message = "call"
                    else:
                        message = "video call"

                    whatsApp(
                        contact_no,
                        query,
                        message,
                        name,
                    )

            else:
                from engine.mongo_store import save_chat_turn

                print("🧠 Sending request to OmniRoute... ✨")
                _safe_display("DisplayMessage", "Thinking...")

                settings = load_settings()

                configured_language = settings.get(
                    "response_language",
                    "auto",
                )

                response_language = query_language

                if configured_language in {
                    "en",
                    "hi",
                }:
                    response_language = configured_language

                language_name = _language_name(
                    response_language
                )
                               
                previous_context = conversation_manager.build_context()

                context_section = ""

                if previous_context:
                    context_section = f"""
                        {previous_context}

                        Use the previous conversation only when it is relevant to the
                        current query. Resolve references such as "it", "that", "this",
                        "the previous one", and follow-up questions using that context.
                    """

                enhanced_prompt = f"""
        You are JARVIS, a polished desktop AI assistant.

        Answer the user's query directly, accurately, and conversationally.
        
        {context_section}

        Language behavior:
        - The user's detected speech language is: {language_name}.
        - Respond in the same language as the user.
        - For Hindi, use natural contemporary Indian Hindi suitable for an Indian speaker.
        - Do not produce awkward literal translations from English.
        - Keep standard technical terms, product names, programming identifiers,
          acronyms, and commonly used English technical words in English when
          that is natural for an Indian Hindi speaker.
        - For English, use natural conversational English.
        - Do not switch languages unless the user does.

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

                response = ask_llm(enhanced_prompt)
                print("JARVIS:", response)

                try:
                    save_chat_turn(
                        query,
                        response,
                        model=os.getenv(
                            "OMNIROUTE_MODEL",
                            "Teamax",
                        ),
                        meta={
                            "language": query_language or "en",
                            "provider": os.getenv(
                                "LLM_PROVIDER",
                                "omniroute",
                            ),
                        },
                        conversation_id=conversation_manager.conversation_id,
                    )
                except Exception as e:
                    print(f"Database save error: {e}")
                    
                conversation_manager.add_turn(
                    query,
                    response,
                )

                _safe_display("assistantResponse", response)

                interrupted = speak(
                    response,
                    display=False,
                    language=response_language,
                    respect_voice_setting=True,
                )

                if interrupted:
                    print(
                        "Speech was interrupted by the JARVIS hotword."
                    )
                    _safe_display("ShowSiriWave")

                    import time
                    time.sleep(0.15)

                    print("Listening for the next query...")
                    _safe_display(
                        "DisplayMessage",
                        "Listening for your next query...",
                    )

                    query, query_language = takecommand(
                        return_language=True
                    )

                    if query == "":
                        speak(
                            "I didn't catch that. Please try again.",
                            language="en",
                        )
                        break

                    continue

                print("Speech completed normally.")

            break

        except Exception as e:
            print(f"Error in allCommands: {e}")
            speak(
                "There was an error processing your command",
                language="en",
            )
            break

    _safe_display("ShowHood")


if __name__ == "__main__":
    pass
