
import time
import logging
import threading

class GlobalClock:
    def __init__(self):
        self.bpm = 120.0
        self.tap_times = []
        self.last_tap_time = 0.0
        self.beats_per_bar = 4
        self.current_beat = 1
        self.samples_since_last_beat = 0
        self.tap_reset_velocity_threshold = 100 # Default value

    def tap(self, velocity):
        current_time = time.time()
        logging.info(f"Tap received. Current time: {current_time:.2f}, Last tap: {self.last_tap_time:.2f}, Velocity: {velocity}")

        if velocity >= self.tap_reset_velocity_threshold: # High velocity tap re-arms the tempo
            logging.info("High velocity tap received. Re-arming tap tempo.")
            self.tap_times = []
            self.last_tap_time = 0.0 # Reset last_tap_time on re-arm
            self.current_beat = 1 # Reset clock to beat 1
            self.samples_since_last_beat = 0
            return

        # If tap_times is empty, this is the first tap in a new sequence (after re-arm or initial start)
        if not self.tap_times:
            self.last_tap_time = current_time
            logging.info("First tap in new sequence received, waiting for second.")
            # Do not return here, allow interval calculation for the second tap

        interval = current_time - self.last_tap_time

        # Add interval to tap_times and maintain rolling average
        self.tap_times.append(interval)
        if len(self.tap_times) > 4:
            self.tap_times.pop(0)
        logging.info(f"Added interval: {interval:.4f}s. Tap times: {self.tap_times}")

        # Calculate BPM if we have at least one interval (meaning at least two taps in the current sequence)
        if len(self.tap_times) >= 1: # We have at least one interval
            avg_interval = sum(self.tap_times) / len(self.tap_times)
            if avg_interval > 0:
                self.bpm = 60.0 / avg_interval
                logging.info(f"Calculated BPM: {self.bpm:.2f}")

        self.last_tap_time = current_time

    def set_beats_per_bar(self, beats):
        if beats > 0:
            self.beats_per_bar = beats
            self.current_beat = 1
            self.samples_since_last_beat = 0
            logging.info(f"Beats per bar set to: {beats}")

    def get_beats_per_bar(self):
        return self.beats_per_bar

    def set_tap_reset_threshold(self, threshold):
        if 0 <= threshold <= 127:
            self.tap_reset_velocity_threshold = threshold
            logging.info(f"Tap reset velocity threshold set to: {threshold}")

