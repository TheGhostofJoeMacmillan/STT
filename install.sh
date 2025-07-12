#!/bin/bash

# Get the absolute path of the script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
MAIN_SCRIPT_PATH="$SCRIPT_DIR/main.py"
VENV_PATH="$SCRIPT_DIR/venv"
LAUNCHER_PATH="$HOME/.local/bin/stt"

echo "Setting up virtual environment in $VENV_PATH..."
# Create a virtual environment
python3 -m venv "$VENV_PATH"

if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "Failed to create virtual environment."
    exit 1
fi

echo "Installing dependencies..."
# Activate the virtual environment and install dependencies
source "$VENV_PATH/bin/activate"
pip install -r "$SCRIPT_DIR/requirements.txt"
deactivate

echo "Creating launcher..."
# Create the target directory if it doesn't exist
mkdir -p "$(dirname "$LAUNCHER_PATH")"

# Create the launcher script that activates the venv and runs the main script
cat << EOF > "$LAUNCHER_PATH"
#!/bin/bash
source "$VENV_PATH/bin/activate"
python3 "$MAIN_SCRIPT_PATH" "\$@"
EOF

# Make the launcher executable
chmod +x "$LAUNCHER_PATH"

echo ""
echo "--- Installation Complete ---"
echo "The application 'stt' is now installed."
echo ""
echo "IMPORTANT: Please ensure '$HOME/.local/bin' is in your system's PATH."
echo "You may need to add the following line to your shell profile (e.g., ~/.bashrc, ~/.zshrc):"
echo 'export PATH="$HOME/.local/bin:$PATH"'
echo ""
echo "After updating your profile, open a new terminal or run 'source ~/.bashrc' (or equivalent)."
echo "You can then run the application by simply typing:"
echo "stt"
