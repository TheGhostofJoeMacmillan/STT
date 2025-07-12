#!/usr/bin/env python3
import argparse
import os
import queue
import sys
import json
import threading
import time
import zipfile
import requests
from pynput import keyboard
import pyperclip
import sounddevice as sd
from vosk import Model, KaldiRecognizer

# --- Configuration ---
MODEL_NAME = "vosk-model-small-en-us-0.15"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODEL_DIR = os.path.join(os.path.expanduser("~"), ".cache", "vosk")
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_NAME)
SAMPLE_RATE = 16000
DEVICE = None # Default microphone
CHANNELS = 1
BLOCK_SIZE = 8000

# --- Global State ---
q = queue.Queue()
is_recording = threading.Event()
is_space_pressed = False
recognizer = None

def download_and_unzip_model():
    """Downloads and extracts the Vosk model if it doesn't exist."""
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
                        # The fix is here: using single quotes inside the f-string
                        print(f'\rDownloading: {progress:.2f}%', end='')
            print("\nExtracting model...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(MODEL_DIR)
            os.remove(zip_path)
            print("Model ready.")
        except requests.exceptions.RequestException as e:
            print(f"Error downloading model: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error extracting model: {e}")
            sys.exit(1)

def audio_callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status, file=sys.stderr)
    if is_recording.is_set():
        q.put(bytes(indata))

def on_press(key):
    """Handle key press events."""
    global is_space_pressed
    if key == keyboard.Key.space and not is_space_pressed:
        is_space_pressed = True
        is_recording.set()
        print("Listening... (release space to transcribe)")

def on_release(key):
    """Handle key release events."""
    global is_space_pressed
    if key == keyboard.Key.space:
        is_space_pressed = False
        is_recording.clear()

def transcribe_audio():
    """Main transcription loop."""
    global recognizer
    download_and_unzip_model()
    try:
        model = Model(MODEL_PATH)
        recognizer = KaldiRecognizer(model, SAMPLE_RATE)
        recognizer.SetWords(True)
    except Exception as e:
        print(f"Failed to initialize recognizer: {e}")
        sys.exit(1)

    print("--- VOSK STT ---")
    print("Press and hold SPACE to record. Press Ctrl+C to exit.")

    try:
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, device=DEVICE,
                               dtype='int16', channels=CHANNELS, callback=audio_callback):
            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.start()

            while listener.is_alive():
                if not is_recording.is_set() and not q.empty():
                    # Process remaining audio in the queue after recording stops
                    while not q.empty():
                        data = q.get()
                        recognizer.AcceptWaveform(data)

                    # Get final result
                    result_json = recognizer.FinalResult()
                    result_dict = json.loads(result_json)
                    text = result_dict.get('text', '').strip()

                    if text:
                        print(f"\rTranscription: {text}")
                        try:
                            pyperclip.copy(text)
                            print("Copied to clipboard.")
                        except pyperclip.PyperclipException:
                            print("(Could not copy to clipboard. `xclip` or `xsel` may be required.)")
                    else:
                        # Clear the "Listening..." line
                        print("\r" + " " * 50 + "\r", end="")

                    recognizer.Reset()
                time.sleep(0.1)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("\nExiting.")
        if 'listener' in locals() and listener.is_alive():
            listener.stop()

if __name__ == "__main__":
    try:
        transcribe_audio()
    except KeyboardInterrupt:
        sys.exit(0)