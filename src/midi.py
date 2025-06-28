
import mido
import threading
import time
import logging
import queue

# Globals for MIDI module
midi_port_name = None
midi_thread = None
midi_stop_event = threading.Event()
sse_queue = None # This will be set by the main app

def list_midi_ports():
    return mido.get_input_names()

def midi_thread_func(port_name, stop_event, global_clock, sse_q):
    global sse_queue
    sse_queue = sse_q # Set the global sse_queue for this module
    try:
        with mido.open_input(port_name) as port:
            logging.info(f"MIDI port '{port_name}' opened.")
            while not stop_event.is_set():
                for msg in port.iter_pending():
                    if msg.type == 'note_on' and msg.velocity > 0:
                        if msg.note == 41:  # Tap Tempo Note
                            global_clock.tap(msg.velocity)
                        elif msg.note == 48: # Loop Restart Note
                            # This needs to trigger a function in audio.py or engine.py
                            # For now, we'll just log it and send to SSE
                            logging.info("Loop restart MIDI note (48) received.")
                            sse_queue.put("MIDI: Loop Restart (Note 48)")
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

def start_midi_listener(port_name, global_clock, sse_q):
    global midi_thread, midi_port_name, midi_stop_event
    if midi_thread and midi_thread.is_alive():
        if midi_port_name == port_name:
            return # Already listening to this port
        midi_stop_event.set()
        midi_thread.join()

    midi_port_name = port_name
    midi_stop_event.clear()
    midi_thread = threading.Thread(target=midi_thread_func, args=(port_name, midi_stop_event, global_clock, sse_q))
    midi_thread.daemon = True
    midi_thread.start()
    logging.info(f"MIDI listener started for: {port_name}")

def stop_midi_listener():
    global midi_thread, midi_stop_event
    if midi_thread and midi_thread.is_alive():
        midi_stop_event.set()
        midi_thread.join()
        logging.info("MIDI listener stopped.")

