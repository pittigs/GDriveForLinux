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

echo "=== Google Drive Mount für Linux - Installation ==="
echo ""

# Function to check if Python and PyQt6 are installed
check_python_pyqt() {
    if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
        return 1 # Python missing
    fi
    # Check if PyQt6 can be imported
    if python3 -c "import PyQt6" &> /dev/null || python -c "import PyQt6" &> /dev/null; then
        return 0 # All good
    fi
    return 2 # PyQt6 missing
}

# Function to check if FUSE3 is installed
check_fuse3() {
    if command -v fusermount3 &> /dev/null; then
        return 0
    fi
    return 1
}

# Package manager detection
detect_package_manager() {
    if command -v apt-get &> /dev/null; then
        echo "apt"
    elif command -v pacman &> /dev/null; then
        echo "pacman"
    elif command -v dnf &> /dev/null; then
        echo "dnf"
    else
        echo "unknown"
    fi
}

# Check dependencies
NEED_PYTHON_PYQT=false
NEED_FUSE3=false

check_python_pyqt
PYTHON_STATUS=$?
if [ $PYTHON_STATUS -ne 0 ]; then
    NEED_PYTHON_PYQT=true
fi

if ! check_fuse3; then
    NEED_FUSE3=true
fi

# If dependencies are missing, try to install them
if [ "$NEED_PYTHON_PYQT" = true ] || [ "$NEED_FUSE3" = true ]; then
    echo "Fehlende Abhängigkeiten erkannt:"
    if [ "$NEED_PYTHON_PYQT" = true ]; then
        if [ $PYTHON_STATUS -eq 1 ]; then
            echo "  - Python 3"
        fi
        echo "  - PyQt6 (Python-Bibliothek)"
    fi
    if [ "$NEED_FUSE3" = true ]; then
        echo "  - FUSE 3 (fusermount3)"
    fi
    echo ""

    PKG_MANAGER=$(detect_package_manager)

    if [ "$PKG_MANAGER" = "unknown" ]; then
        echo "Ihr Paketmanager konnte nicht automatisch ermittelt werden."
        echo "Bitte installieren Sie die oben genannten Abhängigkeiten manuell über Ihren Paketmanager."
        read -p "Möchten Sie trotzdem mit der Installation des Desktop-Eintrags fortfahren? (j/n): " choice
        case "$choice" in 
            j|J|y|Y ) ;;
            * ) echo "Installation abgebrochen."; exit 1;;
        esac
    else
        echo "Erkannter Paketmanager: $PKG_MANAGER"
        read -p "Möchten Sie, dass diese Abhängigkeiten jetzt automatisch installiert werden? (j/n): " choice
        case "$choice" in 
            j|J|y|Y )
                echo "Starte Installation der Abhängigkeiten (sudo-Rechte erforderlich)..."
                if [ "$PKG_MANAGER" = "apt" ]; then
                    sudo apt update
                    PACKAGES=""
                    [ "$NEED_PYTHON_PYQT" = true ] && PACKAGES="$PACKAGES python3 python3-pyqt6"
                    [ "$NEED_FUSE3" = true ] && PACKAGES="$PACKAGES fuse3"
                    sudo apt install -y $PACKAGES
                elif [ "$PKG_MANAGER" = "pacman" ]; then
                    PACKAGES=""
                    [ "$NEED_PYTHON_PYQT" = true ] && PACKAGES="$PACKAGES python python-pyqt6"
                    [ "$NEED_FUSE3" = true ] && PACKAGES="$PACKAGES fuse3"
                    sudo pacman -Sy --needed --noconfirm $PACKAGES
                elif [ "$PKG_MANAGER" = "dnf" ]; then
                    PACKAGES=""
                    [ "$NEED_PYTHON_PYQT" = true ] && PACKAGES="$PACKAGES python3 python3-pyqt6"
                    [ "$NEED_FUSE3" = true ] && PACKAGES="$PACKAGES fuse3"
                    sudo dnf install -y $PACKAGES
                fi
                
                # Verify installation
                check_python_pyqt
                NEW_PYTHON_STATUS=$?
                if [ $NEW_PYTHON_STATUS -eq 0 ] && check_fuse3; then
                    echo "✓ Alle Abhängigkeiten wurden erfolgreich installiert!"
                else
                    echo "⚠️ Einige Abhängigkeiten konnten nicht installiert werden."
                    read -p "Möchten Sie trotzdem fortfahren? (j/n): " choice_retry
                    case "$choice_retry" in 
                        j|J|y|Y ) ;;
                        * ) echo "Installation abgebrochen."; exit 1;;
                    esac
                fi
                ;;
            * )
                echo "Automatische Installation übersprungen."
                read -p "Möchten Sie trotzdem den Desktop-Eintrag erstellen? (j/n): " choice_skip
                case "$choice_skip" in 
                    j|J|y|Y ) ;;
                    * ) echo "Installation abgebrochen."; exit 1;;
                esac
                ;;
        esac
    fi
else
    echo "✓ Alle benötigten Abhängigkeiten (Python, PyQt6, FUSE 3) sind bereits installiert."
fi

echo ""
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
