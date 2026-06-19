import os
import sys
import fcntl
import argparse
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QDir

from gdrive_app.core.config import AppConfig
from gdrive_app.core.rclone_manager import RcloneManager
from gdrive_app.gui.main_window import MainWindow
from gdrive_app.gui.wizard import SetupWizard
from gdrive_app.gui.tray_icon import GDriveTrayIcon

# Global reference to lock file to prevent garbage collection
lock_file = None

def acquire_lock():
    """Ensures only a single instance of the application runs on the system."""
    global lock_file
    lock_dir = Path.home() / ".config" / "gdrive-mount"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file_path = lock_dir / "app.lock"
    
    try:
        lock_file = open(lock_file_path, "w")
        # fcntl.LOCK_NB: Non-blocking, LOCK_EX: Exclusive lock
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except IOError:
        return False


class GDriveApp:
    def __init__(self, run_in_background=False):
        self.config = AppConfig()
        self.manager = RcloneManager(self.config)
        self.main_window = None
        self.tray_icon = None
        self.run_in_background = run_in_background

    def run(self):
        # Check if configured
        if not self.manager.is_configured():
            if self.run_in_background:
                # If running in background but not configured, we cannot do anything.
                # Just exit quietly or log it.
                print("App started in background mode but Google Drive is not configured.")
                sys.exit(0)
            else:
                self.show_wizard()
        else:
            self.start_main_flow()

    def show_wizard(self):
        self.wizard = SetupWizard(self.config, self.manager)
        
        # Style wizard (uses same global stylesheets if set, but we set it specifically)
        from gdrive_app.gui.styles import THEME_STYLE
        self.wizard.setStyleSheet(THEME_STYLE)
        
        result = self.wizard.exec()
        
        if result == SetupWizard.DialogCode.Accepted:
            # Check if user checked "Mount now"
            mount_now = self.wizard.property("mount_now")
            
            # Start normal flow
            self.start_main_flow()
            
            if mount_now:
                profile_name = self.wizard.property("profile_name")
                if profile_name:
                    self.manager.start_mount(profile_name)
                    # Open folder in background
                    if self.main_window:
                        profile = self.config.get_profile(profile_name)
                        if profile:
                            self.main_window.open_mount_folder(profile.get("mount_path"))
        else:
            sys.exit(0)

    def start_main_flow(self):
        # Create Main Dashboard Window
        self.main_window = MainWindow(self.config, self.manager)
        
        # Link parents
        self.main_window.parent_app = self
        
        # Create Tray Icon
        self.tray_icon = GDriveTrayIcon(self.config, self.manager, self.main_window)
        self.tray_icon.show()
        
        # Start mount on start for each profile configured to mount on start
        for profile in self.config.get_profiles():
            if profile.get("mount_on_start", True):
                self.manager.start_mount(profile.get("name"))
            
        # Show window if not background mode
        if not self.run_in_background:
            self.main_window.show()


def main():
    # Parse CLI Arguments
    parser = argparse.ArgumentParser(description="Google Drive Mount utility for Linux.")
    parser.add_argument(
        "--background", 
        action="store_true", 
        help="Starts the application minimized in the system tray and runs configured mounts."
    )
    args = parser.parse_args()

    # 1. Single Instance Check
    if not acquire_lock():
        # App is already running, show warning if not started in background
        if not args.background:
            app = QApplication(sys.argv)
            QMessageBox.warning(
                None, 
                "Bereits aktiv", 
                "Google Drive Mount läuft bereits im Hintergrund.\n"
                "Bitte prüfen Sie Ihr System-Tray-Icon."
            )
            sys.exit(0)
        else:
            print("Google Drive Mount ist bereits aktiv. Beende Hintergrundprozess.")
            sys.exit(0)

    # 2. Init Qt Application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) # Prevent quitting when closing dashboard window
    
    # 3. Start App
    gdrive_app = GDriveApp(run_in_background=args.background)
    gdrive_app.run()
    
    # Run loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
