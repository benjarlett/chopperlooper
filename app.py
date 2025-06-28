

import queue
import threading
import time
import logging

import mido
import numpy as np
import sounddevice as sd
import soundfile as sf
from flask import Flask, Response, jsonify, render_template, request, json

# --- Setup ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)


# --- Clock Class ---
class GlobalClock:
    def __init__(self):
        self.bpm = 120.0
        self.tap_times = []
        self.last_tap_time = 0.0
        self.beats_per_bar = 4
        self.current_beat = 1
        self.samples_since_last_beat = 0

    def tap(self, velocity):
        current_time = time.time()
        logging.info(f"Tap received. Current time: {current_time:.2f}, Last tap: {self.last_tap_time:.2f}, Velocity: {velocity}")

        if velocity >= tap_reset_velocity_threshold: # High velocity tap re-arms the tempo
            logging.info("High velocity tap received. Re-arming tap tempo.")
            self.tap_times = []
            self.last_tap_time = current_time
            self.current_beat = 1 # Reset clock to beat 1
            self.samples_since_last_beat = 0
            return

        # If it's the very first tap (after app start or a reset)
        if not self.tap_times and self.last_tap_time == 0.0: # Only for the absolute first tap
            self.last_tap_time = current_time
            logging.info("First tap received, waiting for second.")
            return

        interval = current_time - self.last_tap_time

        # Add interval to tap_times and maintain rolling average
        self.tap_times.append(interval)
        if len(self.tap_times) > 4:
            self.tap_times.pop(0)
        logging.info(f"Added interval: {interval:.4f}s. Tap times: {self.tap_times}")

        # Calculate BPM if we have at least one interval (meaning at least two taps in the current sequence)
        if self.tap_times:
            avg_interval = sum(self.tap_times) / len(self.tap_times)
            if avg_interval > 0:
                self.bpm = 60.0 / avg_interval
                logging.info(f"New BPM: {self.bpm:.2f}")

        self.last_tap_time = current_time


# --- Globals ---
global_clock = GlobalClock()
tap_reset_velocity_threshold = 100 # Default value
audio_stream = None
midi_port_name = None
midi_thread = None
midi_stop_event = threading.Event()
sse_queue = queue.Queue()
loop_data, loop_samplerate = None, None
play_position = 0
playing = False
vu_level = 0
selected_audio_device = None


# --- Audio Functions ---
def list_audio_devices():
    devices = sd.query_devices()
    device_list = []
    for i, device in enumerate(devices):
        if device['max_output_channels'] > 0:
            device_list.append({'id': i, 'name': device['name']})
    return device_list

def audio_callback(outdata, frames, time, status):
    global play_position, playing, vu_level
    global_clock.samples_since_last_beat += frames

    samples_per_beat = (60.0 / global_clock.bpm) * loop_samplerate

    while global_clock.samples_since_last_beat >= samples_per_beat:
        global_clock.current_beat += 1
        if global_clock.current_beat > global_clock.beats_per_bar:
            global_clock.current_beat = 1
        global_clock.samples_since_last_beat -= samples_per_beat

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


# --- MIDI Functions ---
def list_midi_ports():
    return mido.get_input_names()

def midi_thread_func(port_name, stop_event):
    try:
        with mido.open_input(port_name) as port:
            logging.info(f"MIDI port '{port_name}' opened.")
            while not stop_event.is_set():
                for msg in port.iter_pending():
                    if msg.type == 'note_on' and msg.velocity > 0:
                        if msg.note == 41:  # Tap Tempo Note
                            global_clock.tap(msg.velocity)
                        elif msg.note == 48: # Loop Restart Note
                            global playing, play_position
                            playing = True
                            play_position = 0
                            logging.info("Loop restarted by MIDI note 48.")
                        else:
                            message = f"MIDI: note {msg.channel} {msg.note} {msg.velocity}"
                            logging.info(f"Queueing MIDI message: {message}")
                            sse_queue.put(message)
                    elif msg.type == 'control_change':
                        message = f"MIDI: ctl {msg.channel} {msg.control} {msg.value}"
                        logging.info(f"Queueing MIDI message: {message}")
                        sse_queue.put(message)
                time.sleep(0.01)
    except Exception as e:
        logging.error(f"MIDI Error: {e}")
        sse_queue.put(f"MIDI Error: {e}")
    finally:
        logging.info(f"MIDI thread for '{port_name}' stopped.")


# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/devices')
def get_devices():
    return jsonify({'audio': list_audio_devices(), 'midi': list_midi_ports()})

@app.route('/start_engine', methods=['POST'])
def start_engine():
    global audio_stream, loop_data, loop_samplerate
    if audio_stream and audio_stream.active:
        return "Audio engine already running.", 400
    if loop_data is None:
        try:
            data, sr = sf.read('loops/Better With Brushes.wav', dtype='float32')
            loop_data = data if len(data.shape) > 1 else np.column_stack((data, data))
            loop_samplerate = sr
        except Exception as e:
            return f"Could not load loop: {e}", 500
    try:
        audio_stream = sd.OutputStream(
            device=selected_audio_device, samplerate=loop_samplerate,
            channels=loop_data.shape[1], callback=audio_callback)
        audio_stream.start()
        logging.info(f"Audio engine started with device: {selected_audio_device}")
        return 'OK'
    except Exception as e:
        logging.error(f"Failed to start audio stream: {e}")
        return str(e), 500

@app.route('/stop_engine', methods=['POST'])
def stop_engine():
    global audio_stream
    if audio_stream:
        audio_stream.stop()
        audio_stream.close()
        audio_stream = None
        logging.info("Audio engine stopped.")
    return 'OK'

@app.route('/play', methods=['POST'])
def play():
    global playing, play_position
    playing = True
    play_position = 0
    return 'OK'

@app.route('/stop', methods=['POST'])
def stop():
    global playing
    playing = False
    return 'OK'

@app.route('/set_beats_per_bar', methods=['POST'])
def set_beats_per_bar():
    data = request.json
    if 'beats_per_bar' in data:
        try:
            new_beats_per_bar = int(data['beats_per_bar'])
            if new_beats_per_bar > 0:
                global_clock.beats_per_bar = new_beats_per_bar
                global_clock.current_beat = 1 # Reset current beat when beats per bar changes
                global_clock.samples_since_last_beat = 0
                logging.info(f"Beats per bar set to: {new_beats_per_bar}")
                return 'OK'
            else:
                return "Beats per bar must be a positive integer.", 400
        except ValueError:
            return "Invalid beats per bar value.", 400
    return "No beats_per_bar provided.", 400

@app.route('/set_tap_reset_threshold', methods=['POST'])
def set_tap_reset_threshold():
    global tap_reset_velocity_threshold
    data = request.json
    if 'threshold' in data:
        try:
            new_threshold = int(data['threshold'])
            if 0 <= new_threshold <= 127:
                tap_reset_velocity_threshold = new_threshold
                logging.info(f"Tap reset velocity threshold set to: {new_threshold}")
                return 'OK'
            else:
                return "Threshold must be between 0 and 127.", 400
        except ValueError:
            return "Invalid threshold value.", 400
    return "No threshold provided.", 400

@app.route('/select_devices', methods=['POST'])
def select_devices():
    global midi_thread, midi_port_name, selected_audio_device, midi_stop_event
    data = request.json
    if 'midi_device' in data:
        new_midi_port = data['midi_device']
        if midi_thread and midi_thread.is_alive():
            if midi_port_name == new_midi_port:
                return 'OK'
            midi_stop_event.set()
            midi_thread.join()
        midi_port_name = new_midi_port
        midi_stop_event.clear()
        midi_thread = threading.Thread(target=midi_thread_func, args=(midi_port_name, midi_stop_event))
        midi_thread.daemon = True
        midi_thread.start()
    if 'audio_device' in data:
        selected_audio_device = int(data['audio_device'])
        if audio_stream and audio_stream.active:
            sse_queue.put("INFO: Restart audio engine to apply device change.")
    return 'OK'

@app.route('/stream')
def stream():
    def event_stream():
        while True:
            data_packet = {
                'bpm': f'{global_clock.bpm:.2f}',
                'vu': vu_level,
                'current_beat': global_clock.current_beat,
                'beats_per_bar': global_clock.beats_per_bar
            }
            try:
                midi_message = sse_queue.get_nowait()
                data_packet['midi'] = midi_message
            except queue.Empty:
                pass
            yield f"data: {json.dumps(data_packet)}\n\n"
            time.sleep(0.05)
    return Response(event_stream(), mimetype="text/event-stream")


if __name__ == '__main__':
    # Set a default audio device
    available_audio_devices = list_audio_devices()
    if available_audio_devices:
        selected_audio_device = available_audio_devices[0]['id']

    # Set a default MIDI device
    available_midi_ports = list_midi_ports()
    if available_midi_ports:
        midi_port_name = available_midi_ports[0]
        midi_stop_event.clear()
        midi_thread = threading.Thread(target=midi_thread_func, args=(midi_port_name, midi_stop_event))
        midi_thread.daemon = True
        midi_thread.start()
        logging.info(f"Default MIDI device selected and started: {midi_port_name}")

    app.run(debug=True, port=5000, host='0.0.0.0', threaded=True)