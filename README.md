# STT - Command-Line Speech-to-Text

A simple, offline speech-to-text (STT) application that runs in your terminal. Press and hold the spacebar to record audio from your microphone, and the transcribed text is automatically printed and copied to your clipboard.

## Features

- **Offline First:** Uses the small and efficient Vosk offline model (`vosk-model-small-en-us-0.15`). The model is downloaded automatically on the first run.
- **Push-to-Talk:** Press and hold the **spacebar** to record. Release to transcribe.
- **Clipboard Integration:** The most recent transcription is automatically copied to the clipboard for easy pasting.
- **Simple Installation:** A single installation script sets up a virtual environment and a system-wide `stt` command.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url-here>
    cd stt
    ```

2.  **Run the installer:**
    This will create a local Python virtual environment, install dependencies, and create the `stt` command in `~/.local/bin/`.
    ```bash
    chmod +x install.sh
    ./install.sh
    ```

3.  **Update your PATH:**
    Ensure `~/.local/bin` is in your shell's PATH. You may need to add the following line to your `~/.bashrc` or `~/.zshrc` and restart your terminal:
    ```bash
    export PATH="$HOME/.local/bin:$PATH"
    ```

4.  **Install Clipboard Utility (Linux):**
    For the copy-to-clipboard functionality to work on Linux, you need to have either `xclip` or `xsel` installed.
    ```bash
    # For Debian/Ubuntu
    sudo apt-get update && sudo apt-get install xclip
    ```

## Usage

After installation, simply open a new terminal and run:

```bash
stt
```

Press and hold the **spacebar** to start recording. Release it to see the transcription.

Press `Ctrl+C` to exit the application.
