# Phase 9.2 — Advanced Voice Interaction

## First implementation increment

This branch introduces a conservative, half-duplex-compatible barge-in path:

- Continuous SpeechRecognition capture keeps the microphone while the user is speaking.
- Porcupine remains paused during continuous capture and command processing.
- Porcupine may take the microphone only while JARVIS is actively speaking.
- A detected "Jarvis" wake word during TTS sets the existing process-shared interrupt event. Kokoro/SAPI5 observes that event and stops playback.
- A wake-word hit outside the TTS window is ignored in continuous mode, so it cannot launch a second UI/listening flow.
- Continuous-listening VAD parameters are configurable and bounded to safe ranges. Dynamic energy adjustment is enabled by default; phrase duration and endpointing remain bounded.

## Configuration

The defaults are documented in `.env.example`:

- `JARVIS_VAD_DYNAMIC_ENERGY`
- `JARVIS_VAD_ADJUSTMENT_DAMPING`
- `JARVIS_VAD_ENERGY_RATIO`
- `JARVIS_VAD_PHRASE_THRESHOLD`
- `JARVIS_VAD_NON_SPEAKING_DURATION`
- `JARVIS_CONTINUOUS_PAUSE_THRESHOLD`
- `JARVIS_CONTINUOUS_PHRASE_LIMIT`

Values are parsed defensively and clamped. Invalid environment values fall back to defaults.

## Current limitations

This increment is **wake-word barge-in**, not unrestricted speech barge-in: the user says "Jarvis" while JARVIS is speaking, then gives the next request after playback stops.

Acoustic echo cancellation is not implemented. Porcupine's wake-word detection is intentionally used for this first increment instead of a raw energy-only interruption trigger, which could mistake JARVIS's own loudspeaker output for user speech. Full-duplex, wake-word-free interruption requires a Windows-compatible capture/playback reference path and tested AEC integration before it can be enabled safely.

## Validation

Run on the project's Windows environment:

```powershell
pytest tests/test_continuous_listening.py -q
pytest -q
```

Then verify manually with a microphone and speakers/headphones:

1. Enable Continuous Listening after authentication.
2. Ask JARVIS a question that produces a long spoken answer.
3. Say "Jarvis" during playback. Confirm speech stops promptly.
4. Give a new command after playback stops. Confirm it is captured once.
5. Confirm ordinary speech or the assistant's own TTS does not launch another UI window.
6. Confirm "stop listening", Settings pause, and wake-word mode still work after continuous mode is disabled.

Automated tests do not replace live Windows device validation. Keep Phase 9.2 open until the complete suite, CI, and manual audio scenarios pass.
