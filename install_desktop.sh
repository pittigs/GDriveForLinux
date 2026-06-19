#!/bin/bash
# Get the absolute directory of the project
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
RUN_SCRIPT="$DIR/run.sh"
ICON_PATH="$DIR/gdrive_app/assets/icon.svg"

# Target paths
APP_DIR="$HOME/.local/share/applications"
TARGET_DESKTOP="$APP_DIR/gdrive-mount.desktop"

# Ensure target directories exist
mkdir -p "$APP_DIR"

echo "Erstelle Desktop-Eintrag für Google Drive Mount..."

# Read template and replace placeholders
cat "$DIR/gdrive-mount.desktop" | \
    sed "s|PLACEHOLDER_EXEC|$RUN_SCRIPT|g" | \
    sed "s|PLACEHOLDER_ICON|$ICON_PATH|g" > "$TARGET_DESKTOP"

# Set permissions
chmod +x "$TARGET_DESKTOP"

# Refresh desktop database (if update-desktop-database exists)
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$APP_DIR"
fi

echo "✓ Google Drive Mount wurde erfolgreich installiert!"
echo "Sie finden die App jetzt im Anwendungsmenü Ihres Desktops."
