import os
import re
import threading
from datetime import datetime, timezone
import speech_recognition as sr
import eel

from engine.tts import speak as _tts_speak
from engine.stt import detect_text_language, transcribe_audio
from engine.llm_client import ask_llm, LLMRequestError
from engine.llm_recovery import resolve_pending_retry
from engine.conversation import get_conversation_manager
from engine.intent_classifier import classify_intent
from engine.context_interpreter import (
    interpret_query,
    should_interpret_query,
)
from engine.interaction_state import get_interaction_state
from engine.memory import (
    extract_memories_from_turn,
    record_episode,
)
from engine.legacy_routing import (
    is_legacy_message_command,
    is_legacy_open_command,
    is_legacy_youtube_command,
)
from engine.reference_resolver import (
    assistant_requests_confirmation,
    is_clear_affirmative_confirmation,
    is_clear_negative_confirmation,
)
from engine.persona import build_jarvis_prompt

from engine.settings_store import (
    load_settings,
    update_settings,
)

from engine.intelligence_context import build_turn_intelligence_context

from engine.automation import (
    route_command,
    complete_action,
    execute_action,
)

conversation_manager = get_conversation_manager()

# The continuous mode owns one microphone capture cycle at a time. Its event is
# shared with the Porcupine process so the two listeners never open the device
# concurrently.
_continuous_listening_event = threading.Event()
_continuous_thread = None
_continuous_thread_lock = threading.Lock()
_assistant_ready = False


def _is_stop_listening_request(text):
    value = " ".join(
        re.sub(r"[^a-z0-9 ]+", " ", str(text or "").casefold()).split()
    )
    return value in {
        "stop listening",
        "pause listening",
        "stop continuous listening",
        "pause continuous listening",
        "jarvis stop listening",
        "jarvis pause listening",
    }


def _continuous_listening_loop(stop_event):
    global _continuous_thread

    recognizer = sr.Recognizer()
    try:
        pause_threshold = float(
            os.getenv("JARVIS_CONTINUOUS_PAUSE_THRESHOLD", "0.8")
        )
    except (TypeError, ValueError):
        pause_threshold = 0.8
    recognizer.pause_threshold = max(0.35, min(pause_threshold, 2.0))

    try:
        phrase_limit = float(
            os.getenv("JARVIS_CONTINUOUS_PHRASE_LIMIT", "8")
        )
    except (TypeError, ValueError):
        phrase_limit = 8.0
    phrase_limit = max(2.0, min(phrase_limit, 20.0))

    calibrate = True
    _safe_display("setContinuousListeningStatus", True, "Listening")

    try:
        while (
            not stop_event.is_set()
            and _continuous_listening_event.is_set()
        ):
            query, language = takecommand(
                return_language=True,
                recognizer=recognizer,
                listen_timeout=1.0,
                phrase_time_limit=phrase_limit,
                calibrate=calibrate,
            )
            calibrate = False

            if stop_event.is_set() or not _continuous_listening_event.is_set():
                break

            if not query:
                continue

            if _is_stop_listening_request(query):
                update_settings({"continuous_listening": False})
                _continuous_listening_event.clear()
                stop_event.set()
                speak(
                    "Continuous listening is paused.",
                    language=language or "en",
                )
                break

            _safe_display(
                "setContinuousListeningStatus",
                True,
                "Processing your request",
            )
            allCommands(
                query,
                voice_input=True,
                detected_language=language,
            )

            if (
                not stop_event.is_set()
                and _continuous_listening_event.is_set()
            ):
                _safe_display(
                    "setContinuousListeningStatus",
                    True,
                    "Listening",
                )

    except Exception as exc:
        print(
            "Continuous listening stopped after an error: "
            f"{type(exc).__name__}: {exc}"
        )
        _safe_display(
            "setContinuousListeningStatus",
            False,
            "Microphone unavailable",
        )

    finally:
        with _continuous_thread_lock:
            if _continuous_thread is threading.current_thread():
                _continuous_thread = None
                _continuous_listening_event.clear()
        _safe_display(
            "setContinuousListeningStatus",
            False,
            "Paused",
        )


def set_assistant_ready(ready=True):
    """Enable automatic listening only after the authentication flow succeeds."""
    global _assistant_ready
    _assistant_ready = bool(ready)

    if not _assistant_ready:
        setContinuousListening(False)
        return {"success": True, "enabled": False}

    if load_settings().get("continuous_listening", False):
        return setContinuousListening(True)

    return {"success": True, "enabled": False}


@eel.expose
def setContinuousListening(enabled):
    """Start or stop the optional hands-free voice capture loop."""
    global _continuous_thread

    enabled = bool(enabled)

    if enabled:
        if not _assistant_ready:
            return {
                "success": False,
                "enabled": False,
                "message": "Complete authentication before enabling continuous listening.",
            }

        with _continuous_thread_lock:
            if _continuous_thread is not None and _continuous_thread.is_alive():
                if _continuous_listening_event.is_set():
                    return {
                        "success": True,
                        "enabled": True,
                        "message": "Continuous listening is already active.",
                    }
                return {
                    "success": False,
                    "enabled": False,
                    "message": "The previous microphone session is still stopping. Try again shortly.",
                }

            stop_event = threading.Event()
            _continuous_listening_event.set()
            _continuous_thread = threading.Thread(
                target=_continuous_listening_loop,
                args=(stop_event,),
                name="jarvis-continuous-listener",
                daemon=True,
            )
            _continuous_thread._jarvis_stop_event = stop_event
            _continuous_thread.start()

        return {
            "success": True,
            "enabled": True,
            "message": "Continuous listening enabled.",
        }

    _continuous_listening_event.clear()
    with _continuous_thread_lock:
        worker = _continuous_thread
        if worker is not None and worker.is_alive():
            # The worker checks this event between bounded microphone captures.
            worker_stop = getattr(worker, "_jarvis_stop_event", None)
            if worker_stop is not None:
                worker_stop.set()

    _safe_display(
        "setContinuousListeningStatus",
        False,
        "Paused",
    )
    return {
        "success": True,
        "enabled": False,
        "message": "Continuous listening paused.",
    }


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
            "continuous_listening": False,
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

        saved = update_settings(settings)

        runtime_state = None
        if "continuous_listening" in settings and _assistant_ready:
            runtime_state = setContinuousListening(
                saved.get("continuous_listening", False)
            )

        return {
            "success": True,
            "settings": saved,
            "continuous_listening_state": runtime_state,
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

        # Pending selections/clarifications belong to the previous live turn,
        # not to a conversation loaded from history.
        get_interaction_state().clear()

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
                        "timestamp": turn.get("user_timestamp") or turn.get("timestamp"),
                    }
                )

            if assistant_text:
                messages.append(
                    {
                        "role": "assistant",
                        "content": str(assistant_text),
                        "timestamp": turn.get("assistant_timestamp") or turn.get("timestamp"),
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
        get_interaction_state().clear()

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
    continuous_listening_event=None,
):
    """Configure shared audio-control events supplied by run.py."""
    global _interrupt_event
    global _speaking_event
    global _mic_busy_event
    global _continuous_listening_event

    _interrupt_event = interrupt_event
    _speaking_event = speaking_event
    _mic_busy_event = mic_busy_event
    if continuous_listening_event is not None:
        _continuous_listening_event = continuous_listening_event


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
    respect_voice_setting=False,
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

    try:
        return _tts_speak(
            text,
            language=language,
            interrupt_event=_interrupt_event,
            speaking_event=_speaking_event,
        )
    except Exception as exc:
        # Keep the already-rendered text answer usable when the audio device
        # or TTS engine fails. A voice failure must not discard the response.
        print(f"TTS failure: {type(exc).__name__}")
        _safe_display(
            "DisplayMessage",
            "Voice output is unavailable. The text response remains visible.",
        )
        return False


def takecommand(
    return_language=False,
    *,
    recognizer=None,
    listen_timeout=10,
    phrase_time_limit=6,
    calibrate=True,
):
    """Capture one utterance and automatically detect English/Hindi.

    Existing callers can keep using takecommand() -> string.
    The conversation flow can use takecommand(return_language=True) ->
    (query, detected_language).
    """
    r = recognizer or sr.Recognizer()

    if _mic_busy_event is not None:
        _mic_busy_event.set()

    try:
        with sr.Microphone() as source:
            print("Listening ....")
            _safe_display(
                "DisplayMessage",
                "Listening ....",
            )

            if calibrate:
                r.adjust_for_ambient_noise(source)

            audio = r.listen(
                source,
                timeout=listen_timeout,
                phrase_time_limit=phrase_time_limit,
            )

        print("Recognizing ....")
        _safe_display(
            "DisplayMessage",
            "Recognizing ....",
        )

        query, language, confidence = transcribe_audio(
            audio
        )

        if not query:
            if return_language:
                return "", ""

            return ""

        if language not in {
            "en",
            "hi",
        }:
            print(
                "Detected unsupported language: "
                f"{language or 'unknown'}"
            )

            speak(
                "I currently support English and Hindi.",
                language="en",
            )

            if return_language:
                return "", ""

            return ""

        print(
            f"User Said: {query}"
        )

        print(
            f"Speech language: {language} "
            f"(confidence={confidence:.2f})"
        )

        _safe_display(
            "animateRecognizedQuery",
            query,
        )

        if return_language:
            return query.lower(), language

        return query.lower()

    except sr.WaitTimeoutError:
        if return_language:
            return "", ""
        return ""

    except Exception as e:
        print(
            "Speech recognition failure: "
            f"{type(e).__name__}: {e}"
        )
        _safe_display(
            "DisplayMessage",
            "Speech input failed. Please try speaking again or type your request.",
        )

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


def _handle_llm_failure(
    error,
    query,
    raw_transcript,
    response_language,
    is_voice_input,
):
    """Preserve the failed request and offer an explicit, safe retry."""
    state = get_interaction_state()
    previous_interaction = {
        "state_type": state.state_type,
        "prompt": state.prompt,
        "action_type": state.action_type,
        "candidates": list(state.candidates),
        "data": dict(state.data),
    } if state.has_state() else {}
    message = (
        "The AI service is not configured correctly. "
        "Your request is preserved; fix the configuration and say 'retry'."
        if error.category == "configuration"
        else
        "I couldn't get a reliable AI response. Your request is preserved "
        "in this conversation. Say 'retry' to try it again, or send a "
        "different request."
    )

    state.set(
        "llm_retry",
        prompt="say retry to repeat the preserved request, or send a new request",
        action_type="retry_llm_request",
        pending_request=str(query or ""),
        raw_transcript=str(raw_transcript or query or ""),
        language=response_language or "en",
        is_voice_input=bool(is_voice_input),
        error_category=error.category,
        previous_interaction_state=previous_interaction,
    )

    assistant_timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    conversation_manager.add_turn(
        str(query or raw_transcript or ""),
        message,
    )

    try:
        from engine.mongo_store import save_chat_turn

        save_chat_turn(
            str(query or raw_transcript or ""),
            message,
            model=os.getenv("OMNIROUTE_MODEL", ""),
            meta={
                "provider": os.getenv("LLM_PROVIDER", "omniroute"),
                "error_category": error.category,
                "recovery": "pending_user_retry",
            },
            conversation_id=conversation_manager.conversation_id,
            user_timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            assistant_timestamp=assistant_timestamp,
            raw_user_text=str(raw_transcript or query or ""),
            interpreted_user_text=str(query or raw_transcript or ""),
            interpretation={
                "intent": "llm_error",
                "confidence": 0.0,
                "used_context": True,
            },
        )
    except Exception as persistence_error:
        print(f"LLM recovery history persistence unavailable: {persistence_error}")

    _safe_display(
        "assistantResponse",
        message,
        assistant_timestamp,
    )
    speak(
        message,
        language=response_language or "en",
    )


@eel.expose
def allCommands(message=1, *, voice_input=None, detected_language=None):
    # Initial query comes either from the microphone or the text box. The
    # continuous-listener worker supplies an already captured voice transcript.
    is_voice_input = (
        message == 1 if voice_input is None else bool(voice_input)
    )
    if message == 1 and voice_input is not True:
        query, query_language = takecommand(
            return_language=True
        )

        print(
            f"Recognized query: {query}"
        )

    else:
        query = message
        query_language = (
            detected_language
            or detect_text_language(str(query))
        )

    # A previous model failure keeps its original request in ephemeral state.
    # Only an explicit retry replays that request; a different utterance starts
    # a new request and clears the stale retry state.
    retry_state = get_interaction_state()
    retry_replay = None
    retry_cancelled = False
    retry_resolution = resolve_pending_retry(query, retry_state)
    if retry_resolution is not None:
        if retry_resolution.action == "retry":
            retry_replay = {
                "raw_transcript": retry_resolution.raw_transcript,
            }
            query = retry_resolution.pending_request
            query_language = retry_resolution.language or query_language
            is_voice_input = retry_resolution.is_voice_input
        elif retry_resolution.action == "cancel":
            retry_cancelled = True

    # Phase 3/5 conversation loop:
    # If an LLM response is interrupted by saying "Jarvis", the loop
    # listens for the next query and continues without another activation.
    while True:
        raw_transcript = str(query or "").strip()
        if retry_replay is not None:
            raw_transcript = str(
                retry_replay.get("raw_transcript") or raw_transcript
            ).strip()
            retry_replay = None
        user_timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        if query:
            _safe_display(
                "senderText",
                query,
                user_timestamp,
            )

        try:
            if retry_cancelled:
                speak(
                    "Understood. I won't retry the previous request.",
                    language=query_language or "en",
                )
                break

            if query == "":
                speak(
                    "I didn't catch that. Please try again.",
                    language="en",
                )
                break

            # A clear rejection cancels only the outstanding confirmation.
            # It is handled before interpretation so "no" cannot become an
            # accidental affirmative or be routed as an automation command.
            current_state = get_interaction_state()
            if (
                current_state.state_type == "confirmation"
                and is_clear_negative_confirmation(raw_transcript)
            ):
                cancellation_response = "Understood. I won't proceed with that request."
                current_state.clear()
                conversation_manager.add_turn(
                    raw_transcript,
                    cancellation_response,
                )
                assistant_timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                try:
                    from engine.mongo_store import save_chat_turn

                    save_chat_turn(
                        raw_transcript,
                        cancellation_response,
                        conversation_id=conversation_manager.conversation_id,
                        user_timestamp=user_timestamp,
                        assistant_timestamp=assistant_timestamp,
                        raw_user_text=raw_transcript,
                        interpreted_user_text=raw_transcript,
                        interpretation={
                            "intent": "cancellation",
                            "confidence": 1.0,
                            "used_context": True,
                        },
                    )
                except Exception as persistence_error:
                    print(f"Confirmation cancellation persistence unavailable: {persistence_error}")

                _safe_display(
                    "assistantResponse",
                    cancellation_response,
                    assistant_timestamp,
                )
                speak(
                    cancellation_response,
                    language=query_language or "en",
                )
                break

            # Phase 8.1: preserve the raw utterance and interpret only when
            # context, pending state, memory, or a target-sensitive request
            # makes interpretation useful. Clear known application launches
            # stay on the deterministic fast path.
            interpretation = None
            turn_context = build_turn_intelligence_context(
                query,
                conversation_manager,
            )
            memory_context = turn_context.memory_context
            profile_context = turn_context.profile_context
            conversation_context = turn_context.interpreter_conversation_context
            interaction_context = turn_context.interaction_context

            should_interpret = should_interpret_query(
                query,
                conversation_context=conversation_context,
                memory_context=memory_context,
                profile_context=profile_context,
                interaction_state=interaction_context,
                is_voice_input=is_voice_input,
            )

            if should_interpret:
                try:
                    interpretation = interpret_query(
                        raw_transcript,
                        conversation_context=conversation_context,
                        interaction_state=interaction_context,
                        memory_context=memory_context,
                        profile_context=profile_context,
                        language=query_language or "en",
                    )
                except LLMRequestError as error:
                    # Do not discard a pending selection/clarification when the
                    # interpreter cannot reach its model. Keep the original
                    # request available for an explicit retry.
                    _handle_llm_failure(
                        error,
                        raw_transcript,
                        raw_transcript,
                        query_language or "en",
                        is_voice_input,
                    )
                    break

                print(
                    "Context interpretation: "
                    f"{interpretation.interpreted_query!r} "
                    f"(intent={interpretation.intent}, "
                    f"confidence={interpretation.confidence:.2f})"
                )

                if interpretation.needs_clarification:
                    clarification = (
                        interpretation.clarification_question
                        or "Could you clarify what you mean?"
                    )
                    # Retain the pending clarification so the next utterance
                    # is interpreted as its answer, not as an unrelated command.
                    get_interaction_state().set(
                        "clarification",
                        prompt=clarification,
                        raw_transcript=raw_transcript,
                        candidate_query=interpretation.interpreted_query,
                    )
                    speak(
                        clarification,
                        language=query_language or "en",
                    )
                    break

                current_state = get_interaction_state()
                if current_state.state_type == "clarification":
                    try:
                        minimum_confidence = float(
                            os.getenv(
                                "JARVIS_INTERPRETATION_MIN_CONFIDENCE",
                                "0.70",
                            )
                        )
                    except (TypeError, ValueError):
                        minimum_confidence = 0.70

                    if (
                        interpretation.confidence < minimum_confidence
                        or interpretation.intent == "unknown"
                    ):
                        # Do not drop pending clarification state after an
                        # interpreter failure or uncertain answer.
                        speak(
                            current_state.prompt
                            or "I still need you to clarify that request.",
                            language=query_language or "en",
                        )
                        break

                if current_state.state_type == "confirmation":
                    if is_clear_affirmative_confirmation(raw_transcript):
                        try:
                            minimum_confidence = float(
                                os.getenv(
                                    "JARVIS_INTERPRETATION_MIN_CONFIDENCE",
                                    "0.70",
                                )
                            )
                        except (TypeError, ValueError):
                            minimum_confidence = 0.70

                        if (
                            interpretation.confidence < minimum_confidence
                            or interpretation.query.strip().casefold() == raw_transcript.casefold()
                            or is_clear_affirmative_confirmation(interpretation.query)
                        ):
                            # Never route a bare "yes/do it" when the target action
                            # could not be recovered with sufficient confidence.
                            speak(
                                "I couldn't safely determine which action you are approving. "
                                + (current_state.prompt or "Please state the action you want me to take."),
                                language=query_language or "en",
                            )
                            break
                        current_state.clear()
                    else:
                        # A complete new request supersedes the pending question;
                        # its relevant history remains available to the interpreter.
                        current_state.clear()

                query = interpretation.query
                # A previous clarification has now received a sufficiently
                # confident answer, so its temporary state can be cleared.
                if current_state.state_type == "clarification":
                    current_state.clear()

            intent_result = classify_intent(
                query,
                raw_text=raw_transcript,
                interpretation=interpretation,
                interaction_state=get_interaction_state(),
            )
            print(
                "Semantic intent: "
                f"{intent_result.intent.value} "
                f"(confidence={intent_result.confidence:.2f}, "
                f"source={intent_result.source})"
            )
            # Use the classifier's preserved/corrected query consistently
            # for both routing and the conversational response path.
            query = intent_result.normalized_query or query

            # Classification selects the pathway only. The deterministic
            # router still constructs AutomationAction objects, and the
            # existing executor remains responsible for authorization.
            automation_action = (
                route_command(intent_result.normalized_query or query)
                if intent_result.should_route_automation
                else None
            )

            if automation_action is not None:
                try:
                    automation_action = complete_action(
                        automation_action
                    )

                    if automation_action is None:
                        break

                    automation_result = execute_action(
                        automation_action
                    )
                except Exception as automation_error:
                    # Clear stale dialogue state so the user cannot accidentally
                    # answer an old selection/confirmation after execution failed.
                    get_interaction_state().clear()
                    # Do not claim success or automatically repeat an action
                    # when an exception leaves its final execution state uncertain.
                    print(
                        "Automation execution failure: "
                        f"{type(automation_error).__name__}"
                    )
                    recovery_message = (
                        "I couldn't verify whether that desktop action completed. "
                        "Please check the target before asking me to repeat it."
                    )
                    assistant_timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                    conversation_manager.add_turn(
                        query,
                        recovery_message,
                    )
                    try:
                        from engine.mongo_store import save_chat_turn

                        save_chat_turn(
                            query,
                            recovery_message,
                            meta={
                                "error_category": "automation_execution_uncertain",
                                "action_type": getattr(automation_action, "action_type", "unknown"),
                            },
                            conversation_id=conversation_manager.conversation_id,
                            user_timestamp=user_timestamp,
                            assistant_timestamp=assistant_timestamp,
                            raw_user_text=raw_transcript,
                            interpreted_user_text=query,
                        )
                    except Exception as persistence_error:
                        print(f"Automation recovery persistence unavailable: {persistence_error}")

                    _safe_display(
                        "assistantResponse",
                        recovery_message,
                        assistant_timestamp,
                    )
                    speak(
                        recovery_message,
                        language=query_language or "en",
                    )
                    break

                if automation_result.get(
                    "success"
                ):
                    if automation_action.action_type == "read_application":
                        # Show the extracted text in the UI, but keep TTS concise.
                        _safe_display(
                            "receiverText",
                            automation_result.get("message", ""),
                        )
                        speak(
                            automation_result.get(
                                "spoken_message",
                                "I read the visible application text and displayed it.",
                            ),
                            display=False,
                            language=query_language or "en",
                        )
                    elif (
                        automation_action.action_type
                        == "find_file"
                        and automation_result.get(
                            "message"
                        )
                    ):
                        speak(
                            automation_result.get(
                                "message",
                                "Action completed successfully.",
                            ),
                            display=False,
                        )
                    else:
                        speak(
                            automation_result.get(
                                "message",
                                "Action completed successfully.",
                            )
                        )

                else:
                    speak(
                        automation_result.get(
                            "message",
                            "The action could not be completed.",
                        )
                    )

                if automation_result.get("success"):
                    action_message = str(
                        automation_result.get(
                            "summary" if automation_action.action_type == "read_application" else "message",
                            "Action completed successfully.",
                        )
                    )
                    try:
                        # Application text can contain private document content. Keep
                        # it in the immediate UI response, not durable long-term memory.
                        if automation_action.action_type != "read_application":
                            record_episode(
                                query,
                                outcome=action_message,
                                action_type=automation_action.action_type,
                                conversation_id=conversation_manager.conversation_id,
                                metadata={
                                    "action_type": automation_action.action_type,
                                    "raw_transcript": raw_transcript,
                                    "interpreted_query": query,
                                    "interpretation_confidence": (
                                        interpretation.confidence
                                        if interpretation is not None
                                        else None
                                    ),
                                },
                            )
                        # The conversation context uses the understood request;
                        # the original transcript is retained in memory metadata.
                        conversation_manager.add_turn(
                            query,
                            action_message,
                        )
                    except Exception as memory_error:
                        print(
                            "Action memory recording unavailable: "
                            f"{memory_error}"
                        )

                break

            if intent_result.should_route_automation and is_legacy_open_command(query):
                from engine.features import openCommand

                openCommand(query)

            elif intent_result.should_route_automation and is_legacy_youtube_command(query):
                from engine.features import PlayYoutube

                PlayYoutube(query)

            elif intent_result.should_route_automation and is_legacy_message_command(query):
                from engine.features import (
                    findContact,
                    whatsApp,
                    makeCall,
                    sendMessage,
                )

                contact_no, name = findContact(
                    query
                )

                if contact_no == 0:
                    speak(
                        "I could not find that contact."
                    )
                    break

                speak(
                    "Sir, Which mode you would like "
                    "to use WhatsApp or Mobile?"
                )

                preference = takecommand()

                print(
                    f"Call/message preference: "
                    f"{preference}"
                )

                if "mobile" in preference:
                    if (
                        "send message" in query
                        or "send sms" in query
                    ):
                        speak(
                            "What message to send, Sir?"
                        )

                        message = takecommand()

                        sendMessage(
                            message,
                            contact_no,
                            name,
                        )

                    elif "phone call" in query:
                        makeCall(
                            name,
                            contact_no,
                        )

                    else:
                        speak(
                            "Please try again."
                        )

                elif "whatsapp" in preference:
                    message = ""

                    if "send message" in query:
                        message = "message"

                        speak(
                            "What message to send, Sir?"
                        )

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
                    speak(
                        "I didn't recognize the mode. "
                        "Please say WhatsApp or Mobile."
                    )

            else:
                from engine.mongo_store import save_chat_turn

                print(
                    "🧠 Sending request to OmniRoute... ✨"
                )

                _safe_display(
                    "DisplayMessage",
                    "Thinking...",
                )

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
                    response_language = (
                        configured_language
                    )

                language_name = _language_name(
                    response_language
                )

                context_section = turn_context.response_context

                enhanced_prompt = build_jarvis_prompt(
                    query,
                    language_name,
                    context_section,
                )

                try:
                    response = ask_llm(
                        enhanced_prompt
                    )
                except LLMRequestError as error:
                    _handle_llm_failure(
                        error,
                        query,
                        raw_transcript,
                        response_language,
                        is_voice_input,
                    )
                    break

                assistant_timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")

                print(
                    "JARVIS:",
                    response,
                )

                try:
                    save_chat_turn(
                        query,
                        response,
                        model=os.getenv(
                            "OMNIROUTE_MODEL",
                            "Teamax",
                        ),
                        meta={
                            "language": (
                                query_language
                                or "en"
                            ),
                            "provider": os.getenv(
                                "LLM_PROVIDER",
                                "omniroute",
                            ),
                        },
                        conversation_id=(
                            conversation_manager
                            .conversation_id
                        ),
                        user_timestamp=user_timestamp,
                        assistant_timestamp=assistant_timestamp,
                        raw_user_text=raw_transcript,
                        interpreted_user_text=query,
                        interpretation=(
                            {
                                "intent": interpretation.intent,
                                "confidence": interpretation.confidence,
                                "used_context": interpretation.used_context,
                            }
                            if interpretation is not None
                            else {
                                "intent": "unmodified",
                                "confidence": 1.0,
                                "used_context": False,
                            }
                        ),
                    )

                except Exception as e:
                    print(
                        f"Database save error: {e}"
                    )

                conversation_manager.add_turn(
                    query,
                    response,
                )

                if assistant_requests_confirmation(response):
                    # Persist the assistant's pending question across allCommands
                    # calls so a later "yes", "do it", or "cancel" is interpreted
                    # against the right task instead of as a standalone utterance.
                    get_interaction_state().set(
                        "confirmation",
                        prompt=response,
                        action_type="confirm_previous_task",
                        pending_request=query,
                    )

                _safe_display(
                    "assistantResponse",
                    response,
                    assistant_timestamp,
                )

                interrupted = speak(
                    response,
                    display=False,
                    language=response_language,
                    respect_voice_setting=True,
                )

                # Run selective durable-memory extraction after the response
                # has been displayed/spoken, so memory maintenance does not
                # delay the user's current answer.
                try:
                    extract_memories_from_turn(
                        raw_transcript,
                        response,
                        conversation_id=conversation_manager.conversation_id,
                    )
                except Exception as memory_error:
                    print(
                        "Long-term memory extraction unavailable: "
                        f"{memory_error}"
                    )

                if interrupted:
                    print(
                        "Speech was interrupted by "
                        "the JARVIS hotword."
                    )

                    _safe_display(
                        "ShowSiriWave"
                    )

                    import time

                    time.sleep(
                        0.15
                    )

                    print(
                        "Listening for the next query..."
                    )

                    _safe_display(
                        "DisplayMessage",
                        "Listening for your next query...",
                    )

                    query, query_language = takecommand(
                        return_language=True
                    )

                    if query == "":
                        speak(
                            "I didn't catch that. "
                            "Please try again.",
                            language="en",
                        )
                        break

                    continue

                print(
                    "Speech completed normally."
                )

            break

        except Exception as e:
            print(
                f"Error in allCommands: {e}"
            )

            speak(
                "There was an error processing your command",
                language="en",
            )

            break

    _safe_display(
        "ShowHood"
    )


if __name__ == "__main__":
    pass