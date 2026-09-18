import os
import re
import sqlite3
import struct
import subprocess
import time
import webbrowser
from playsound import playsound
import eel
import pyaudio
import pyautogui
from engine.command import speak, takecommand
from engine.config import ASSISTANT_NAME, PRIMARY_ASSISTANT_NAME
import pywhatkit as kit
import pvporcupine
from shlex import quote

from engine.helper import extract_yt_term, remove_words

# Gemini API import
try:
    from engine.gemini_client import gemini_client
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Gemini client not available")

con = sqlite3.connect("jarvis.db")
cursor = con.cursor()

# Playing Assistant Sound Function
@eel.expose
def playAssistantSound():
    music_dir = "www\\assets\\audio\\start_sound.mp3"
    playsound(music_dir)

def openCommand(query):
    query = query.replace(PRIMARY_ASSISTANT_NAME, "")
    query = query.replace("open", "")
    query = query.strip().lower()  # Normalize to lowercase

    app_name = query

    if app_name != "":
        try:
            # Case-insensitive search in sys_command
            cursor.execute("SELECT path FROM sys_command WHERE LOWER(name) = LOWER(?)", (app_name,))
            result = cursor.fetchall()

            if len(result) != 0:
                path = result[0][0]
                # announce (speak will update the hood)
                speak("Opening " + app_name)

                if path.startswith("start"):
                    os.system(path)
                else:
                    os.startfile(path)

            else:
                # Case-insensitive search in web_command
                cursor.execute("SELECT url FROM web_command WHERE LOWER(name) = LOWER(?)", (app_name,))
                result = cursor.fetchall()

                if len(result) != 0:
                    speak("Opening " + app_name)
                    webbrowser.open(result[0][0])

                else:
                    speak("Opening " + app_name)
                    try:
                        os.system("start " + app_name + ".exe")
                    except Exception as e:
                        print(f"Error: {e}")
                        speak("Sorry, I am unable to open " + app_name)

        except Exception as e:
            print(f"Error in openCommand: {e}")
            speak("Something went wrong")

def PlayYoutube(query):
    try:
        # Remove trigger phrases
        search_term = query.replace("play", "").replace("on youtube", "").replace("youtube", "").strip()
        
        if not search_term:
            speak("What would you like me to play on YouTube?")
            search_term = takecommand().strip()
            
        if search_term:
            speak(f"Playing {search_term} on YouTube")
            kit.playonyt(search_term)
        else:
            speak("I didn't catch what you want to play on YouTube")
    except Exception as e:
        print(f"Error in PlayYoutube: {e}")
        speak("Sorry, I couldn't play that on YouTube")

#
def hotword(
    interrupt_event=None,
    speaking_event=None,
    mic_busy_event=None,
):
    porcupine = None
    paud = None
    audio_stream = None

    try:
        porcupine = pvporcupine.create(
            keywords=["jarvis"],
            sensitivities=[0.9],
        )

        paud = pyaudio.PyAudio()

        while True:

            # ---------------------------------------------------------
            # SpeechRecognition owns the microphone.
            # Release the Porcupine audio stream while it is busy.
            # ---------------------------------------------------------
            if (
                mic_busy_event is not None
                and mic_busy_event.is_set()
            ):
                if audio_stream is not None:
                    try:
                        audio_stream.stop_stream()
                    except Exception:
                        pass

                    try:
                        audio_stream.close()
                    except Exception:
                        pass

                    audio_stream = None

                time.sleep(0.05)
                continue

            # ---------------------------------------------------------
            # Re-open the Porcupine stream when the microphone
            # becomes available again.
            # ---------------------------------------------------------
            if audio_stream is None:
                audio_stream = paud.open(
                    rate=porcupine.sample_rate,
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    frames_per_buffer=porcupine.frame_length,
                )

            keyword = audio_stream.read(
                porcupine.frame_length,
                exception_on_overflow=False,
            )

            keyword = struct.unpack_from(
                "h" * porcupine.frame_length,
                keyword,
            )

            keyword_index = porcupine.process(keyword)

            if keyword_index >= 0:

                print("hotword detected")

                # -----------------------------------------------------
                # Phase 1 behavior:
                #
                # If JARVIS is speaking, mark the hotword as an
                # interruption request.
                #
                # We deliberately do NOT stop pyttsx3 yet.
                # That comes in Phase 2.
                # -----------------------------------------------------
                if (
                    speaking_event is not None
                    and speaking_event.is_set()
                ):

                    print(
                        "Hotword detected while JARVIS "
                        "is speaking."
                    )

                    if interrupt_event is not None:
                        interrupt_event.set()

                    continue

                # -----------------------------------------------------
                # Normal hotword activation remains unchanged.
                # -----------------------------------------------------
                import pyautogui as autogui

                autogui.keyDown("win")
                autogui.press("j")

                time.sleep(2)

                autogui.keyUp("win")

    except Exception as e:
        print("Hotword listener stopped:", e)

    finally:

        if porcupine is not None:
            try:
                porcupine.delete()
            except Exception:
                pass

        if audio_stream is not None:
            try:
                audio_stream.stop_stream()
            except Exception:
                pass

            try:
                audio_stream.close()
            except Exception:
                pass

        if paud is not None:
            try:
                paud.terminate()
            except Exception:
                pass

# Whatsapp Message Sending 
def findContact(query):

    words_to_remove = [ASSISTANT_NAME, 'make', 'a', 'to', 'phone', 'call', 'send', 'message', 'wahtsapp', 'video']
    query = remove_words(query, words_to_remove)

    try:
        query = query.strip().lower()
        cursor.execute("SELECT mobile_no FROM contacts WHERE LOWER(name) LIKE ? OR LOWER(name) LIKE ?", ('%' + query + '%', query + '%'))
        results = cursor.fetchall()
        print(results[0][0])
        mobile_number_str = str(results[0][0])

        if not mobile_number_str.startswith('+91'):
            mobile_number_str = '+91' + mobile_number_str

        return mobile_number_str, query
    except:
        speak('not exist in contacts')
        return 0, 0

def whatsApp(mobile_no, message, flag, name):

    if flag == 'message':
        target_tab = 12
        jarvis_message = "Sir, Message is sent successfully to "+name

    elif flag == 'call':
        target_tab = 7
        message = ''
        jarvis_message = "Calling to "+name

    else:
        target_tab = 6
        message = ''
        jarvis_message = "Starting video call with "+name

    # Encode the message for URL
    encoded_message = quote(message)

    # Construct the URL
    whatsapp_url = f"whatsapp://send?phone={mobile_no}&text={encoded_message}"

    # Construct the full command
    full_command = f'start "" "{whatsapp_url}"'

    # Open WhatsApp with the constructed URL using cmd.exe
    subprocess.run(full_command, shell=True)
    time.sleep(5)
    subprocess.run(full_command, shell=True)

    pyautogui.hotkey('ctrl', 'f')

    for i in range(1, target_tab):
        pyautogui.hotkey('tab')

    pyautogui.hotkey('enter')
    speak(jarvis_message)
    
# Android Automation
def makeCall(name, mobileNo):
    mobileNo = mobileNo.replace(" ", "")
    speak("Calling " + name)
    command = 'adb shell am start -a android.intent.action.CALL -d tel:'+mobileNo
    os.system(command)
    
# to send message
def sendMessage(message, mobileNo, name):
    from engine.helper import replace_spaces_with_percent_s, goback, keyEvent, tapEvents, adbInput
    message = replace_spaces_with_percent_s(message)
    mobileNo = replace_spaces_with_percent_s(mobileNo)
    speak("sending message")
    goback(4)
    time.sleep(1)
    keyEvent(3)

    # open sms app
    tapEvents(443.6, 2204.1)
    # start chat
    tapEvents(810.2, 2227.1)
    # search mobile no
    adbInput(mobileNo)
    # tap on name
    tapEvents(414.6, 635.7)
    # tap on input
    tapEvents(390.6, 2260.1)
    # message
    adbInput(message)
    # send
    tapEvents(984, 1348.4)
    speak("Message sent successfully to "+name)

# Gemini API processing function
def process_with_gemini(command):
    """
    Process command using Gemini API
    """
    if not GEMINI_AVAILABLE:
        speak("Gemini API is not configured properly")
        return
        
    prompt = f"""
    You are JARVIS, an AI assistant. Respond to the user query helpfully and concisely.
    
    User: {command}
    JARVIS:
    """
    
    response = gemini_client.ask_gemini(prompt)
    speak(response)