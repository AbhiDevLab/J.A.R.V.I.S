"""Installer script to add voice authentication dependencies on Windows.

Run this inside the Python environment you want to use for JARVIS (e.g., envjarvis):

    python tools/install_voice_deps.py

What it does:
- Installs SpeechRecognition via pip
- Installs pipwin via pip and uses it to install PyAudio (Windows binary)
- If pipwin is unavailable, it attempts a fallback `pip install pyaudio`.

This script is idempotent and prints actions and errors.
"""
import subprocess
import sys
import shutil

def run(cmd, check=True):
    print('>',' '.join(cmd))
    return subprocess.run(cmd, check=check)

def main():
    # ensure pip is available
    python = sys.executable
    print('Using Python:', python)

    # install SpeechRecognition
    try:
        run([python, '-m', 'pip', 'install', 'SpeechRecognition'])
    except subprocess.CalledProcessError:
        print('Failed installing SpeechRecognition')
        return 1

    # install pipwin to fetch a binary PyAudio on Windows
    try:
        run([python, '-m', 'pip', 'install', 'pipwin'])
    except subprocess.CalledProcessError:
        print('Failed installing pipwin; will try direct PyAudio install')

    # prefer pipwin for PyAudio on Windows
    pipwin = shutil.which('pipwin')
    if pipwin:
        try:
            run([python, '-m', 'pipwin', 'install', 'pyaudio'])
        except subprocess.CalledProcessError:
            print('pipwin install failed, trying pip install pyaudio')
            try:
                run([python, '-m', 'pip', 'install', 'pyaudio'])
            except subprocess.CalledProcessError:
                print('Failed to install PyAudio via pip as well')
                return 1
    else:
        # Try pip install as a fallback
        try:
            run([python, '-m', 'pip', 'install', 'pyaudio'])
        except subprocess.CalledProcessError:
            print('pip install pyaudio failed. On Windows try:')
            print('  python -m pip install pipwin')
            print('  python -m pipwin install pyaudio')
            return 1

    print('\nVoice dependencies installed. You can now run JARVIS and use voice fallback.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
