import os
from pathlib import Path
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QComboBox, QCheckBox, 
                             QFileDialog, QMessageBox, QFrame)
from PyQt6.QtCore import Qt
from gdrive_app.gui.styles import THEME_STYLE

class ProfileDialog(QDialog):
    def __init__(self, config, profile_data, parent=None):
        super().__init__(parent)
        self.config = config
        self.original_name = profile_data.get("name")
        self.profile_data = profile_data.copy()
        
        self.setWindowTitle("Konto-Einstellungen bearbeiten")
        self.setStyleSheet(THEME_STYLE)
        self.resize(450, 420)
        
        # Layout
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        self.header_lbl = QLabel(f"Einstellungen für '{self.original_name}'")
        self.header_lbl.setObjectName("Title")
        self.layout.addWidget(self.header_lbl)
        
        # Inner container
        self.card = QFrame()
        self.card.setObjectName("InnerCard")
        self.card.setStyleSheet("#InnerCard { background-color: #1a1a1e; border: 1px solid #2d2d34; border-radius: 8px; }")
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setSpacing(12)
        
        # 1. Profile Name
        name_lbl = QLabel("Profil-Name:")
        self.card_layout.addWidget(name_lbl)
        self.name_input = QLineEdit()
        self.name_input.setText(self.profile_data.get("name"))
        self.card_layout.addWidget(self.name_input)
        
        # 2. Mount Path
        path_lbl = QLabel("Lokaler Mount-Ordner:")
        self.card_layout.addWidget(path_lbl)
        
        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setText(self.profile_data.get("mount_path"))
        self.path_input.setReadOnly(True)
        path_row.addWidget(self.path_input)
        
        browse_btn = QPushButton("Ändern...")
        browse_btn.clicked.connect(self.browse_folder)
        path_row.addWidget(browse_btn)
        self.card_layout.addLayout(path_row)
        
        # 3. Cache Mode
        cache_lbl = QLabel("VFS Cache-Modus:")
        self.card_layout.addWidget(cache_lbl)
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
        self.card_layout.addWidget(self.cache_combo)
        
        # 4. Write-back Delay & Bandwidth Limit (Side-by-side)
        params_layout = QHBoxLayout()
        
        delay_col = QVBoxLayout()
        delay_col.addWidget(QLabel("Schreibverzögerung (z.B. 5s):"))
        self.delay_input = QLineEdit()
        self.delay_input.setText(self.profile_data.get("write_back_delay", "5s"))
        delay_col.addWidget(self.delay_input)
        params_layout.addLayout(delay_col)
        
        limit_col = QVBoxLayout()
        limit_col.addWidget(QLabel("Upload-Limit (z.B. 2M, 500k):"))
        self.limit_input = QLineEdit()
        self.limit_input.setText(self.profile_data.get("bw_limit", ""))
        self.limit_input.setPlaceholderText("Unbegrenzt")
        limit_col.addWidget(self.limit_input)
        params_layout.addLayout(limit_col)
        
        self.card_layout.addLayout(params_layout)
        
        # 5. Checkboxes
        self.mount_on_start_cb = QCheckBox("Google Drive beim App-Start automatisch mounten")
        self.mount_on_start_cb.setChecked(self.profile_data.get("mount_on_start", True))
        self.card_layout.addWidget(self.mount_on_start_cb)
        
        self.keep_cached_cb = QCheckBox("Dateien dauerhaft lokal speichern (Offline-Verfügbarkeit)")
        self.keep_cached_cb.setChecked(self.profile_data.get("keep_cached", False))
        self.card_layout.addWidget(self.keep_cached_cb)
        
        self.layout.addWidget(self.card)
        
        # Buttons
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
                
        # Validate write back delay formatting (optional check, e.g. must end in s, m, h or empty)
        delay = self.delay_input.text().strip()
        if delay and not any(delay.endswith(u) for u in ['s', 'm', 'h']):
            QMessageBox.warning(self, "Warnung", "Die Schreibverzögerung muss eine Zeiteinheit haben, z. B. '5s', '2m' oder leer sein.")
            return

        # Validate bandwidth limit formatting
        limit = self.limit_input.text().strip()
        if limit and not any(limit.lower().endswith(u) for u in ['k', 'm', 'g']):
            # If purely digits, it's bytes (which is fine), otherwise check suffix
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
        
        self.accept()

    def get_data(self):
        return self.profile_data
