import os
import sys
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QTabWidget, QCheckBox, 
                             QLineEdit, QFileDialog, QComboBox, QTextEdit, 
                             QProgressBar, QFrame, QMessageBox, QScrollArea,
                             QSystemTrayIcon)
from PyQt6.QtCore import Qt, QUrl, pyqtSlot, QThread, pyqtSignal, QTimer, QProcess
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtSvgWidgets import QSvgWidget

from gdrive_app.core.autostart import AutostartManager
from gdrive_app.core.network import check_internet
from gdrive_app.gui.styles import THEME_STYLE
from gdrive_app.gui.profile_dialog import ProfileDialog
from gdrive_app.gui.wizard import SetupWizard

class StatsWorker(QThread):
    stats_loaded = pyqtSignal(str, dict) # (profile_name, stats)
    stats_failed = pyqtSignal(str) # (profile_name)

    def __init__(self, manager, profile_name):
        super().__init__()
        self.manager = manager
        self.profile_name = profile_name

    def run(self):
        stats = self.manager.get_space_stats(self.profile_name)
        if stats:
            self.stats_loaded.emit(self.profile_name, stats)
        else:
            self.stats_failed.emit(self.profile_name)


class MainWindow(QMainWindow):
    def __init__(self, config, manager, parent=None):
        super().__init__(parent)
        self.config = config
        self.manager = manager
        
        self.setWindowTitle("Google Drive Mount Manager")
        self.setWindowIcon(QIcon(str(Path(__file__).parents[1] / "assets" / "icon.svg")))
        self.resize(680, 520)
        self.setStyleSheet(THEME_STYLE)
        
        # Central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Layout
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Track states and worker threads
        self.stats_workers = {} # profile_name -> StatsWorker
        self.is_mounted_cache = {} # profile_name -> bool
        self.desired_mount_states = {} # profile_name -> bool (should it be mounted?)
        self.logs = {} # profile_name -> list of logs
        self.was_offline = False
        
        # UI Reference Dictionaries
        self.cards = {}
        self.status_dots = {}
        self.status_texts = {}
        self.toggle_btns = {}
        self.open_folder_btns = {}
        self.storage_progress_bars = {}
        self.storage_details = {}
        
        # Header (Logo & App Name & Connection status & Add Account)
        self.setup_header()
        
        # Tabs
        self.tabs = QTabWidget()
        self.setup_dashboard_tab()
        self.setup_logs_tab()
        self.setup_settings_tab()
        self.main_layout.addWidget(self.tabs)
        
        # Connect signals
        self.manager.mount_status_changed.connect(self.on_mount_status_changed)
        self.manager.log_received.connect(self.append_log)
        
        # Timers
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.check_actual_mount_statuses)
        self.status_timer.start(2000) # Check mount states every 2s
        
        self.network_timer = QTimer(self)
        self.network_timer.timeout.connect(self.check_network_status)
        self.network_timer.start(5000) # Check network every 5s
        
        # Initial run
        self.check_network_status()
        self.rebuild_profile_cards()
        self.check_actual_mount_statuses()

    def setup_header(self):
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 10)
        
        self.logo_widget = QSvgWidget(str(Path(__file__).parents[1] / "assets" / "icon.svg"))
        self.logo_widget.setFixedSize(36, 36)
        header_layout.addWidget(self.logo_widget)
        
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        
        title_lbl = QLabel("Google Drive Verbindung")
        title_lbl.setObjectName("Title")
        title_layout.addWidget(title_lbl)
        
        self.subtitle_lbl = QLabel("Multi-Account Konfiguration & Steuerung")
        self.subtitle_lbl.setObjectName("SubTitle")
        title_layout.addWidget(self.subtitle_lbl)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # Global Network Status Indicator
        self.network_status_lbl = QLabel("Online")
        self.network_status_lbl.setStyleSheet("color: #34A853; font-weight: bold; margin-right: 10px;")
        header_layout.addWidget(self.network_status_lbl)
        
        # Add Account button
        self.add_account_btn = QPushButton("+ Konto hinzufügen")
        self.add_account_btn.setObjectName("Primary")
        self.add_account_btn.clicked.connect(self.show_wizard)
        header_layout.addWidget(self.add_account_btn)
        
        self.main_layout.addLayout(header_layout)

    def setup_dashboard_tab(self):
        self.dashboard_tab = QWidget()
        layout = QVBoxLayout(self.dashboard_tab)
        layout.setContentsMargins(5, 10, 5, 5)
        
        # Scroll Area for Profile Cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.scroll_content)
        self.cards_layout.setSpacing(15)
        
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)
        self.tabs.addTab(self.dashboard_tab, "Übersicht")

    def rebuild_profile_cards(self):
        """Clears and rebuilds the profile cards inside the scroll area layout."""
        # Clear existing layout fully (widgets and spacers)
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        self.cards.clear()
        self.status_dots.clear()
        self.status_texts.clear()
        self.toggle_btns.clear()
        self.open_folder_btns.clear()
        self.storage_progress_bars.clear()
        self.storage_details.clear()
        
        profiles = self.config.get_profiles()
        
        if not profiles:
            # Show empty state label
            empty_lbl = QLabel(
                "Keine Google Drive Konten eingerichtet.\n"
                "Klicken Sie oben auf '+ Konto hinzufügen', um zu starten."
            )
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("color: #a0a0a9; font-size: 14px; margin-top: 50px;")
            empty_lbl.setObjectName("EmptyLabel")
            self.cards_layout.addWidget(empty_lbl)
            self.cards_layout.addStretch()
            return
            
        # Recreate profile cards
        for idx, profile in enumerate(profiles):
            name = profile.get("name")
            mount_path = profile.get("mount_path")
            
            # Setup desired mount states cache
            if name not in self.desired_mount_states:
                self.desired_mount_states[name] = profile.get("mount_on_start", True)
                
            if name not in self.is_mounted_cache:
                self.is_mounted_cache[name] = None

            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(10)
            card_layout.setContentsMargins(15, 15, 15, 15)
            
            # Top row: Profile Name & Status & Actions
            top_row = QHBoxLayout()
            
            # Status Indicator
            dot = QFrame()
            dot.setObjectName("StatusDot")
            dot.setStyleSheet("#StatusDot { background-color: #EA4335; border-radius: 6px; }")
            top_row.addWidget(dot)
            self.status_dots[name] = dot
            
            status_txt = QLabel("Nicht verbunden")
            status_txt.setObjectName("StatusLabel")
            status_txt.setStyleSheet("color: #EA4335;")
            top_row.addWidget(status_txt)
            self.status_texts[name] = status_txt
            
            # Name
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet("font-weight: bold; font-size: 15px; margin-left: 10px;")
            top_row.addWidget(name_lbl)
            top_row.addStretch()
            
            # Actions
            toggle_btn = QPushButton("Verbinden")
            toggle_btn.setObjectName("Primary")
            toggle_btn.clicked.connect(lambda checked, p_name=name: self.toggle_mount(p_name))
            top_row.addWidget(toggle_btn)
            self.toggle_btns[name] = toggle_btn
            
            open_folder_btn = QPushButton("Ordner öffnen")
            open_folder_btn.clicked.connect(lambda checked, path=mount_path: self.open_mount_folder(path))
            open_folder_btn.setEnabled(False)
            top_row.addWidget(open_folder_btn)
            self.open_folder_btns[name] = open_folder_btn
            
            edit_btn = QPushButton("Bearbeiten")
            edit_btn.clicked.connect(lambda checked, p_name=name: self.edit_profile(p_name))
            top_row.addWidget(edit_btn)
            
            delete_btn = QPushButton("Löschen")
            delete_btn.setObjectName("Destructive")
            delete_btn.clicked.connect(lambda checked, p_name=name: self.delete_profile(p_name))
            top_row.addWidget(delete_btn)
            
            card_layout.addLayout(top_row)
            
            # Middle row: Path info & Caching status
            keep_cached = profile.get("keep_cached", False)
            cache_status = "Aktiv (Offline-Verfügbarkeit)" if keep_cached else "Inaktiv (Streaming)"
            path_lbl = QLabel(f"Zielordner: {mount_path}  |  Lokal speichern: {cache_status}")
            path_lbl.setStyleSheet("color: #a0a0a9; font-size: 11px;")
            card_layout.addWidget(path_lbl)
            
            # Space Stats row
            storage_progress = QProgressBar()
            storage_progress.setObjectName("DiskUsage")
            storage_progress.setValue(0)
            storage_progress.setFormat("Quota ausstehend...")
            card_layout.addWidget(storage_progress)
            self.storage_progress_bars[name] = storage_progress
            
            storage_detail_lbl = QLabel("Speicherplatzinformationen ausstehend...")
            storage_detail_lbl.setStyleSheet("color: #8e8e93; font-size: 11px;")
            card_layout.addWidget(storage_detail_lbl)
            self.storage_details[name] = storage_detail_lbl
            
            self.cards_layout.addWidget(card)
            self.cards[name] = card
            
            # Re-initialize logs cache
            if name not in self.logs:
                self.logs[name] = ""
                
        # Add stretch at the end to push cards to the top
        self.cards_layout.addStretch()
                
        # Re-populate log combo box
        self.update_log_combo()

    def setup_logs_tab(self):
        self.logs_tab = QWidget()
        layout = QVBoxLayout(self.logs_tab)
        layout.setContentsMargins(10, 15, 10, 10)
        
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Konto-Protokoll filtern:"))
        
        self.log_combo = QComboBox()
        self.log_combo.currentIndexChanged.connect(self.switch_log_view)
        filter_layout.addWidget(self.log_combo)
        filter_layout.addStretch()
        
        clear_btn = QPushButton("Protokoll leeren")
        clear_btn.clicked.connect(self.clear_logs)
        filter_layout.addWidget(clear_btn)
        layout.addLayout(filter_layout)
        
        self.log_console = QTextEdit()
        self.log_console.setObjectName("LogConsole")
        self.log_console.setReadOnly(True)
        layout.addWidget(self.log_console)
        
        self.tabs.addTab(self.logs_tab, "Protokoll")

    def update_log_combo(self):
        self.log_combo.blockSignals(True)
        self.log_combo.clear()
        self.log_combo.addItem("Alle Konten", "all")
        for profile in self.config.get_profiles():
            name = profile.get("name")
            self.log_combo.addItem(name, name)
        self.log_combo.blockSignals(False)
        self.switch_log_view()

    def setup_settings_tab(self):
        self.settings_tab = QWidget()
        layout = QVBoxLayout(self.settings_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(QLabel("Globale Einstellungen").setObjectName("Header"))
        
        self.autostart_cb = QCheckBox("Google Drive Mount Utility beim Systemstart ausführen")
        self.autostart_cb.setChecked(self.config.autostart)
        self.autostart_cb.stateChanged.connect(self.toggle_global_autostart)
        layout.addWidget(self.autostart_cb)
        
        layout.addSpacing(10)
        layout.addWidget(QLabel("Rclone ausführbare Datei (Pfad):").setObjectName("Header"))
        
        rclone_path_row = QHBoxLayout()
        self.rclone_path_input = QLineEdit()
        self.rclone_path_input.setText(self.config.rclone_path)
        rclone_path_row.addWidget(self.rclone_path_input)
        
        save_path_btn = QPushButton("Übernehmen")
        save_path_btn.clicked.connect(self.apply_rclone_path)
        rclone_path_row.addWidget(save_path_btn)
        layout.addLayout(rclone_path_row)
        
        layout.addStretch()
        self.tabs.addTab(self.settings_tab, "Einstellungen")

    def show_wizard(self):
        self.wizard = SetupWizard(self.config, self.manager)
        result = self.wizard.exec()
        if result == SetupWizard.DialogCode.Accepted:
            # Rebuild cards to show the newly added account
            self.rebuild_profile_cards()
            
            # Start mounting if requested
            mount_now = self.wizard.property("mount_now")
            profile_name = self.wizard.property("profile_name")
            if mount_now and profile_name:
                self.manager.start_mount(profile_name)
                
            # If minimized, tray icon updates automatically because signals wire in MainWindow
            if hasattr(self, 'tray_icon_ref') and self.tray_icon_ref:
                self.tray_icon_ref.rebuild_menu()

    def edit_profile(self, profile_name):
        profile_data = self.config.get_profile(profile_name)
        if not profile_data:
            return
            
        # Verify it is not mounted before editing
        if self.manager.is_currently_mounted(profile_name):
            QMessageBox.warning(self, "Konto aktiv", "Bitte trennen Sie die Verbindung, bevor Sie Einstellungen ändern.")
            return
            
        dialog = ProfileDialog(self.config, profile_data, self)
        if dialog.exec() == ProfileDialog.DialogCode.Accepted:
            updated_data = dialog.get_data()
            
            # Apply changes
            self.config.update_profile(profile_name, updated_data)
            
            # Handle renaming in active desired states
            new_name = updated_data.get("name")
            if new_name != profile_name:
                if profile_name in self.desired_mount_states:
                    self.desired_mount_states[new_name] = self.desired_mount_states[profile_name]
                    del self.desired_mount_states[profile_name]
                if profile_name in self.is_mounted_cache:
                    self.is_mounted_cache[new_name] = self.is_mounted_cache[profile_name]
                    del self.is_mounted_cache[profile_name]
                if profile_name in self.logs:
                    self.logs[new_name] = self.logs[profile_name]
                    del self.logs[profile_name]
                    
            # Rebuild UI
            self.rebuild_profile_cards()
            self.check_actual_mount_statuses()
            
            if hasattr(self, 'tray_icon_ref') and self.tray_icon_ref:
                self.tray_icon_ref.rebuild_menu()

    def delete_profile(self, profile_name):
        profile = self.config.get_profile(profile_name)
        if not profile:
            return
            
        reply = QMessageBox.question(
            self, 
            "Konto löschen", 
            f"Möchten Sie das Profil '{profile_name}' wirklich löschen?\n"
            "Die rclone-Konfiguration wird dauerhaft entfernt.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Stop mount and remove from sidebar
            self.manager.stop_mount(profile_name)
            
            from gdrive_app.core.sidebar import remove_from_sidebar
            remove_from_sidebar(profile.get("mount_path"))
            
            # Delete configuration from rclone
            self.manager.remove_configuration(profile.get("remote_name"))
            
            # Delete profile from config
            self.config.remove_profile(profile_name)
            
            if profile_name in self.desired_mount_states:
                del self.desired_mount_states[profile_name]
            if profile_name in self.is_mounted_cache:
                del self.is_mounted_cache[profile_name]
            if profile_name in self.logs:
                del self.logs[profile_name]
                
            # Rebuild GUI
            self.rebuild_profile_cards()
            
            if hasattr(self, 'tray_icon_ref') and self.tray_icon_ref:
                self.tray_icon_ref.rebuild_menu()

    def toggle_mount(self, profile_name):
        is_mounted = self.manager.is_currently_mounted(profile_name)
        
        # Disable button during toggle transition
        if profile_name in self.toggle_btns:
            self.toggle_btns[profile_name].setEnabled(False)
            
        if is_mounted:
            self.desired_mount_states[profile_name] = False
            self.manager.stop_mount(profile_name)
        else:
            self.desired_mount_states[profile_name] = True
            
            # Check network before starting mount
            if self.network_status_lbl.text() == "Offline":
                if profile_name in self.status_texts:
                    self.status_texts[profile_name].setText("Warte auf Netzwerk...")
                    self.status_texts[profile_name].setStyleSheet("color: #FBBC05;")
                if profile_name in self.status_dots:
                    self.status_dots[profile_name].setStyleSheet("#StatusDot { background-color: #FBBC05; border-radius: 6px; }")
                if profile_name in self.toggle_btns:
                    self.toggle_btns[profile_name].setEnabled(True)
                    self.toggle_btns[profile_name].setText("Trennen")
            else:
                self.manager.start_mount(profile_name)

    def open_mount_folder(self, mount_path):
        if os.path.exists(mount_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(mount_path))

    @pyqtSlot(str, bool, str)
    def on_mount_status_changed(self, profile_name, is_mounted, status_msg):
        # Prevent updates if profile card is deleted
        if profile_name not in self.cards:
            return
            
        # Get elements
        dot = self.status_dots.get(profile_name)
        status_lbl = self.status_texts.get(profile_name)
        toggle_btn = self.toggle_btns.get(profile_name)
        open_folder_btn = self.open_folder_btns.get(profile_name)
        
        if not all([dot, status_lbl, toggle_btn, open_folder_btn]):
            return
            
        toggle_btn.setEnabled(True)
        
        state_changed = (is_mounted != self.is_mounted_cache.get(profile_name))
        self.is_mounted_cache[profile_name] = is_mounted
        
        # Retrieve profile
        profile = self.config.get_profile(profile_name)
        mount_path = profile.get("mount_path") if profile else ""
        
        if is_mounted:
            dot.setStyleSheet("#StatusDot { background-color: #34A853; border-radius: 6px; }")
            status_lbl.setText("Verbunden")
            status_lbl.setStyleSheet("color: #34A853;")
            toggle_btn.setText("Trennen")
            open_folder_btn.setEnabled(True)
            
            if state_changed:
                self.refresh_stats(profile_name)
                # Add to sidebar
                from gdrive_app.core.sidebar import add_to_sidebar
                add_to_sidebar(mount_path)
                
                # Show tray notification
                if hasattr(self, 'tray_icon_ref') and self.tray_icon_ref:
                    self.tray_icon_ref.showMessage(
                        "Google Drive verbunden",
                        f"Konto '{profile_name}' wurde erfolgreich gemountet.",
                        QSystemTrayIcon.MessageIcon.Information,
                        3000
                    )
        else:
            if self.network_status_lbl.text() == "Offline" and self.desired_mount_states.get(profile_name, False):
                dot.setStyleSheet("#StatusDot { background-color: #FBBC05; border-radius: 6px; }")
                status_lbl.setText("Warte auf Netzwerk...")
                status_lbl.setStyleSheet("color: #FBBC05;")
                toggle_btn.setText("Trennen")
                open_folder_btn.setEnabled(False)
            elif status_msg == "Verbinde...":
                dot.setStyleSheet("#StatusDot { background-color: #FBBC05; border-radius: 6px; }")
                status_lbl.setText("Verbinde...")
                status_lbl.setStyleSheet("color: #FBBC05;")
                toggle_btn.setText("Verbinde...")
                toggle_btn.setEnabled(False)
                open_folder_btn.setEnabled(False)
            else:
                dot.setStyleSheet("#StatusDot { background-color: #EA4335; border-radius: 6px; }")
                status_lbl.setText(status_msg)
                status_lbl.setStyleSheet("color: #EA4335;")
                toggle_btn.setText("Verbinden")
                open_folder_btn.setEnabled(False)
                
                if state_changed:
                    from gdrive_app.core.sidebar import remove_from_sidebar
                    remove_from_sidebar(mount_path)
                    
                    # Show tray notification if previously connected
                    if hasattr(self, 'tray_icon_ref') and self.tray_icon_ref:
                        self.tray_icon_ref.showMessage(
                            "Google Drive getrennt",
                            f"Die Verbindung für '{profile_name}' wurde beendet.",
                            QSystemTrayIcon.MessageIcon.Information,
                            2000
                        )

    def check_actual_mount_statuses(self):
        """Checks the real FUSE states of all profile directories."""
        for profile in self.config.get_profiles():
            name = profile.get("name")
            is_mounted = self.manager.is_currently_mounted(name)
            
            # Skip overriding "Verbinde..." status if mounting process is starting
            current_status = self.status_texts.get(name)
            if current_status:
                current_text = current_status.text()
                if not is_mounted and current_text in ["Verbinde...", "Warte auf Netzwerk..."]:
                    process = self.manager.mount_processes.get(name)
                    if process and process.state() == QProcess.ProcessState.NotRunning:
                        self.on_mount_status_changed(name, False, "Verbindung fehlgeschlagen")
                    continue
                    
            self.on_mount_status_changed(name, is_mounted, "Nicht verbunden" if not is_mounted else "Verbunden")

    def check_network_status(self):
        """Monitors system internet connectivity and handles auto-reconnections."""
        is_online = check_internet()
        
        if is_online:
            self.network_status_lbl.setText("Online")
            self.network_status_lbl.setStyleSheet("color: #34A853; font-weight: bold; margin-right: 10px;")
            
            # Auto reconnect transitioned from offline
            if self.was_offline:
                self.log_console.append("[System] Netzwerkverbindung wiederhergestellt. Starte ausstehende Mounts...\n")
                self.was_offline = False
                
                for profile in self.config.get_profiles():
                    name = profile.get("name")
                    # If the user desired to connect this profile, start it up now!
                    if self.desired_mount_states.get(name, False):
                        if not self.manager.is_currently_mounted(name):
                            self.manager.start_mount(name)
        else:
            self.network_status_lbl.setText("Offline")
            self.network_status_lbl.setStyleSheet("color: #EA4335; font-weight: bold; margin-right: 10px;")
            self.was_offline = True
            
            # Show offline statuses
            for profile in self.config.get_profiles():
                name = profile.get("name")
                if self.desired_mount_states.get(name, False) and not self.manager.is_currently_mounted(name):
                    self.on_mount_status_changed(name, False, "Warte auf Netzwerk...")

    @pyqtSlot(str)
    def refresh_stats(self, profile_name):
        if not self.manager.is_configured():
            return
            
        # Prevent overlapping workers
        if profile_name in self.stats_workers and self.stats_workers[profile_name].isRunning():
            return
            
        progress = self.storage_progress_bars.get(profile_name)
        detail = self.storage_details.get(profile_name)
        
        if progress:
            progress.setValue(0)
            progress.setFormat("Hole Quota...")
            
        worker = StatsWorker(self.manager, profile_name)
        worker.stats_loaded.connect(self.on_stats_loaded)
        worker.stats_failed.connect(self.on_stats_failed)
        self.stats_workers[profile_name] = worker
        worker.start()

    @pyqtSlot(str, dict)
    def on_stats_loaded(self, profile_name, stats):
        # Remove reference
        if profile_name in self.stats_workers:
            del self.stats_workers[profile_name]
            
        progress = self.storage_progress_bars.get(profile_name)
        detail = self.storage_details.get(profile_name)
        
        if not progress or not detail:
            return
            
        total = stats.get("total", 0)
        used = stats.get("used", 0)
        free = stats.get("free", 0)
        
        if total > 0:
            percent = int((used / total) * 100)
            progress.setValue(percent)
            progress.setFormat(f"{percent}% belegt")
            
            total_gb = total / (1024**3)
            used_gb = used / (1024**3)
            free_gb = free / (1024**3)
            detail.setText(f"Belegt: {used_gb:.2f} GB von {total_gb:.2f} GB  |  Frei: {free_gb:.2f} GB")
        else:
            progress.setValue(0)
            progress.setFormat("Unbegrenzt")
            used_gb = used / (1024**3)
            detail.setText(f"Belegt: {used_gb:.2f} GB (Unbegrenzter Tarif)")

    @pyqtSlot(str)
    def on_stats_failed(self, profile_name):
        if profile_name in self.stats_workers:
            del self.stats_workers[profile_name]
            
        progress = self.storage_progress_bars.get(profile_name)
        detail = self.storage_details.get(profile_name)
        
        if not progress or not detail:
            return
            
        progress.setValue(0)
        progress.setFormat("Quota fehlgeschlagen")
        
        # Disk fallback check
        profile = self.config.get_profile(profile_name)
        if profile and self.manager.is_currently_mounted(profile_name):
            try:
                usage = shutil.disk_usage(profile.get("mount_path"))
                total_gb = usage.total / (1024**3)
                used_gb = usage.used / (1024**3)
                free_gb = usage.free / (1024**3)
                percent = int((usage.used / usage.total) * 100)
                
                progress.setValue(percent)
                progress.setFormat(f"{percent}% belegt (Lokale Schätzung)")
                detail.setText(f"Belegt: {used_gb:.2f} GB von {total_gb:.2f} GB  |  Frei: {free_gb:.2f} GB")
            except Exception:
                detail.setText("Fehler beim Laden der Speicherplatzinformationen.")
        else:
            detail.setText("Keine Speicherplatzdaten verfügbar.")

    @pyqtSlot(str, str)
    def append_log(self, profile_name, text):
        # Accumulate logs per profile
        if profile_name not in self.logs:
            self.logs[profile_name] = ""
        self.logs[profile_name] += text
        
        # Limit log length
        if len(self.logs[profile_name]) > 50000:
            self.logs[profile_name] = self.logs[profile_name][-30000:]
            
        # Update text console if current filter fits
        current_filter = self.log_combo.currentData()
        if current_filter == "all":
            self.log_console.append(f"[{profile_name}] {text}")
        elif current_filter == profile_name:
            self.log_console.append(text)

    def switch_log_view(self):
        self.log_console.clear()
        filter_name = self.log_combo.currentData()
        
        if filter_name == "all":
            self.log_console.append("[System] Zeige Logs aller Konten an...")
            # We can merge them chronologically or show what we have
            for name, content in self.logs.items():
                if content:
                    lines = content.strip().split('\n')
                    prefix_lines = "\n".join(f"[{name}] {l}" for l in lines)
                    self.log_console.append(prefix_lines)
        else:
            self.log_console.append(f"[System] Zeige Logs für Konto '{filter_name}'...")
            self.log_console.append(self.logs.get(filter_name, ""))

    def clear_logs(self):
        filter_name = self.log_combo.currentData()
        if filter_name == "all":
            for name in self.logs:
                self.logs[name] = ""
        else:
            if filter_name in self.logs:
                self.logs[filter_name] = ""
        self.log_console.clear()

    def toggle_global_autostart(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self.config.autostart = enabled
        AutostartManager.set_autostart(enabled)

    def apply_rclone_path(self):
        path = self.rclone_path_input.text().strip()
        if not path or (os.path.exists(path) and os.access(path, os.X_OK)):
            self.config.rclone_path = path
            QMessageBox.information(self, "Erfolg", "Pfad zur ausführbaren rclone-Datei wurde aktualisiert.")
        else:
            QMessageBox.warning(self, "Ungültiger Pfad", "Der angegebene Pfad existiert nicht oder ist nicht ausführbar.")

    def closeEvent(self, event):
        # Hide to tray rather than exiting
        if self.config.get_profiles():
            event.ignore()
            self.hide()
            if hasattr(self, 'tray_icon_ref') and self.tray_icon_ref:
                self.tray_icon_ref.show_minimize_message()
        else:
            event.accept()
