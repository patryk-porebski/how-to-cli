#!/bin/bash

# Install script for how CLI tool

echo "Setting up how command..."

# Install Python dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Make how.py executable
chmod +x how.py

# Create local bin directory
mkdir -p ~/.local/bin

# Create symlink
ln -sf "$(pwd)/how.py" ~/.local/bin/how

echo "✓ Created symlink: ~/.local/bin/how -> $(pwd)/how.py"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo ""
    echo "⚠️  ~/.local/bin is not in your PATH"
    echo "Add this line to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then reload your shell with: source ~/.bashrc (or ~/.zshrc)"
else
    echo "✓ ~/.local/bin is already in your PATH"
fi

echo ""
echo "✓ Setup complete! You can now use: how to 'your question'"
echo "Don't forget to add your OpenRouter API key with: how config-set --key openrouter.api_key --value 'your-key'"
