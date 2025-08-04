# STT - Command-Line Speech-to-Text

A simple, offline speech-to-text (STT) application that runs in your terminal. It can type the transcribed text, copy it to the clipboard, or paste it on a mouse click.

## Features

- **Offline First:** Uses the small and efficient Vosk offline model (`vosk-model-small-en-us-0.15`). The model is downloaded automatically on the first run.
- **Push-to-Talk:** Press **<Ctrl>+<Shift>+<Space>** to toggle recording.
- **Multiple Output Modes:**
  - **Type Mode (Default):** The transcribed text is automatically typed into the active window.
  - **Copy Mode:** The transcribed text is automatically copied to the clipboard.
  - **Mouse Click Paste Mode:** The transcribed text is pasted on the next mouse click.
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

After installation, simply open a new terminal and run the `stt` command with the desired flags.

When the application is running, it will display the following message:
```
--- VOSK STT ---
Press <Ctrl>+<Shift>+<Space> to toggle recording.
Press Ctrl+C in the terminal to exit.
✅ Ready to record. Press hotkey.
```

### Default Mode (Type)

```bash
stt
```

Press **<Ctrl>+<Shift>+<Space>** to start and stop recording. The text will be typed into the active window.

### Copy Mode

```bash
stt --copy
```

The transcribed text will be copied to the clipboard.

### Mouse Click Paste Mode

```bash
stt --mouse-click
```

After a transcription is complete, the text will be pasted at the location of the next mouse click.

Press `Ctrl+C` in the terminal to exit the application.

## Troubleshooting

### Hotkey Issues on Linux

This application uses the `pynput` library to listen for keyboard input. Keyboard event handling on Linux can sometimes be complex. If the hotkey does not work, it may be due to the X11 or Wayland display server configuration.

This application previously used a `suppress=True` feature of `pynput` to prevent the hotkey from being passed to other applications, but this was found to be unstable and could cause system crashes on some Linux distributions. This feature has been removed to ensure stability.
