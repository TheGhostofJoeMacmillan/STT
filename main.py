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
from vosk import Model, KaldiRecognizer

# --- Configuration ---
MODEL_NAME = "vosk-model-small-en-us-0.15"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODEL_DIR = os.path.join(os.path.expanduser("~"), ".cache", "vosk")
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_NAME)
SAMPLE_RATE = 16000
DEVICE = None  # Default microphone
CHANNELS = 1
BLOCK_SIZE = 8000
SIMULATE_ENTER = False  # Set to True to press Enter after inserting text
controller = Controller()  # For typing text and backspace

# --- Global State ---
q = queue.Queue()
is_recording = False
recognizer = None
current_keys = set()  # Track currently pressed keys
last_transcription = ""

def download_and_unzip_model():
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
            print(f"Error downloading model: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error extracting model: {e}")
            sys.exit(1)

def audio_callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    if is_recording:
        q.put(bytes(indata))

def on_press(key):
    global is_recording
    current_keys.add(key)
    if keyboard.Key.ctrl in current_keys and keyboard.Key.shift in current_keys and keyboard.Key.space == key:
        controller.press(Key.backspace)
        controller.release(Key.backspace)
        is_recording = not is_recording
        if is_recording:
            print("Recording started... (press Ctrl+Shift+Space again to stop)")
        else:
            print("Recording stopped. Processing...")

def on_release(key):
    if key in current_keys:
        current_keys.remove(key)

def on_click(x, y, button, pressed):
    if pressed and last_transcription:
        pyperclip.copy(last_transcription)
        print(f"Pasted on click: {last_transcription}")
        # Simulate Ctrl+V to paste
        with controller.pressed(Key.ctrl):
            controller.press('v')
            controller.release('v')
    return True

def insert_text(text):
    if not text:
        return
    controller.type(text + ' ')
    if SIMULATE_ENTER:
        controller.press(Key.enter)
        controller.release(Key.enter)

def transcribe_audio(mode='type'):
    global recognizer, last_transcription
    download_and_unzip_model()
    try:
        model = Model(MODEL_PATH)
        recognizer = KaldiRecognizer(model, SAMPLE_RATE)
        recognizer.SetWords(True)
    except Exception as e:
        print(f"Failed to initialize recognizer: {e}")
        sys.exit(1)

    print("--- VOSK STT (Toggle with Ctrl+Shift+Space) ---")
    print("Press Ctrl+Shift+Space to start/stop recording. Ctrl+C to exit.")

    listener_keyboard = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener_keyboard.start()

    listener_mouse = None
    if mode == 'mouse_click':
        listener_mouse = mouse.Listener(on_click=on_click)
        listener_mouse.start()
        print("Mouse click paste is active.")

    try:
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, device=DEVICE,
                               dtype='int16', channels=CHANNELS, callback=audio_callback):
            while listener_keyboard.is_alive():
                if not is_recording and not q.empty():
                    while not q.empty():
                        data = q.get()
                        recognizer.AcceptWaveform(data)

                    time.sleep(0.5)
                    result_json = recognizer.FinalResult()
                    result_dict = json.loads(result_json)
                    text = result_dict.get('text', '').strip()

                    if text:
                        print(f"\rTranscription: {text}")
                        last_transcription = text
                        if mode == 'type':
                            insert_text(text)
                        elif mode == 'copy':
                            pyperclip.copy(text)
                            print("Copied to clipboard.")
                    else:
                        print("\r" + " " * 50 + "\r", end="")

                    recognizer.Reset()
                time.sleep(0.1)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("\nExiting.")
        listener_keyboard.stop()
        if listener_mouse:
            listener_mouse.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline Speech-to-Text Tool.")
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
    args = parser.parse_args()

    mode = 'type'
    if args.copy:
        mode = 'copy'
    elif args.mouse_click:
        mode = 'mouse_click'

    try:
        transcribe_audio(mode=mode)
    except KeyboardInterrupt:
        sys.exit(0)