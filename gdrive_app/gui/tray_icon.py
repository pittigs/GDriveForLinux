import os
from pathlib import Path
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt

class GDriveTrayIcon(QSystemTrayIcon):
    def __init__(self, config, manager, main_window, parent=None):
        icon_path = str(Path(__file__).parents[1] / "assets" / "icon.svg")
        super().__init__(QIcon(icon_path), parent)
        self.config = config
        self.manager = manager
        self.main_window = main_window
        
        # Link main window
        self.main_window.tray_icon_ref = self
        self.shown_minimize_msg = False
        
        # Setup context menu
        self.menu = QMenu()
        self.setContextMenu(self.menu)
        
        # Connect signals
        self.activated.connect(self.on_tray_activated)
        self.manager.mount_status_changed.connect(self.handle_mount_state_change)
        
        # Initial menu build
        self.rebuild_menu()

    def rebuild_menu(self):
        """Rebuilds the tray icon context menu dynamically based on configured profiles."""
        self.menu.clear()
        
        # 1. Open Dashboard
        open_action = QAction("Übersicht öffnen", self)
        open_action.triggered.connect(self.show_main_window)
        self.menu.addAction(open_action)
        
        # 2. Add Account
        add_action = QAction("Konto hinzufügen...", self)
        add_action.triggered.connect(self.main_window.show_wizard)
        self.menu.addAction(add_action)
        
        self.menu.addSeparator()
        
        # 3. Dynamic Profile List
        profiles = self.config.get_profiles()
        if not profiles:
            empty_action = QAction("Keine Konten eingerichtet", self)
            empty_action.setEnabled(False)
            self.menu.addAction(empty_action)
        else:
            # Subheading
            subhead = QAction("Konten verbinden/trennen:", self)
            subhead.setEnabled(False)
            self.menu.addAction(subhead)
            
            for profile in profiles:
                name = profile.get("name")
                is_mounted = self.manager.is_currently_mounted(name)
                
                status_str = "Verbunden" if is_mounted else "Nicht verbunden"
                # Check for wait network states
                if not is_mounted and self.main_window.desired_mount_states.get(name, False) and self.main_window.network_status_lbl.text() == "Offline":
                    status_str = "Warte auf Netzwerk"
                elif not is_mounted and self.main_window.status_texts.get(name) and self.main_window.status_texts[name].text() == "Verbinde...":
                    status_str = "Verbinde..."

                # Make checkable menu entry
                profile_action = QAction(f"{'  [✓]' if is_mounted else '  [  ]'}  {name} ({status_str})", self)
                profile_action.triggered.connect(lambda checked, p_name=name: self.toggle_profile_mount(p_name))
                self.menu.addAction(profile_action)
                
        self.menu.addSeparator()
        
        # 4. Quit application
        quit_action = QAction("Beenden", self)
        quit_action.triggered.connect(self.quit_application)
        self.menu.addAction(quit_action)

    def handle_mount_state_change(self, profile_name, is_mounted, status_msg):
        # Rebuild tray menu dynamically on mount status updates
        self.rebuild_menu()

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self.show_main_window()

    def show_main_window(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def toggle_profile_mount(self, profile_name):
        # Delegate toggle mount to MainWindow controller
        self.main_window.toggle_mount(profile_name)

    def show_minimize_message(self):
        if not self.shown_minimize_msg:
            self.showMessage(
                "Google Drive Mount Manager",
                "Die Anwendung läuft im Hintergrund im System-Tray.",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )
            self.shown_minimize_msg = True

    def quit_application(self):
        self.hide()
        # Stop prefetcher thread
        if hasattr(self.main_window, 'prefetcher') and self.main_window.prefetcher:
            self.main_window.prefetcher.stop()
        # Cleanly stop all FUSE mount processes before exit
        self.manager.stop_all_mounts()
        QApplication.quit()
