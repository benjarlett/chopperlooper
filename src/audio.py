
import sounddevice as sd
import numpy as np
import soundfile as sf
import logging
import json

# Globals for audio module
loop_data = None
loop_samplerate = None
loop_beats = None
loop_bars = None
play_position = 0
playing = False
vu_level = 0
audio_stream = None
selected_audio_device = None

# Load loop metadata on module import
try:
    loop_metadata_path = 'loops/Better With Brushes.json'
    with open(loop_metadata_path, 'r') as f:
        metadata = json.load(f)
    loop_beats = metadata.get('beats', 8)
    loop_bars = metadata.get('bars', 2)
    logging.info(f"Audio module initialized with loop_beats={loop_beats}, loop_bars={loop_bars}")
except Exception as e:
    logging.error(f"Error loading loop metadata on import: {e}")
    # Set default values if loading fails
    loop_beats = 8
    loop_bars = 2

def list_audio_devices():
    devices = sd.query_devices()
    device_list = []
    for i, device in enumerate(devices):
        if device['max_output_channels'] > 0:
            device_list.append({'id': i, 'name': device['name']})
    return device_list

def audio_callback(outdata, frames, time, status, global_clock):
    global play_position, playing, vu_level
    global_clock.samples_since_last_beat += frames

    # Ensure loop_samplerate is valid before calculating samples_per_beat
    if loop_samplerate is None or loop_samplerate == 0:
        logging.warning("loop_samplerate is not set or is zero. Cannot calculate samples_per_beat.")
        return # Exit early if samplerate is invalid

    samples_per_beat = (60.0 / global_clock.bpm) * loop_samplerate

    logging.debug(f"Audio Callback: frames={frames}, current_beat={global_clock.current_beat}, samples_since_last_beat={global_clock.samples_since_last_beat}, samples_per_beat={samples_per_beat:.2f}, BPM={global_clock.bpm:.2f}, Samplerate={loop_samplerate}, Playing={playing}")

    while global_clock.samples_since_last_beat >= samples_per_beat:
        logging.debug(f"  Advancing beat: current_beat={global_clock.current_beat} -> {global_clock.current_beat + 1}, samples_since_last_beat={global_clock.samples_since_last_beat} -> {global_clock.samples_since_last_beat - samples_per_beat}")
        global_clock.current_beat += 1
        if global_clock.current_beat > global_clock.beats_per_bar:
            global_clock.current_beat = 1
        global_clock.samples_since_last_beat -= samples_per_beat
        logging.info(f"Beat changed to: {global_clock.current_beat} at BPM {global_clock.bpm:.2f}")

    if playing and loop_data is not None:
        remaining_frames = frames
        buffer_offset = 0
        while remaining_frames > 0:
            if play_position >= len(loop_data):
                play_position = 0  # Loop back to the start
            
            chunk_size = min(remaining_frames, len(loop_data) - play_position)
            chunk = loop_data[play_position : play_position + chunk_size]
            
            outdata[buffer_offset : buffer_offset + chunk_size] = chunk
            play_position += chunk_size
            remaining_frames -= chunk_size
            buffer_offset += chunk_size

        vu_level = np.sqrt(np.mean(outdata**2)) * 250
    else:
        outdata.fill(0)
        vu_level = 0

def start_audio_engine(global_clock):
    global audio_stream, loop_data, loop_samplerate
    if audio_stream and audio_stream.active:
        return "Audio engine already running.", 400
    if loop_data is None:
        try:
            data, sr = sf.read('loops/Better With Brushes.wav', dtype='float32')
            loop_data = data if len(data.shape) > 1 else np.column_stack((data, data))
            loop_samplerate = sr
            global_clock.set_beats_per_bar(loop_beats / loop_bars) # Update global clock with loop's beats per bar
        except Exception as e:
            return f"Could not load loop or metadata: {e}", 500
    try:
        # Reset beat tracking when starting engine
        global_clock.samples_since_last_beat = 0
        global_clock.current_beat = 1

        audio_stream = sd.OutputStream(
            device=selected_audio_device, samplerate=loop_samplerate,
            channels=loop_data.shape[1], callback=lambda *args: audio_callback(*args, global_clock=global_clock))
        audio_stream.start()
        logging.info(f"Audio engine started with device: {selected_audio_device}")
        return 'OK'
    except Exception as e:
        logging.error(f"Failed to start audio stream: {e}")
        return str(e), 500

def stop_audio_engine():
    global audio_stream
    if audio_stream:
        audio_stream.stop()
        audio_stream.close()
        audio_stream = None
        logging.info("Audio engine stopped.")
    return 'OK'

def play_loop(global_clock):
    global playing, play_position
    playing = True
    play_position = 0
    global_clock.samples_since_last_beat = 0 # Reset samples_since_last_beat when loop starts/restarts
    return 'OK'

def stop_loop(global_clock):
    global playing
    playing = False
    return 'OK'

def get_vu_level():
    return float(vu_level)

def get_divisors(n):
    divs = []
    for i in range(1, int(n**0.5) + 1):
        if n % i == 0:
            divs.append(i)
            if i * i != n:
                divs.append(n // i)
    divs.sort()
    return divs

def set_loop_bars(bars, global_clock):
    global loop_bars
    if bars > 0 and loop_beats % bars == 0:
        loop_bars = bars
        global_clock.set_beats_per_bar(loop_beats / loop_bars)
        logging.info(f"Loop bars set to: {loop_bars}")
        return True
    return False

def set_loop_beats(beats, global_clock):
    global loop_beats
    if beats > 0:
        loop_beats = beats
        # Re-validate loop_bars to ensure it's still a divisor of new loop_beats
        if loop_beats % loop_bars != 0:
            loop_bars = get_divisors(loop_beats)[-1] # Default to largest divisor
            logging.warning(f"Loop bars adjusted to {loop_bars} as it was no longer a divisor of {loop_beats}.")
        global_clock.set_beats_per_bar(loop_beats / loop_bars)
        logging.info(f"Loop beats set to: {loop_beats}")
        return True
    return False

def set_audio_device(device_id):
    global selected_audio_device
    selected_audio_device = device_id
    logging.info(f"Audio device set to: {selected_audio_device}")

