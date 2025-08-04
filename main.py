#!/usr/bin/env python3
import os
import queue
import sys
import json
import time
import zipfile
import requests
import argparse
import pyperclip
from pynput import keyboard, mouse
from pynput.keyboard import Controller, Key
import sounddevice as sd
from vosk import Model, KaldiRecognizer, SetLogLevel

# --- Constants ---
MODEL_NAME = "vosk-model-small-en-us-0.15"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODEL_DIR = os.path.join(os.path.expanduser("~"), ".cache", "vosk")
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_NAME)
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 8000

class SttApp:
    def __init__(self, mode='type', simulate_enter=False, verbose=False):
        self.mode = mode
        self.simulate_enter = simulate_enter
        self.verbose = verbose
        self.q = queue.Queue()
        self.is_recording = False
        self.current_keys = set()
        self.last_transcription = ""
        self.recognizer = None
        self.keyboard_controller = Controller()
        self.keyboard_listener = None
        self.mouse_listener = None

    def _log(self, message):
        if self.verbose:
            print(message, file=sys.stderr)

    def download_and_unzip_model(self):
        os.makedirs(MODEL_DIR, exist_ok=True)
        if not os.path.exists(MODEL_PATH):
            print(f"Model not found. Downloading {MODEL_NAME}...")
            zip_path = os.path.join(MODEL_DIR, f"{MODEL_NAME}.zip")
            try:
                with requests.get(MODEL_URL, stream=True) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get('content-length', 0))
                    bytes_downloaded = 0
                    with open(zip_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
                            progress = (bytes_downloaded / total_size) * 100
                            print(f'\rDownloading: {progress:.2f}%', end='')
                print("\nExtracting model...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(MODEL_DIR)
                os.remove(zip_path)
                print("Model ready.")
            except requests.exceptions.RequestException as e:
                print(f"Error downloading model: {e}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Error extracting model: {e}", file=sys.stderr)
                sys.exit(1)

    def audio_callback(self, indata, frames, time, status):
        if status:
            self._log(f"Audio status: {status}")
        if self.is_recording:
            self.q.put(bytes(indata))

    def on_press(self, key):
        if key in self.current_keys:
            return
        self.current_keys.add(key)
        if keyboard.Key.ctrl in self.current_keys and \
           keyboard.Key.shift in self.current_keys and \
           key == keyboard.Key.space:
            self.is_recording = not self.is_recording

    def on_release(self, key):
        try:
            self.current_keys.remove(key)
        except KeyError:
            pass

    def on_click(self, x, y, button, pressed):
        if pressed and self.last_transcription:
            pyperclip.copy(self.last_transcription)
            self._log(f"Pasted on click: {self.last_transcription}")
            with self.keyboard_controller.pressed(Key.ctrl):
                self.keyboard_controller.press('v')
                self.keyboard_controller.release('v')
        return True

    def insert_text(self, text):
        if not text:
            return
        self.keyboard_controller.type(text + ' ')
        if self.simulate_enter:
            self.keyboard_controller.press(Key.enter)
            self.keyboard_controller.release(Key.enter)

    def run(self):
        self.download_and_unzip_model()
        try:
            SetLogLevel(-1)
            model = Model(MODEL_PATH)
            self.recognizer = KaldiRecognizer(model, SAMPLE_RATE)
            self.recognizer.SetWords(True)
        except Exception as e:
            print(f"Error: Failed to initialize Vosk recognizer: {e}", file=sys.stderr)
            sys.exit(1)

        try:
            sd.check_input_settings(device=None, samplerate=SAMPLE_RATE, channels=CHANNELS)
        except sd.PortAudioError as e:
            print(f"Error: Audio device not suitable.", file=sys.stderr)
            print(f"Please check your microphone. It might not support {SAMPLE_RATE}Hz sample rate or {CHANNELS} channel(s).", file=sys.stderr)
            print(f"Details: {e}", file=sys.stderr)
            sys.exit(1)

        print("\n--- VOSK STT ---")
        print("Press <Ctrl>+<Shift>+<Space> to toggle recording.")
        print("Press Ctrl+C in the terminal to exit.")

        self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.keyboard_listener.start()

        if self.mode == 'mouse_click':
            self.mouse_listener = mouse.Listener(on_click=self.on_click)
            self.mouse_listener.start()
            self._log("Mouse click paste is active.")

        try:
            with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
                                   device=None, dtype='int16', channels=CHANNELS,
                                   callback=self.audio_callback):
                self.main_loop()
        except sd.PortAudioError as e:
            print(f"Error: Could not open audio stream: {e}", file=sys.stderr)
            print("Please check your microphone connection and system permissions.", file=sys.stderr)
        except Exception as e:
            print(f"An unexpected error occurred in the main loop: {e}", file=sys.stderr)
        finally:
            self.stop()

    def main_loop(self):
        spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        spinner_index = 0
        was_recording = False
        ready_message_shown = False

        while self.keyboard_listener.is_alive():
            if self.is_recording:
                ready_message_shown = False
                was_recording = True
                spinner_char = spinner_chars[spinner_index]
                sys.stdout.write(f"\r🎤 Recording {spinner_char} ")
                sys.stdout.flush()
                spinner_index = (spinner_index + 1) % len(spinner_chars)
                time.sleep(0.1)
            elif was_recording:
                was_recording = False
                sys.stdout.write("\r" + " " * 30 + "\r")
                sys.stdout.flush()
                self.process_audio_queue()
            else:
                if not ready_message_shown:
                    sys.stdout.write("\r✅ Ready to record. Press hotkey. ")
                    sys.stdout.flush()
                    ready_message_shown = True
                time.sleep(0.1)

    def process_audio_queue(self):
        if self.q.empty():
            return

        sys.stdout.write("\r🧠 Processing...      ")
        sys.stdout.flush()

        while not self.q.empty():
            data = self.q.get()
            self.recognizer.AcceptWaveform(data)

        result_json = self.recognizer.FinalResult()
        result_dict = json.loads(result_json)
        text = result_dict.get('text', '').strip()

        sys.stdout.write("\r" + " " * 20 + "\r")
        sys.stdout.flush()

        if text:
            self._log(f"Transcription: {text}")
            self.last_transcription = text
            if self.mode == 'type':
                self.insert_text(text)
            elif self.mode == 'copy':
                pyperclip.copy(text)
                self._log("Copied to clipboard.")

        self.recognizer.Reset()

    def stop(self):
        self._log("Exiting.")
        if self.keyboard_listener and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()
        if self.mouse_listener and self.mouse_listener.is_alive():
            self.mouse_listener.stop()
        print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A simple, offline speech-to-text tool.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-c', '--copy',
        action='store_true',
        help="Enable copy mode instead of typing."
    )
    parser.add_argument(
        '-mc', '--mouse-click',
        action='store_true',
        help="Enable paste on mouse click mode."
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help="Print verbose output to stderr."
    )
    args = parser.parse_args()

    mode = 'type'
    if args.copy:
        mode = 'copy'
    elif args.mouse_click:
        mode = 'mouse_click'

    app = SttApp(mode=mode, verbose=args.verbose)
    try:
        app.run()
    except KeyboardInterrupt:
        app.stop()
        sys.exit(0)