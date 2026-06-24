import os
import re
from pathlib import Path
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QComboBox, QCheckBox, 
                             QFileDialog, QMessageBox, QFrame, QTabWidget, 
                             QGroupBox, QWidget)
from PyQt6.QtCore import Qt, QUrl, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from gdrive_app.gui.styles import THEME_STYLE

class ProfileDialog(QDialog):
    def __init__(self, config, profile_data, parent=None):
        super().__init__(parent)
        self.config = config
        self.manager = parent.manager if parent else None
        self.original_name = profile_data.get("name")
        self.profile_data = profile_data.copy()
        
        self.setWindowTitle("Konto-Einstellungen bearbeiten")
        self.setStyleSheet(THEME_STYLE)
        self.resize(520, 560)
        
        # Auth-state
        self.auth_url = ""
        
        # Layout
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        self.header_lbl = QLabel(f"Einstellungen für '{self.original_name}'")
        self.header_lbl.setObjectName("Title")
        self.layout.addWidget(self.header_lbl)
        
        # Create Tab Widget
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)
        
        # Setup Tab 1: Allgemein
        self.setup_general_tab()
        
        # Setup Tab 2: API & Performance
        self.setup_performance_tab()
        
        # Bottom Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        
        save_btn = QPushButton("Speichern")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self.save_settings)
        btn_row.addWidget(save_btn)
        
        self.layout.addLayout(btn_row)

    def setup_general_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(10, 15, 10, 10)
        
        card = QFrame()
        card.setObjectName("InnerCard")
        card.setStyleSheet("#InnerCard { background-color: #1a1a1e; border: 1px solid #2d2d34; border-radius: 8px; }")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        
        # 1. Profile Name
        name_lbl = QLabel("Profil-Name:")
        card_layout.addWidget(name_lbl)
        self.name_input = QLineEdit()
        self.name_input.setText(self.profile_data.get("name"))
        card_layout.addWidget(self.name_input)
        
        # 2. Mount Path
        path_lbl = QLabel("Lokaler Mount-Ordner:")
        card_layout.addWidget(path_lbl)
        
        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setText(self.profile_data.get("mount_path"))
        self.path_input.setReadOnly(True)
        path_row.addWidget(self.path_input)
        
        browse_btn = QPushButton("Ändern...")
        browse_btn.clicked.connect(self.browse_folder)
        path_row.addWidget(browse_btn)
        card_layout.addLayout(path_row)
        
        # 3. Cache Mode
        cache_lbl = QLabel("VFS Cache-Modus:")
        card_layout.addWidget(cache_lbl)
        self.cache_combo = QComboBox()
        self.cache_combo.addItems(["full (Empfohlen - Windows-artig)", "writes (Bessere Performance)", "minimal", "off"])
        current_cache = self.profile_data.get("cache_mode", "full")
        if current_cache == "full":
            self.cache_combo.setCurrentIndex(0)
        elif current_cache == "writes":
            self.cache_combo.setCurrentIndex(1)
        elif current_cache == "minimal":
            self.cache_combo.setCurrentIndex(2)
        else:
            self.cache_combo.setCurrentIndex(3)
        card_layout.addWidget(self.cache_combo)
        
        # 4. Checkboxes
        self.mount_on_start_cb = QCheckBox("Google Drive beim App-Start automatisch mounten")
        self.mount_on_start_cb.setChecked(self.profile_data.get("mount_on_start", True))
        card_layout.addWidget(self.mount_on_start_cb)
        
        self.keep_cached_cb = QCheckBox("Dateien dauerhaft lokal speichern (Offline-Verfügbarkeit)")
        self.keep_cached_cb.setChecked(self.profile_data.get("keep_cached", False))
        card_layout.addWidget(self.keep_cached_cb)
        
        self.prefetch_cb = QCheckBox("Intelligentes Vorab-Herunterladen (Prediction)")
        self.prefetch_cb.setChecked(self.profile_data.get("prefetch_enabled", True))
        card_layout.addWidget(self.prefetch_cb)
        
        layout.addWidget(card)
        layout.addStretch()
        self.tab_widget.addTab(tab, "Allgemein")

    def setup_performance_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(10, 15, 10, 10)
        
        # 1. API Credentials Group
        api_group = QGroupBox("Google Drive API-Zugangsdaten")
        api_layout = QVBoxLayout(api_group)
        api_layout.setSpacing(8)
        
        info_lbl = QLabel(
            "Verwenden Sie eigene Google-API-Zugangsdaten, um Google-Drosselungen zu "
            "verhindern und die Performance des Windows-Clients zu erreichen."
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("color: #a0a0a9; font-size: 11px;")
        api_layout.addWidget(info_lbl)
        
        self.use_custom_api_cb = QCheckBox("Eigene Google API-Zugangsdaten verwenden")
        self.use_custom_api_cb.setChecked(self.profile_data.get("use_custom_api", False))
        self.use_custom_api_cb.stateChanged.connect(self.toggle_api_inputs)
        api_layout.addWidget(self.use_custom_api_cb)
        
        # API credentials inputs container
        self.api_inputs_widget = QWidget()
        api_inputs_layout = QVBoxLayout(self.api_inputs_widget)
        api_inputs_layout.setContentsMargins(0, 0, 0, 0)
        api_inputs_layout.setSpacing(6)
        
        # Client ID & Secret
        api_inputs_layout.addWidget(QLabel("Client-ID:"))
        self.client_id_input = QLineEdit()
        api_inputs_layout.addWidget(self.client_id_input)
        
        api_inputs_layout.addWidget(QLabel("Client-Secret:"))
        self.client_secret_input = QLineEdit()
        api_inputs_layout.addWidget(self.client_secret_input)
        
        # Help link
        help_btn = QPushButton("Wie erstelle ich meine eigenen API-Zugangsdaten? (Anleitung öffnen)")
        help_btn.setStyleSheet("color: #4285F4; text-decoration: underline; background: transparent; border: none; font-size: 11px; text-align: left; padding: 0;")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(self.open_api_guide)
        api_inputs_layout.addWidget(help_btn)
        
        # Load existing credentials from rclone.conf
        remote_name = self.profile_data.get("remote_name")
        if self.manager:
            cid, csec = self.manager.get_remote_credentials(remote_name)
            self.client_id_input.setText(cid)
            self.client_secret_input.setText(csec)
            
        # Re-auth section
        self.reauth_frame = QFrame()
        self.reauth_frame.setStyleSheet("background-color: #1a1a1f; border: 1px dashed #4285F4; border-radius: 6px; padding: 8px;")
        reauth_layout = QVBoxLayout(self.reauth_frame)
        reauth_layout.setSpacing(6)
        
        self.reauth_status_lbl = QLabel("Anmeldung erforderlich nach Änderung der Zugangsdaten.")
        self.reauth_status_lbl.setStyleSheet("color: #a0a0a9; font-size: 11px;")
        self.reauth_status_lbl.setWordWrap(True)
        reauth_layout.addWidget(self.reauth_status_lbl)
        
        reauth_btn_row = QHBoxLayout()
        self.reauth_btn = QPushButton("Verbindung neu autorisieren")
        self.reauth_btn.setObjectName("Secondary")
        self.reauth_btn.clicked.connect(self.start_reauth)
        reauth_btn_row.addWidget(self.reauth_btn)
        
        self.reauth_link_btn = QPushButton("Link manuell öffnen")
        self.reauth_link_btn.setStyleSheet("color: #4285F4; text-decoration: underline; background: transparent; border: none; font-size: 11px; font-weight: bold;")
        self.reauth_link_btn.setVisible(False)
        self.reauth_link_btn.clicked.connect(self.open_reauth_link_manually)
        reauth_btn_row.addWidget(self.reauth_link_btn)
        reauth_layout.addLayout(reauth_btn_row)
        
        api_inputs_layout.addWidget(self.reauth_frame)
        api_layout.addWidget(self.api_inputs_widget)
        
        self.api_inputs_widget.setVisible(self.use_custom_api_cb.isChecked())
        layout.addWidget(api_group)
        
        # 2. Performance Parameters Group
        perf_group = QGroupBox("Erweiterte Performance-Parameter")
        perf_layout = QVBoxLayout(perf_group)
        perf_layout.setSpacing(8)
        
        params_row1 = QHBoxLayout()
        
        # Upload chunk size
        chunk_col = QVBoxLayout()
        chunk_col.addWidget(QLabel("Upload-Chunk-Größe:"))
        self.chunk_combo = QComboBox()
        self.chunk_combo.addItems(["8 MB (Standard)", "16 MB", "32 MB", "64 MB (Empfohlen)", "128 MB", "256 MB"])
        # Set selection
        current_chunk = self.profile_data.get("drive_chunk_size", "64M")
        chunk_map = {"8M": 0, "16M": 1, "32M": 2, "64M": 3, "128M": 4, "256M": 5}
        self.chunk_combo.setCurrentIndex(chunk_map.get(current_chunk, 3))
        chunk_col.addWidget(self.chunk_combo)
        params_row1.addLayout(chunk_col)
        
        # Buffer size
        buf_col = QVBoxLayout()
        buf_col.addWidget(QLabel("Lese-Puffer (Buffer Size):"))
        self.buf_combo = QComboBox()
        self.buf_combo.addItems(["16 MB", "32 MB", "64 MB (Empfohlen)", "128 MB", "256 MB"])
        current_buf = self.profile_data.get("buffer_size", "64M")
        buf_map = {"16M": 0, "32M": 1, "64M": 2, "128M": 3, "256M": 4}
        self.buf_combo.setCurrentIndex(buf_map.get(current_buf, 2))
        buf_col.addWidget(self.buf_combo)
        params_row1.addLayout(buf_col)
        
        # Read ahead
        read_col = QVBoxLayout()
        read_col.addWidget(QLabel("Vorauslesen (Read-Ahead):"))
        self.read_combo = QComboBox()
        self.read_combo.addItems(["Deaktiviert", "32 MB", "64 MB", "128 MB (Empfohlen)", "256 MB", "512 MB"])
        current_read = self.profile_data.get("vfs_read_ahead", "128M")
        read_map = {"off": 0, "32M": 1, "64M": 2, "128M": 3, "256M": 4, "512M": 5}
        self.read_combo.setCurrentIndex(read_map.get(current_read, 3))
        read_col.addWidget(self.read_combo)
        params_row1.addLayout(read_col)
        
        perf_layout.addLayout(params_row1)
        
        # Write-back delay and bandwidth limit
        params_row2 = QHBoxLayout()
        
        delay_col = QVBoxLayout()
        delay_col.addWidget(QLabel("Schreibverzögerung (z.B. 5s):"))
        self.delay_input = QLineEdit()
        self.delay_input.setText(self.profile_data.get("write_back_delay", "5s"))
        delay_col.addWidget(self.delay_input)
        params_row2.addLayout(delay_col)
        
        limit_col = QVBoxLayout()
        limit_col.addWidget(QLabel("Bandbreiten-Limit (z.B. 2M, 500k):"))
        self.limit_input = QLineEdit()
        self.limit_input.setText(self.profile_data.get("bw_limit", ""))
        self.limit_input.setPlaceholderText("Unbegrenzt")
        limit_col.addWidget(self.limit_input)
        params_row2.addLayout(limit_col)
        
        perf_layout.addLayout(params_row2)
        layout.addWidget(perf_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "API & Performance")

    def toggle_api_inputs(self, state):
        show = state == Qt.CheckState.Checked.value
        self.api_inputs_widget.setVisible(show)

    def open_api_guide(self):
        QDesktopServices.openUrl(QUrl("https://rclone.org/drive/#making-your-own-client-id"))

    def open_reauth_link_manually(self):
        if self.auth_url:
            QDesktopServices.openUrl(QUrl(self.auth_url))

    def start_reauth(self):
        """Starts Google OAuth flow in the background with the custom API credentials input by the user."""
        if not self.manager:
            QMessageBox.warning(self, "Fehler", "rclone-Manager nicht verfügbar.")
            return
            
        client_id = self.client_id_input.text().strip()
        client_secret = self.client_secret_input.text().strip()
        
        if self.use_custom_api_cb.isChecked() and (not client_id or not client_secret):
            QMessageBox.warning(self, "Warnung", "Bitte geben Sie Client-ID und Client-Secret ein, bevor Sie autorisieren.")
            return
            
        self.reauth_btn.setEnabled(False)
        self.reauth_status_lbl.setText("Starte rclone Verbindungsprozess...")
        self.reauth_status_lbl.setStyleSheet("color: #FBBC05; font-weight: bold;")
        
        remote_name = self.profile_data.get("remote_name")
        success, err = self.manager.start_auth(
            remote_name,
            self.handle_reauth_output,
            client_id=client_id if self.use_custom_api_cb.isChecked() else "",
            client_secret=client_secret if self.use_custom_api_cb.isChecked() else ""
        )
        
        if not success:
            self.reauth_status_lbl.setText(f"Fehler: {err}")
            self.reauth_status_lbl.setStyleSheet("color: #EA4335; font-weight: bold;")
            self.reauth_btn.setEnabled(True)
        else:
            try:
                self.manager.auth_process.finished.disconnect(self.on_reauth_process_finished)
            except (TypeError, AttributeError):
                pass
            self.manager.auth_process.finished.connect(self.on_reauth_process_finished)

    def handle_reauth_output(self, text):
        if "http://127.0.0.1:53682/" in text:
            match = re.search(r"http://127.0.0.1:53682/auth\?state=\S+", text)
            if match:
                self.auth_url = match.group(0)
                self.reauth_status_lbl.setText("Bitte bestätigen Sie die Anmeldung im Webbrowser.")
                self.reauth_status_lbl.setStyleSheet("color: #FBBC05; font-weight: bold;")
                self.reauth_link_btn.setVisible(True)
                QDesktopServices.openUrl(QUrl(self.auth_url))

    def on_reauth_process_finished(self, exit_code, exit_status):
        self.reauth_link_btn.setVisible(False)
        self.reauth_btn.setEnabled(True)
        
        remote_name = self.profile_data.get("remote_name")
        if exit_code == 0 and self.manager.is_configured(remote_name):
            self.reauth_status_lbl.setText("✓ Anmeldung erfolgreich erneuert!")
            self.reauth_status_lbl.setStyleSheet("color: #34A853; font-weight: bold;")
        else:
            if exit_code != 0:
                self.reauth_status_lbl.setText("✗ Anmeldung fehlgeschlagen oder abgebrochen.")
                self.reauth_status_lbl.setStyleSheet("color: #EA4335; font-weight: bold;")
            else:
                self.reauth_status_lbl.setText("Bereit zum Anmelden.")
                self.reauth_status_lbl.setStyleSheet("color: #a0a0a9;")

    def browse_folder(self):
        current_dir = self.path_input.text()
        selected_dir = QFileDialog.getExistingDirectory(
            self, 
            "Wähle Google Drive Ordner", 
            current_dir,
            QFileDialog.Option.ShowDirsOnly
        )
        if selected_dir:
            self.path_input.setText(selected_dir)

    def reject(self):
        if self.manager:
            self.manager.cancel_auth()
        super().reject()

    def save_settings(self):
        new_name = self.name_input.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Warnung", "Bitte geben Sie einen Profilnamen ein.")
            return
            
        # Verify unique name if name changed
        if new_name != self.original_name:
            if self.config.get_profile(new_name):
                QMessageBox.warning(self, "Warnung", f"Ein Profil namens '{new_name}' existiert bereits.")
                return
                
        # Validate write back delay formatting
        delay = self.delay_input.text().strip()
        if delay and not any(delay.endswith(u) for u in ['s', 'm', 'h']):
            QMessageBox.warning(self, "Warnung", "Die Schreibverzögerung muss eine Zeiteinheit haben, z. B. '5s', '2m' oder leer sein.")
            return

        # Validate bandwidth limit formatting
        limit = self.limit_input.text().strip()
        if limit and not any(limit.lower().endswith(u) for u in ['k', 'm', 'g']):
            if not limit.isdigit():
                QMessageBox.warning(self, "Warnung", "Das Bandbreiten-Limit muss eine Einheit haben, z. B. '2M', '500K' oder leer sein.")
                return

        # Update profile dictionary
        self.profile_data["name"] = new_name
        self.profile_data["mount_path"] = self.path_input.text()
        
        cache_modes = ["full", "writes", "minimal", "off"]
        self.profile_data["cache_mode"] = cache_modes[self.cache_combo.currentIndex()]
        self.profile_data["write_back_delay"] = delay
        self.profile_data["bw_limit"] = limit
        self.profile_data["mount_on_start"] = self.mount_on_start_cb.isChecked()
        self.profile_data["keep_cached"] = self.keep_cached_cb.isChecked()
        self.profile_data["prefetch_enabled"] = self.prefetch_cb.isChecked()
        
        # New settings
        use_custom_api = self.use_custom_api_cb.isChecked()
        self.profile_data["use_custom_api"] = use_custom_api
        
        chunk_sizes = ["8M", "16M", "32M", "64M", "128M", "256M"]
        self.profile_data["drive_chunk_size"] = chunk_sizes[self.chunk_combo.currentIndex()]
        
        buf_sizes = ["16M", "32M", "64M", "128M", "256M"]
        self.profile_data["buffer_size"] = buf_sizes[self.buf_combo.currentIndex()]
        
        read_aheads = ["off", "32M", "64M", "128M", "256M", "512M"]
        self.profile_data["vfs_read_ahead"] = read_aheads[self.read_combo.currentIndex()]
        
        # Update credentials in rclone.conf directly if custom api is selected
        remote_name = self.profile_data.get("remote_name")
        client_id = self.client_id_input.text().strip()
        client_secret = self.client_secret_input.text().strip()
        
        if self.manager:
            if use_custom_api:
                self.manager.update_remote_credentials(remote_name, client_id, client_secret)
            else:
                self.manager.update_remote_credentials(remote_name, "", "")
        
        self.accept()

    def get_data(self):
        return self.profile_data
