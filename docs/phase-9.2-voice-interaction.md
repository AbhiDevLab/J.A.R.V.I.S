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

## Acoustic echo cancellation investigation (2026-11-08)

### Candidate evaluation

The strongest low-friction candidate found so far is [Echoff](https://github.com/KoljaB/echoff) (PyPI `echoff==0.3.0`). It provides Windows 10/11 WASAPI loopback-reference and microphone capture, timestamp alignment, and WebRTC AEC processing. The release is explicitly marked **alpha**, requires Python 3.11+, and has hardware-dependent capture behavior. It is promising for a controlled prototype, not yet a production dependency.

A second option is [pywebrtc-audio](https://github.com/strands-labs/pywebrtc-audio) (`0.2.0`, beta), which exposes the WebRTC audio-processing module. It can perform AEC when supplied with correctly aligned near-end microphone and far-end playback reference frames. It does not by itself solve capture/clock synchronization for two independently clocked Windows devices.

Windows also exposes an AEC APO framework, but this depends on the capture endpoint's audio driver/APO support and the selected render endpoint. It is not a universal app-level switch that JARVIS can assume is present.

### Architecture required before integration

AEC must receive the actual audio rendered by JARVIS as its far-end reference and the microphone as its near-end signal. The streams must be timestamp-aligned. Therefore, adding an AEC DSP call after the existing SpeechRecognition capture would be insufficient: JARVIS would still have opened the microphone without an aligned playback reference.

The intended integration should use one process-local capture owner/broker:

1. Own the microphone and speaker-loopback capture streams in one component.
2. Align reference and microphone frames and feed them to WebRTC AEC.
3. Send only the cleaned microphone frames to VAD/STT, while preserving the original stream for diagnostics only.
4. Reuse the same cleaned capture for barge-in speech detection and transcription, avoiding a second microphone reader.
5. Keep the existing half-duplex path as a fallback when AEC initialization fails or the endpoint cannot provide a valid reference.

### Decision

Do **not** add Echoff or pywebrtc-audio to the main requirements yet. Before integration, test on the target Windows PC with the actual selected microphone and speaker/headphone endpoints. Measure echo reduction while JARVIS speaks, confirm that the user's near-end speech remains intelligible, test output-device switching, and verify startup/shutdown/recovery. Keep AEC opt-in until those tests pass.

This investigation closes the research task only; AEC integration, arbitrary-speech barge-in, and full-duplex capture remain incomplete.

## Isolated Windows AEC hardware probe (Echoff 0.3.0)

The probe dependency is intentionally isolated from the normal application dependencies. It must not be imported by `run.py`, `engine/command.py`, or the default speech path before the target hardware has passed the acceptance checks below.

OpenJarvis provides a useful architectural reference: its Faster-Whisper speech backend accepts audio data independently of device capture. J.A.R.V.I.S should preserve the same separation when AEC is integrated: capture and clean the audio first, then hand cleaned audio to the existing STT path. Do not create a second microphone reader or feed unsynchronized microphone and speaker streams into the AEC processor.

### Install the optional probe

Run from the repository root in the existing Python 3.11 `envjarvis` environment:

```powershell
python -m pip install -r requirements-aec-probe.txt
python -m echoff --help
```

The normal `requirements.txt` remains unchanged. Echoff 0.3.0 is alpha software and requires Python 3.11 or newer.

### Discover Windows audio endpoints

```powershell
python -m echoff devices
```

Record the selected microphone and render/output device names. Connect the same headphones/speakers and microphone normally used with J.A.R.V.I.S. Do not assume the default Windows endpoint is the endpoint J.A.R.V.I.S actually uses.

### Capture a raw-versus-AEC comparison

```powershell
python -m echoff record --duration 25
```

During the capture, use a repeatable sequence:

1. Play continuous spoken audio through the selected output device for at least ten seconds while remaining silent. This creates a far-end-only interval for checking speaker leakage.
2. Stop playback and speak several normal commands into the selected microphone. This checks that AEC does not suppress the user's own speech.
3. Play output audio again and speak over it. This checks the combined case required for interruption.

For a repeatable far-end-only stimulus, first confirm that `ffplay -version` works, then use a known speech WAV:

```powershell
python -m echoff record --play-wav C:\\audio\\known-speech.wav --repetitions 3
```

Use an actual local WAV path. Keep the microphone silent during the stimulus portion. The Echoff CLI prints the artifact directory. Preserve it outside the repository and inspect at least:

- `computer_audio.wav` — render-device reference.
- `microphone_raw.wav` — microphone before AEC.
- `microphone_aec.wav` — microphone after AEC.

### Acceptance criteria

Do not integrate AEC into the J.A.R.V.I.S runtime unless all of these are satisfied on the target Windows PC:

- The capture status is `completed`, not `incomplete`, `degraded`, or `failed`.
- The three primary tracks have matching duration/frame counts.
- No source failure, unsafe overflow, or hard discontinuity is reported.
- With output audio and no user speech, the AEC track audibly reduces speaker leakage compared with the raw microphone track.
- With user speech and no output audio, the user's words remain intelligible in the AEC track.
- With simultaneous user speech and output audio, the user's words remain intelligible while speaker leakage is reduced.
- The capture can start, stop, and recover after changing the Windows input/output device.
- Repeat the test with the actual microphone/speaker placement and volume used during J.A.R.V.I.S sessions.

Echoff's `echo_path_ready` indicator is a readiness heuristic, not proof that all echo is removed. Listen to the raw and AEC tracks; do not accept a numeric suppression score alone.

### Privacy and repository hygiene

The capture artifacts may contain private microphone speech and all computer audio routed through the selected output. Keep the artifacts local, do not commit them, and inspect `git status --short` before any push. Do not upload recordings unless their contents have been reviewed and sharing is intentional.

### Runtime integration gate

Until the hardware acceptance criteria pass:

- Keep the current half-duplex listener and wake-word-only TTS interruption as the production behavior.
- Do not add Echoff to `requirements.txt`.
- Do not enable wake-word-free barge-in or full-duplex capture.
- Do not allow Porcupine, SpeechRecognition, or a future AEC capture service to open competing microphone streams.

After acceptance, the implementation should use one capture owner for both the microphone and render-loopback reference, dispatch bounded cleaned-audio frames to VAD/STT and the interruption detector, and retain the current half-duplex path as a safe fallback. AEC must be opt-in until the full Windows lifecycle and false-interruption tests pass.

