import os
from pathlib import Path

class AutostartManager:
    AUTOSTART_DIR = Path.home() / ".config" / "autostart"
    DESKTOP_FILE = AUTOSTART_DIR / "gdrive-mount.desktop"

    @classmethod
    def set_autostart(cls, enabled):
        """Creates or removes the autostart .desktop file."""
        try:
            if enabled:
                cls.AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
                
                # Get the absolute path to run.sh relative to this file
                project_dir = Path(__file__).parents[2].resolve()
                run_script = project_dir / "run.sh"
                icon_file = project_dir / "gdrive_app" / "assets" / "icon.svg"
                
                desktop_content = f"""[Desktop Entry]
Type=Application
Name=Google Drive Mount
Comment=Startet die Google Drive Verbindung im Hintergrund
Exec={str(run_script)} --background
Icon={str(icon_file)}
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
"""
                with open(cls.DESKTOP_FILE, "w") as f:
                    f.write(desktop_content)
                os.chmod(cls.DESKTOP_FILE, 0o755)
            else:
                if cls.DESKTOP_FILE.exists():
                    cls.DESKTOP_FILE.unlink()
            return True
        except Exception as e:
            print(f"Error setting autostart configuration: {e}")
            return False

    @classmethod
    def is_enabled(cls):
        """Checks if the autostart file currently exists."""
        return cls.DESKTOP_FILE.exists()
