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
import threading
import shutil
import numpy as np
import termios
import tty
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
    def __init__(self, mode='type', simulate_enter=False, visualizer=False, hotkey_combo=None):
        self.mode = mode
        self.simulate_enter = simulate_enter
        self.visualizer = visualizer
        self.q = queue.Queue()
        self.is_recording = False
        self.current_keys = set()
        self.last_transcription = ""
        self.recognizer = None
        self.keyboard_controller = Controller()
        self.keyboard_listener = None
        self.mouse_listener = None
        self.last_toggle_time = 0
        
        # Parse hotkey combination
        self.hotkey_combo = hotkey_combo or ['ctrl', 'shift', 'space']
        self.hotkey_keys = []
        for key_name in self.hotkey_combo:
            key_lower = key_name.lower()
            if key_lower == 'ctrl':
                self.hotkey_keys.append(keyboard.Key.ctrl)
            elif key_lower == 'shift':
                self.hotkey_keys.append(keyboard.Key.shift)
            elif key_lower == 'alt':
                self.hotkey_keys.append(keyboard.Key.alt)
            elif key_lower == 'space':
                self.hotkey_keys.append(keyboard.Key.space)
            elif key_lower == 'tab':
                self.hotkey_keys.append(keyboard.Key.tab)
            elif key_lower == 'enter':
                self.hotkey_keys.append(keyboard.Key.enter)
            elif key_lower.startswith('f') and key_lower[1:].isdigit():
                # Function keys F1-F12
                fkey_num = int(key_lower[1:])
                self.hotkey_keys.append(getattr(keyboard.Key, f'f{fkey_num}'))
            elif len(key_name) == 1:
                self.hotkey_keys.append(keyboard.KeyCode.from_char(key_name.lower()))
        
        # Audio visualization data
        self.audio_data = []
        self.frequency_data = []
        self.max_audio_history = 200
        self.terminal_width = shutil.get_terminal_size().columns
        self.terminal_height = shutil.get_terminal_size().lines
        self.num_bars = min(60, self.terminal_width - 10)  # Number of frequency bars
        self.original_settings = None

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
        if self.is_recording:
            self.q.put(bytes(indata))
        
        # Store audio data for visualization
        if self.visualizer:
            # Convert to numpy array
            audio_array = np.frombuffer(indata, dtype=np.int16).astype(np.float32)
            
            # Calculate overall audio level
            audio_level = np.sqrt(np.mean(audio_array**2)) / 32768.0
            self.audio_data.append(audio_level)
            if len(self.audio_data) > self.max_audio_history:
                self.audio_data.pop(0)
            
            # Frequency analysis for spectrum
            if len(audio_array) >= 512:  # Ensure we have enough samples
                # Apply window and FFT
                windowed = audio_array[:512] * np.hanning(512)
                fft = np.abs(np.fft.rfft(windowed))
                
                # Group frequencies into bars
                freqs_per_bar = len(fft) // self.num_bars
                spectrum = []
                for i in range(self.num_bars):
                    start_idx = i * freqs_per_bar
                    end_idx = (i + 1) * freqs_per_bar
                    if end_idx > len(fft):
                        end_idx = len(fft)
                    bar_magnitude = np.mean(fft[start_idx:end_idx])
                    spectrum.append(bar_magnitude)
                
                # Normalize and store
                if max(spectrum) > 0:
                    spectrum = [s / max(spectrum) for s in spectrum]
                self.frequency_data = spectrum

    def on_press(self, key):
        if key in self.current_keys:
            return
        self.current_keys.add(key)
        
        # Check if all hotkey keys are pressed
        if all(hkey in self.current_keys for hkey in self.hotkey_keys[:-1]) and key == self.hotkey_keys[-1]:
            now = time.time()
            if now - self.last_toggle_time > 0.3:
                self.is_recording = not self.is_recording
                self.last_toggle_time = now
                # Clear any key echo that might appear
                if not self.visualizer:
                    sys.stdout.write("\r" + " " * 50 + "\r")
                    sys.stdout.flush()

    def on_release(self, key):
        try:
            self.current_keys.remove(key)
        except KeyError:
            pass

    def on_click(self, x, y, button, pressed):
        if pressed and self.last_transcription:
            # Copy to clipboard first
            pyperclip.copy(self.last_transcription)
            # Small delay to ensure clipboard is set
            time.sleep(0.05)
            # Paste using Ctrl+V
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
    
    def draw_vu_meters(self):
        """Draw classic VU meter visualization"""
        lines = []
        
        # Get current audio level
        current_level = self.audio_data[-1] if self.audio_data else 0
        
        # VU meter settings
        meter_width = 50
        filled_blocks = int(current_level * meter_width)
        
        # Create the main VU meter
        meter_line = "  VU │ "
        
        # Build the meter bar
        for i in range(meter_width):
            if i < filled_blocks:
                if i < meter_width * 0.6:
                    meter_line += "\033[92m█\033[0m"  # Green for safe levels
                elif i < meter_width * 0.8:
                    meter_line += "\033[93m█\033[0m"  # Yellow for moderate
                else:
                    meter_line += "\033[91m█\033[0m"  # Red for high levels
            else:
                meter_line += "\033[90m░\033[0m"  # Gray for empty
        
        # Add level percentage
        level_percent = int(current_level * 100)
        meter_line += f" │ {level_percent:3d}%"
        
        lines.append("")
        lines.append(meter_line)
        
        # Add a peak indicator if recording
        if self.is_recording:
            peak_line = "     │ "
            peak_pos = min(filled_blocks, meter_width - 1)
            for i in range(meter_width):
                if i == peak_pos and current_level > 0.1:
                    peak_line += "\033[95m▲\033[0m"  # Magenta peak indicator
                else:
                    peak_line += " "
            peak_line += " │"
            lines.append(peak_line)
        
        lines.append("")
        
        # Add frequency bands for extra visual interest
        if self.frequency_data:
            bands = ["BASS", "MID ", "HIGH"]
            band_line = "     │ "
            
            # Group frequency data into 3 bands
            band_size = len(self.frequency_data) // 3
            for i, band_name in enumerate(bands):
                start_idx = i * band_size
                end_idx = (i + 1) * band_size if i < 2 else len(self.frequency_data)
                band_level = sum(self.frequency_data[start_idx:end_idx]) / (end_idx - start_idx) if end_idx > start_idx else 0
                
                # Create mini bar for each band
                mini_bars = int(band_level * 8)
                band_display = ""
                for j in range(8):
                    if j < mini_bars:
                        if i == 0:  # Bass - blue
                            band_display += "\033[94m▌\033[0m"
                        elif i == 1:  # Mid - green
                            band_display += "\033[92m▌\033[0m"
                        else:  # High - yellow
                            band_display += "\033[93m▌\033[0m"
                    else:
                        band_display += "\033[90m▌\033[0m"
                
                band_line += f"{band_name}:{band_display} "
            
            band_line += "│"
            lines.append(band_line)
        
        return lines
    
    def draw_clean_header(self):
        """Draw a minimal, clean header"""
        # Format hotkey display
        hotkey_parts = []
        for k in self.hotkey_keys:
            if hasattr(k, 'name'):
                hotkey_parts.append(k.name.upper())
            else:
                key_str = str(k)
                if 'KeyCode' in key_str:
                    if 'char=' in key_str:
                        char = key_str.split("char='")[1].split("'")[0]
                        hotkey_parts.append(char.upper())
                else:
                    hotkey_parts.append(key_str.replace('Key.', '').upper())
        
        hotkey_display = '+'.join(hotkey_parts)
        
        # Clean header line
        status_icon = "🔴" if self.is_recording else "⚪"
        header = f" {status_icon} VOSK STT  │  Hotkey: {hotkey_display}  │  Mode: {self.mode.upper()}"
        
        return [header, "─" * len(header)]
    
    def draw_clean_status(self):
        """Draw a clean status line at bottom"""
        if self.last_transcription:
            text_preview = self.last_transcription[:60] + "..." if len(self.last_transcription) > 60 else self.last_transcription
            status = f"💬 \"{text_preview}\""
        else:
            status = "💬 Ready to record..."
        
        return ["", status]
    
    def render_visualizer(self):
        """Render minimal visualizer with volume dots"""
        if not self.visualizer:
            return
        
        # Get current audio level for dot visualization
        current_level = self.audio_data[-1] if self.audio_data else 0
        max_dots = 20
        num_dots = int(current_level * max_dots)
        
        # Create dot visualization
        dots = "•" * num_dots
        
        # Position cursor at top-left and clear line
        sys.stdout.write("\033[1;1H")  # Move to row 1, column 1 (top-left)
        sys.stdout.write("\033[K")     # Clear from cursor to end of line
        
        if self.is_recording:
            spinner_char = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[int(time.time() * 10) % 10]
            line = f"\033[93m{spinner_char} listening\033[0m {dots}"
        elif hasattr(self, '_was_recording') and self._was_recording:
            spinner_char = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[int(time.time() * 10) % 10]
            line = f"\033[91m{spinner_char} processing\033[0m {dots}"
        else:
            line = f"\033[92m• ready\033[0m {dots}"
        
        sys.stdout.write(line)
        sys.stdout.flush()

    def run(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        time.sleep(0.05) # Add a small delay to ensure the terminal has time to clear
        
        # Disable terminal echo and hide cursor for cleaner display
        if sys.stdin.isatty():
            self.original_settings = termios.tcgetattr(sys.stdin)
            new_settings = termios.tcgetattr(sys.stdin)
            new_settings[3] = new_settings[3] & ~termios.ECHO  # Disable echo
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)
            
            # Hide cursor
            sys.stdout.write('\033[?25l')
            sys.stdout.flush()
        
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

        if not self.visualizer:
            # Minimal startup - no messages, just start
            pass

        self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.keyboard_listener.start()

        if self.mode == 'mouse_click':
            self.mouse_listener = mouse.Listener(on_click=self.on_click)
            self.mouse_listener.start()

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
        if self.visualizer:
            # Minimal visualizer mode - just dots
            was_recording = False
            processing = False
            
            while self.keyboard_listener.is_alive():
                # Track state for processing display
                if was_recording and not self.is_recording and not processing:
                    processing = True
                    self._was_recording = True
                    self.render_visualizer()
                    self.process_audio_queue()
                    processing = False
                    self._was_recording = False
                elif self.is_recording:
                    was_recording = True
                    self._was_recording = False
                else:
                    self._was_recording = False
                
                self.render_visualizer()
                time.sleep(0.05)  # Smooth dot updates
        else:
            # Minimal mode - just status with spinner
            spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            spinner_index = 0
            was_recording = False
            processing = False

            while self.keyboard_listener.is_alive():
                if self.is_recording:
                    was_recording = True
                    processing = False
                    spinner_char = spinner_chars[spinner_index]
                    # Clear line and write listening state
                    sys.stdout.write("\r" + " " * 50 + "\r")
                    line = f"\033[93m{spinner_char} listening\033[0m"  # Yellow
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    spinner_index = (spinner_index + 1) % len(spinner_chars)
                    time.sleep(0.1)
                elif was_recording and not processing:
                    processing = True
                    was_recording = False
                    spinner_char = spinner_chars[spinner_index]
                    # Clear line and write processing state
                    sys.stdout.write("\r" + " " * 50 + "\r")
                    line = f"\033[91m{spinner_char} processing\033[0m"  # Red
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    self.process_audio_queue()
                    processing = False
                    # Show ready state briefly
                    sys.stdout.write("\r" + " " * 50 + "\r")
                    line = f"\033[92m• ready\033[0m"  # Green
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    time.sleep(0.5)  # Brief pause to show result
                else:
                    if not processing:
                        # Clear the entire line first, then write ready state
                        sys.stdout.write("\r" + " " * 50 + "\r")
                        line = f"\033[92m• ready\033[0m"  # Green
                        sys.stdout.write(line)
                        sys.stdout.flush()
                    time.sleep(0.1)

    def process_audio_queue(self):
        if self.q.empty():
            return

        # Processing is now handled in the main loop for minimal mode

        while not self.q.empty():
            data = self.q.get()
            self.recognizer.AcceptWaveform(data)

        result_json = self.recognizer.FinalResult()
        result_dict = json.loads(result_json)
        text = result_dict.get('text', '').strip()

        # No need to clear - minimal mode handles display in main loop

        if text:
            self.last_transcription = text
            if self.mode == 'type':
                self.insert_text(text)
            elif self.mode == 'copy':
                pyperclip.copy(text)

        self.recognizer.Reset()

    def stop(self):
        # Restore terminal settings and show cursor
        if self.original_settings and sys.stdin.isatty():
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.original_settings)
            # Show cursor again
            sys.stdout.write('\033[?25h')
            sys.stdout.flush()
        
        if self.keyboard_listener and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()
        if self.mouse_listener and self.mouse_listener.is_alive():
            self.mouse_listener.stop()
        print()

class MinimalHelpFormatter(argparse.HelpFormatter):
    """Custom formatter for minimal, clean help output"""
    def _format_usage(self, usage, actions, groups, prefix):
        return f"stt [-c|-mc] [-v] [-k HOTKEY]\n\n"
    
    def format_help(self):
        return """stt - minimal speech-to-text

USAGE
  stt [-c|-mc] [-v] [-k HOTKEY]

MODES
  (default)     Type transcribed text directly
  -c            Copy text to clipboard  
  -mc           Paste on mouse click

OPTIONS  
  -v            Show volume dots
  -k HOTKEY     Custom hotkey (default: ctrl+shift+space)
                Examples: f1, ctrl+r, shift+space

EXAMPLES
  stt                    Basic mode
  stt -c -k f1          Copy mode with F1 key
  stt -v -mc            Mouse mode with dots

"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="",
        formatter_class=MinimalHelpFormatter,
        add_help=False
    )
    parser.add_argument(
        '-h', '--help', 
        action='store_true',
        help=argparse.SUPPRESS
    )
    parser.add_argument(
        '-c', '--copy',
        action='store_true'
    )
    parser.add_argument(
        '-mc', '--mouse-click',
        action='store_true'
    )
    parser.add_argument(
        '-v', '--visualizer',
        action='store_true'
    )
    parser.add_argument(
        '-k', '--hotkey',
        default='ctrl+shift+space'
    )
    args = parser.parse_args()

    # Handle help
    if args.help:
        print(parser.format_help(), end='')
        sys.exit(0)

    mode = 'type'
    if args.copy:
        mode = 'copy'
    elif args.mouse_click:
        mode = 'mouse_click'

    # Parse hotkey combination
    hotkey_combo = [key.strip().lower() for key in args.hotkey.split('+')]

    app = SttApp(mode=mode, visualizer=args.visualizer, hotkey_combo=hotkey_combo)
    try:
        app.run()
    except KeyboardInterrupt:
        app.stop()
        sys.exit(0)