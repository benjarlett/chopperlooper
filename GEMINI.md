# chopper Looper Specification

## 🔹 1. Chop-Level Design
A single chop playback consists of a division of the origional loop played back at it's origional speed (unless defined to playback faster)
- **Start position (sample offset)**
- **Division (Length of a chop, which is a division of a beat, 1, 2, 4, 8, 16 32)**
- **Transpose (playback speed if you want to pitch up/down defined in semitones, default 0, can be up or down)**
- **Tune** (like transpose but for fine tuning, defined in cents)
- **Overlap Strategy** Each chop has a configurable overlap (default 100%). If max overlap (200%) it will continue playing until the end of the next chop, if 50% it will Have faded out half way through it's length.
- **Window** If Window selected -- apply a simple envelope (e.g., Hann window) to each chop, diffferent windows can be selected (e.g. hanning)
- **Fade Start/Stop** If env selected - length in ms of the fade in and fade out at the start/end of the chop, defined separately

**Recommendations:**
- Use **numpy-based buffers** for memory-efficient chopping.
- Apply a simple envelope (e.g., Hann window) to each chop.
- Trigger chops via:
  - A scheduler (time-based, tempo-locked),
  - Each voice can be muted or paused. Scheduler is only active while the voice is unmuted and triggered..

---

## 🔹 2. Voice Model (Single Loop Playback)
A `Voice` handles:
- One audio buffer (loop)
- Chop playback scheduling
- Pitch shift and time stretch
- Volume, panning, filters (optional)
- Each loop may optionally be routed to a specific JACK output channel (e.g., for external mixing or FX). Default is stereo mix.
- Playback mode options: loop, one-shot, retrigger.
- The voice will need to be told how many beats a loop contains. Better With Brushes.wav included in the loops folder is 8 beats long or 2 bars in 4/4 - This is the default loop, but more loops can be loaded, and their properties saved in a loops.json file for recall.

### Control Parameters:
- `loop_id`, `file_path`
- `bpm`, `beat_length_ms`
- `start_beat_offset`, `chop_length`
- `pitch_shift_semitones`
- `tempo_sync: bool`

---

## 🔹 3. Multi-Voice Engine (Song Engine)
Manages multiple `Voice` objects:
- Global tempo (from MIDI tap)
- Beats per bar (i.e quazi time signature so that 4/4 time and 3/4 and 5/4 are possible)
- Shared clock (quantized triggers)
- Per-loop offsets
- Mute/solo per voice
- Crossfade/sync control

```
[Song] --> [Voice1, Voice2, Voice3...]
         ↳ [LoopA] [LoopB] [LoopC]
         ↳ Sync offset, BPM, Key
```

---

## 🔹 4. Loop Metadata
Stored as JSON or embedded in filename.

```json
{
  "filename": "Better With Brushes.wav",
  "path": "/loops/drums/",
  "original_key": "C",
  "transpose": "D",
  "tune": "+10",
  "beats": 8,
  "beats_per_bar": 4,
  "bars": 2,
  "tags": ["drums", "jazz", "bouncy"]
}
```

---

## 🔹 5. Song Definition
```json
{
  "name": "Jah is the Light",
  "global_bpm": 72,
  "loops": [
    {"file": "loop1.wav", "channel": 0, "start_offset_beats": 0},
    {"file": "loop2.wav", "channel": 1, "start_offset_beats": 4}
  ]
}
```

---

## 🔹 6. Control Model
- Global MIDI Tap Tempo → Sets BPM
- Per-loop control:
  - Trigger/mute (MIDI CC/note)
  - Pitch shift (encoder or automation)
  - Offset (delayed loop start by X beats)
  - Each loop channel can be toggled by a velocity of above 80 assigned note/channel (configurable threshold). Softer velocities are counted as tap tempo. I will need to use a better keyboard as the current one only outputs a fixed 100 velocity.

---

## 🔹 7. LLM Prompt Template
Use to scaffold code with LLM tools:

> Write a Python class `Chop` that reads from a numpy buffer and plays overlapping chops with Hann envelopes. Then a `Voice` class that uses a `ChopScheduler` to control rate and pitch. Ensure it supports dynamic BPM input and audio playback with `sounddevice`.

---

## ✅ Summary
Benefits:
- Headless + MIDI/web control
- Efficient (numpy/sounddevice)
- Portable (Pi 3/5, Mac, embedded Linux)
- `metadata-driven`

## 🔹 8. Platform and Hardware Context

### Current Development Setup:
- **Target Runtime**: Raspberry Pi 3 Model B with Pisound HAT
- **Operating System**: Raspbian GNU/Linux 11 (Bullseye) with JACK1 and ALSA
- **Audio Interface**: Pisound (card 1)
- **MIDI Input**: USB MIDI Keyboard (during development)
- **Control Computer**: macOS (for development, SSH access, browser control)
- Real-time kernel (optional)
- JACK buffer tuning (essential)
- Consider Pi 5 or other SBCs

### Future Portability Goals:
- Should support moving to other hardware (e.g., Raspberry Pi 5, or embedded Linux platforms with ALSA/JACK).
- Code should be cleanly separated from platform-specific audio/MIDI drivers to allow reuse.

---

## 🔹 9. Web Interface

### UI Features:
- Tap tempo button
- Live BPM display
- Volume control slider
- Loop/channel playback status
- Toggle/mute/start/stop per channel
- Settings form to adjust:
  - Loop assignments
  - Window/Env mode with Fade in/out
  - Playback key
  - Chop division and Overlap

### Backend Requirements:
- Flask or FastAPI server with REST + Server-Sent Events (SSE)
- Expose endpoints for:
  - `/tap` → Receives tap input
  - `/bpm_stream` → Sends live BPM updates
  - `/play`, `/stop`, `/volume`, `/set_port`, `/set_output_device`
  - `/loop_config`, `/save_song`, `/load_song`

---

## 🔹 10. MIDI Mapping

### Tempo Input:
- MIDI Note On triggers from a defined **channel** and **note number**
- This tempo tap input replaces manual web tap in performance mode
- Configurable per user preference

```json
{
  "tempo_source": {
    "type": "midi_note",
    "channel": 10,
    "note": 37
  }
}
```

### Double Tap Detection:
- Double tap = two taps within 125ms (configurable)
- Used to start/stop loops per channel
- Mimics a "MIDI switch pedal" behavior
- Optionally distinguish by note velocity

---

## 🔹 11. Configuration and Settings

All runtime options should be editable via:
- Web UI settings page
- JSON file (`settings.json`)
- Live reload without restart

```json
{
  "default_port": "USB MIDI keyboard:USB MIDI keyboard MIDI 1 24:0",
  "default_output_device": 5,
  "tempo_input": {
    "mode": "midi_note",
    "channel": 10,
    "note": 37
  },
  "chop_defaults": {
    "division": 8,
    "transpose": 0,
    "tune": 0,
    "overlap": 100
  }
}
```
---

---

## 🔹 12. Advanced Considerations

### 2. Clock & Sync Design
- A global clock is derived from a dedicated MIDI note tap (e.g., a pad on the first MIDI channel).
- Loops can be quantized to start on beats or bars (user-selectable).
- Loops can be resynced mid-play using another MIDI pad.
- Loops can be reversed (played from end to beginning)
- Chops can be reversed (played the opposite way from loops)

### 3. Latency Consideration
- MIDI tap input latency should be minimal.
- Buffer sizes and JACK configuration should aim for low latency (details TBD).
- Chops can use "pre-roll" — buffering slightly before playback begins to improve timing.

### 5. Audio File Constraints
- Accepts WAV, FLAC, MP3.
- Optionally cache files in the target format for performance.
- Project-wide setting for sample rate and bit depth (e.g., 16bit/48kHz or 8bit/24kHz).
- Max file duration: 64 bars.
- File metadata (tempo, key, bars) must be entered via web UI.
- File upload via web UI is desirable but optional.

### 6. Web UI Notes
- Per-loop controls: Volume, Key, Play/Stop, Sync Mode.
- Global BPM indicator.
- Loop browser or file selector.
- Global volume.
- Chopper engine controls:
  - Division, envelope shape.
- Settings page:
  - CPU frequency, temperature, performance monitoring.
  - Default settings editor.

### 7. Performance Targets
- Target: 4 voices under 80% CPU usage on Pi 3B.
- Include CPU usage indicator if feasible.

### 8. Logging & Debugging
- Logging levels: off, info, warning, error (user selectable).
- Global beat counter display.
- Loop start feedback (e.g., "Loop 1 started at beat 17").
- Visual debugging: VU meters, loop playback state.

### 9. Modular Code Goals
- A clean separation between core audio engine, web UI, and MIDI input.
- Main engine logic in an `Engine` class or module.

### 10. Dev/Prod Modes
- **Dev mode**:
  - Verbose logging
  - Test loops available
  - Hot-reload UI

- **Prod mode**:
  - Auto-start with `boot.sh`
  - Watchdog for process recovery
  - Optimized for CPU use
---

## 🔹 13. Storage Model and Metadata

### Hybrid Storage Strategy
This project uses a **hybrid approach** combining JSON files and future database support:

- ✅ **Current Approach (JSON)**:
  - Transparent, human-readable files
  - Easy to version control
  - Each loop and song has a standalone `.json` file
  - Recommended for prototyping, small- to medium-scale use

- 🧠 **Future Option (Database)**:
  - SQLite or similar embedded database
  - Useful for organizing large loop libraries, search/filtering, or multiple users
  - Code should abstract storage layer to support both file and DB backends

### Folder Layout Example
```
/loops/
  /drums/Better with Brushes.wav
  /drums/Better with Brushes.json
/songs/
  jah_is_the_light.json
/config/
  settings.json
```
---

## 🔹 15. Dependencies in Use (subject to change)

These are the currently installed or expected packages on the development system:

- Python 3.9
- `mido==1.2.9` — MIDI I/O
- `python-rtmidi==1.4.7` — Backend for mido
- `sounddevice==0.5.2` — Real-time audio playback
- `numpy` — Array manipulation and audio buffers
- `Flask` or `FastAPI` — Web UI server (TBD or switchable)
- `JACK1` and `ALSA` — Audio backend on Raspberry Pi
- Coreaudio — Audio backend on Mac (for development)

Dependencies may evolve, especially if:
- WebSocket replaces SSE
- SQLite is introduced
- GUI styling libraries or waveform visualization is added

---

## 🔹 16. License

License: TBD (likely MIT or GPLv3 depending on contribution and future distribution plans).
---

## 🔹 17. Development Plan & Technical Considerations

### Development Phases
This project will be developed incrementally for clarity and testability:

1. **Phase 1** – Single voice, chopped playback from static file
2. **Phase 2** – Add tempo-based chop scheduling (tap tempo → BPM)
3. **Phase 3** – Multi-voice architecture with offset support
4. **Phase 4** – MIDI input mapping (tempo + loop control)
5. **Phase 5** – Web UI for live status + control
6. **Phase 6** – Performance tuning, debugging tools, visual UI/UX polish

---

### State Management Across Control Surfaces
- The **core engine** should maintain authoritative playback state.
- Web UI and MIDI inputs send **events**, not direct state changes.
- Use a **message/event bus** or **reactive observer pattern** to keep UI and engine in sync.
- Prevent feedback loops (e.g., MIDI updates UI, which loops back).

---


### Latency Budget
- Target **<30ms** total latency from MIDI trigger to chop output
- Account for JACK buffer size (64–128 samples)
- Chop scheduler should **pre-roll** and align to callback boundaries

---

### Performance & Audio Backend Notes
- `sounddevice`: simple and effective for early dev
- `aubio`: consider for future audio analysis (onset, BPM detection)
- `numba` or C extension: explore for chop render loop if CPU-limited
- `pyaudio`: optional alternative for direct ALSA if needed

---

## 🔹 18. Gemini Feedback Integration

### Strengths Confirmed
- Clear modular design (Chop, Voice, Engine)
- Robust platform awareness and performance targets
- Numpy for buffers and hybrid JSON/database model
- Strong attention to real-time audio challenges

### Enhancements Integrated

#### Envelope Variety (Future Feature)
Offer configurable window functions (`hann`, `hamming`, `blackman`) via `envelope_shape` in chop settings.

#### Optional Filters
- If implemented, use simple low-pass/high-pass IIR filters.
- Avoid complex filters in early versions to preserve CPU.

#### Clock Precision and Scheduling
- Use sample-frame-accurate clock for internal timing.
- Avoid blocking ops inside sounddevice callback.
- Pre-roll chop and align to high-resolution internal time.

#### Memory & GC Management
- Implement chop pooling to avoid real-time allocation spikes.
- Reuse numpy buffers where possible.

#### Error Handling
- Catch and log errors from audio/MIDI/file handling.
- Always fail gracefully (e.g., skip loop, log issue, continue playback).

#### Live Config Reload
- Detect `settings.json` changes at runtime.
- Apply settings in a thread-safe way (e.g., enqueue config update events).

#### Chop Parameter UX
- Visualize overlap %, and scheduling rate.

#### Extensible Granular Modes
- Use a Strategy pattern: define separate `ChopScheduler` or `ChopStrategy` classes.
- Keeps the core `Voice` class clean and easy to extend.

#### JACK Config Guidance
- Start with moderate buffer sizes (e.g., 256–512 samples).
- Adjust for lowest stable latency on your system.

#### Web UI Consideration
- Flask: simpler, good for MVP.
- FastAPI: async support for scaling (e.g., live updates + control).
- SSE for status; REST for control.

#### Advanced MIDI Mapping
- Support velocity-sensitive tap (later feature).
- All timing thresholds (e.g., double tap detection) must be configurable.

#### Loop Metadata Enhancements
- Preserve `original_bpm` in metadata.

#### Performance Watchdog
- Monitor CPU/memory usage, can be switched off with toggle, default off.

### Implementation Notes
- Plan Phase 1 with 2 voices max, measure CPU usage.
- Upgrade to Pi 5 or real-time kernel if dropouts persist under expected load.


## 🔹 19. Mobile App Expansion Path (Future)

This section outlines a potential future port of the browser-based control interface to a dedicated iOS app. The iPhone becomes a **performance-focused remote control** for the Pi-based engine.

### ❓ Why
- More responsive control during live use
- Portable monitoring while walking the venue
- Enables performance without needing a browser or desktop device

### 🧰 Architecture Compatibility
The current system already uses:
- **HTTP REST endpoints** (`/tap`, `/play`, `/stop`, etc.)
- **Server-Sent Events (SSE)** for live updates (`/bpm_stream`, `/vu_stream`)

This is ideal for mobile interaction and can be used by:
- **React Native** (`fetch()`, EventSource)
- **Swift / SwiftUI** (using `URLSession`, Combine)
- **Progressive Web App (PWA)** (quick deployment)

### 📱 Potential App Features
- Tap tempo
- Play/stop toggle
- Volume + output control
- MIDI port selection
- Live BPM/VU display
- System status readout

### 🔗 Communication Mapping

| Action        | Method | Endpoint             | Payload                 |
|---------------|--------|----------------------|--------------------------|
| Tap Tempo     | POST   | `/tap`               | –                        |
| Play/Stop     | POST   | `/play`, `/stop`     | –                        |
| Volume        | POST   | `/volume`            | `{ volume: Float }`      |
| Output Select | POST   | `/set_output_device` | `{ device_index: Int }`  |
| MIDI Port     | POST   | `/set_port`          | `{ port: String }`       |
| Status Fetch  | GET    | `/system_status`     | –                        |
| BPM/VU Meter  | SSE    | `/bpm_stream`, `/vu_stream` | –                |

### 🚀 Development Path
1. Scaffold React Native app (preferred: Expo)
2. Reuse `main.js` logic for endpoint calls
3. Test live connection to Pi
4. Iterate UI for touch UX
5. Explore Swift/SwiftUI version if deeper iOS features (Bluetooth MIDI) are desired

### 🌐 Enhancements
- Bonjour/ZeroConf for Pi discovery (`patchbox.local`)
- Optional auth system if used beyond local network
- Optimize for big touch targets, dark mode