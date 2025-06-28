

import queue
import threading
import time
import logging

from flask import Flask, Response, jsonify, render_template, request, json

from src.clock import GlobalClock
from src import audio
from src import midi

# --- Setup ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__, template_folder='templates')

# --- Globals ---
global_clock = GlobalClock()
sse_queue = queue.Queue()


# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/devices')
def get_devices():
    return jsonify({'audio': audio.list_audio_devices(), 'midi': midi.list_midi_ports()})

@app.route('/start_engine', methods=['POST'])
def start_engine():
    return audio.start_audio_engine(global_clock)

@app.route('/stop_engine', methods=['POST'])
def stop_engine():
    return audio.stop_audio_engine()

@app.route('/play', methods=['POST'])
def play():
    return audio.play_loop(global_clock)

@app.route('/stop', methods=['POST'])
def stop():
    return audio.stop_loop(global_clock)

@app.route('/restart_loop', methods=['POST'])
def restart_loop():
    audio.play_loop(global_clock) # This function already resets play_position to 0
    global_clock.current_beat = 1 # Explicitly reset current beat
    global_clock.tap(velocity=global_clock.tap_reset_velocity_threshold) # Simulate a high velocity tap to re-arm
    sse_queue.put("MIDI: Loop Restart (UI Button)") # For display on MIDI log
    return 'OK'

@app.route('/tap', methods=['POST'])
def tap_tempo():
    global_clock.tap(velocity=global_clock.tap_reset_velocity_threshold - 1) # Simulate a tap below threshold
    return 'OK'

@app.route('/set_loop_bars', methods=['POST'])
def set_loop_bars():
    data = request.json
    if 'bars' in data:
        try:
            new_bars = int(data['bars'])
            if audio.set_loop_bars(new_bars, global_clock):
                return 'OK'
            else:
                return "Loop bars must be a positive integer and a divisor of loop beats.", 400
        except ValueError:
            return "Invalid loop bars value.", 400
    return "No loop bars provided.", 400

@app.route('/set_loop_beats', methods=['POST'])
def set_loop_beats():
    data = request.json
    if 'beats' in data:
        try:
            new_beats = int(data['beats'])
            if audio.set_loop_beats(new_beats, global_clock):
                return 'OK'
            else:
                return "Loop beats must be a positive integer.", 400
        except ValueError:
            return "Invalid loop beats value.", 400
    return "No loop beats provided.", 400

@app.route('/set_tap_reset_threshold', methods=['POST'])
def set_tap_reset_threshold():
    data = request.json
    if 'threshold' in data:
        try:
            new_threshold = int(data['threshold'])
            if 0 <= new_threshold <= 127:
                global_clock.set_tap_reset_threshold(new_threshold)
                return 'OK'
            else:
                return "Threshold must be between 0 and 127.", 400
        except ValueError:
            return "Invalid threshold value.", 400
    return "No threshold provided.", 400

@app.route('/get_tap_reset_threshold')
def get_tap_reset_threshold():
    return jsonify({'threshold': global_clock.tap_reset_velocity_threshold})

@app.route('/get_loop_metadata')
def get_loop_metadata():
    return jsonify({'beats': audio.loop_beats, 'bars': audio.loop_bars})

@app.route('/select_devices', methods=['POST'])
def select_devices():
    data = request.json
    if 'midi_device' in data:
        midi.start_midi_listener(data['midi_device'], global_clock, sse_queue)
    if 'audio_device' in data:
        audio.set_audio_device(int(data['audio_device']))
    return 'OK'

@app.route('/stream')
def stream():
    def event_stream():
        while True:
            data_packet = {
                'bpm': f'{global_clock.bpm:.2f}',
                'vu': audio.get_vu_level(),
                'current_beat': global_clock.current_beat,
                'beats_per_bar': global_clock.get_beats_per_bar()
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
    available_audio_devices = audio.list_audio_devices()
    if available_audio_devices:
        audio.set_audio_device(available_audio_devices[0]['id'])

    # Set a default MIDI device
    available_midi_ports = midi.list_midi_ports()
    if available_midi_ports:
        midi.start_midi_listener(available_midi_ports[0], global_clock, sse_queue)

    app.run(debug=True, port=5000, host='0.0.0.0', threaded=True)
