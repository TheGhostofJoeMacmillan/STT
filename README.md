# stt - minimal speech-to-text

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

A beautifully minimal, offline speech-to-text tool that just works. Clean interface, configurable hotkeys, and multiple output modes.

## ✨ Features

- **🎙️ Offline** - No internet required after setup
- **⌨️ Custom hotkeys** - Any key combination you want  
- **🎯 Multiple modes** - Type, copy, or paste on click
- **📦 Zero config** - One command install, ready to use
- **🎨 Minimal UI** - Clean status indicators, optional volume dots
- **🔒 Private** - All processing happens locally

## 🚀 Quick Start

```bash
# Install
git clone https://github.com/TheGhostofJoeMacmillan/STT
cd STT
./install.sh

# Use
stt                    # Basic typing mode
stt -c -k f1          # Copy mode with F1 key  
stt -v -mc            # Mouse paste with volume dots
```

## 📖 Usage

### Basic Modes
```bash
stt           # Type transcribed text directly
stt -c        # Copy text to clipboard  
stt -mc       # Paste on mouse click
stt -v        # Show volume dots visualization
```

### Custom Hotkeys
```bash
stt -k f1                    # F1 key
stt -k "ctrl+r"             # Ctrl+R
stt -k "shift+space"        # Shift+Space
```

### Status Indicators
- 🟢 `• ready` - Press hotkey to start
- 🟡 `⠋ listening` - Recording your voice  
- 🔴 `⠙ processing` - Converting to text

With `-v` flag, volume dots extend to show audio levels:
```
🟡 ⠋ listening ••••••••••••••••
```

## ⚙️ Installation Details

The installer creates:
- Virtual environment with all dependencies
- `~/.local/bin/stt` command  
- Auto-downloads Vosk model (~40MB) on first run

Make sure `~/.local/bin` is in your PATH:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## 🎯 Examples

```bash
# Quick voice notes while coding
stt -c -k f1

# Transcribe to document  
stt -v

# Voice commands with mouse
stt -mc -k "ctrl+space"
```

## 🔧 Requirements

- Python 3.7+
- Microphone access
- Linux/macOS/Windows

## 💡 Tips

- **Speak clearly** for best results
- **Quiet environment** improves accuracy  
- **Try different hotkeys** if one doesn't work
- **Use `-v` mode** to see if microphone is working

## 🐛 Troubleshooting

**Microphone not working?**
- Check system audio permissions
- Test with other audio apps first

**Hotkey not responding?**  
- Try function keys (`f1`, `f2`) instead of combinations
- Some key combos may be reserved by system

**Poor recognition?**
- Increase microphone volume
- Reduce background noise
- Speak more slowly and clearly

## 🏗️ Technical Details

- **Engine**: Vosk offline speech recognition
- **Model**: English US, optimized for speed/accuracy
- **Audio**: 16kHz sampling, real-time processing
- **Interface**: Terminal-based with ANSI colors

## 🔒 Privacy

100% offline processing. No data sent to external servers. Your voice stays on your machine.

## 📄 License

MIT License - feel free to modify and share!