import os
import re
from pathlib import Path
from PyQt6.QtWidgets import (QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFileDialog, QCheckBox, 
                             QLineEdit, QProgressBar, QWidget, QMessageBox)
from PyQt6.QtCore import Qt, QUrl, pyqtSlot
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtSvgWidgets import QSvgWidget

class SetupWizard(QWizard):
    def __init__(self, config, manager, parent=None):
        super().__init__(parent)
        self.config = config
        self.manager = manager
        
        self.setWindowTitle("Google Drive Verbindung hinzufügen")
        self.setWindowIcon(QIcon(str(Path(__file__).parents[1] / "assets" / "icon.svg")))
        self.resize(550, 520)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        
        self.setOption(QWizard.WizardOption.NoCancelButton, False)
        
        # Swapped pages: Options before Auth to generate remote name
        self.addPage(WelcomePage(self.config, self.manager, self))
        self.addPage(OptionsPage(self.config, self.manager, self))
        self.addPage(AuthPage(self.config, self.manager, self))
        
        self.button(QWizard.WizardButton.NextButton).setObjectName("Primary")
        self.button(QWizard.WizardButton.FinishButton).setObjectName("Primary")
        
        self.finished.connect(self.on_wizard_finished)

    def on_wizard_finished(self, result):
        if result != QWizard.DialogCode.Accepted:
            self.manager.cancel_auth()


class WelcomePage(QWizardPage):
    def __init__(self, config, manager, parent=None):
        super().__init__(parent)
        self.config = config
        self.manager = manager
        
        self.setTitle("Willkommen bei Google Drive Mount")
        self.setSubTitle("Diese App hilft Ihnen, Ihr Google Drive als lokales Laufwerk einzubinden.")
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        logo_layout = QHBoxLayout()
        logo_layout.addStretch()
        self.logo_widget = QSvgWidget(str(Path(__file__).parents[1] / "assets" / "icon.svg"))
        self.logo_widget.setFixedSize(100, 100)
        logo_layout.addWidget(self.logo_widget)
        logo_layout.addStretch()
        layout.addLayout(logo_layout)
        
        self.info_label = QLabel(
            "Um Google Drive auf Linux nutzen zu können, verwenden wir rclone. "
            "Dieses Tool konfiguriert und mountet Google Drive nahtlos im Hintergrund. "
            "Wir prüfen nun, ob rclone auf Ihrem System installiert ist."
        )
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        self.status_box = QWidget()
        self.status_box.setObjectName("InnerCard")
        self.status_box.setStyleSheet("#InnerCard { background-color: #1a1a1e; border: 1px solid #2d2d34; border-radius: 8px; }")
        status_layout = QVBoxLayout(self.status_box)
        
        self.status_label = QLabel("Prüfe System auf rclone...")
        self.status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        
        self.install_btn = QPushButton("rclone installieren")
        self.install_btn.setObjectName("Primary")
        self.install_btn.setVisible(False)
        self.install_btn.clicked.connect(self.start_rclone_download)
        status_layout.addWidget(self.install_btn)
        
        layout.addWidget(self.status_box)
        layout.addStretch()
        self.setLayout(layout)
        self.downloader = None

    def initializePage(self):
        self.wizard().button(QWizard.WizardButton.NextButton).setEnabled(False)
        self.check_rclone()

    def check_rclone(self):
        if self.manager.is_installed():
            rclone_bin = self.manager.find_rclone()
            self.status_label.setText(f"✓ rclone gefunden in:\n{rclone_bin}")
            self.status_label.setStyleSheet("color: #34A853; font-weight: bold;")
            self.install_btn.setVisible(False)
            self.progress_bar.setVisible(False)
            self.wizard().button(QWizard.WizardButton.NextButton).setEnabled(True)
        else:
            self.status_label.setText("✗ rclone wurde nicht auf Ihrem System gefunden.")
            self.status_label.setStyleSheet("color: #EA4335; font-weight: bold;")
            self.install_btn.setVisible(True)

    def start_rclone_download(self):
        self.install_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.downloader = self.manager.get_downloader()
        self.downloader.progress.connect(self.progress_bar.setValue)
        self.downloader.status.connect(self.status_label.setText)
        self.downloader.finished.connect(self.on_download_finished)
        self.downloader.start()

    def on_download_finished(self, success, result_msg):
        if success:
            self.config.rclone_path = result_msg
            self.config.save()
            self.status_label.setText("✓ rclone wurde erfolgreich heruntergeladen und installiert!")
            self.status_label.setStyleSheet("color: #34A853; font-weight: bold;")
            self.install_btn.setVisible(False)
            self.progress_bar.setVisible(False)
            self.wizard().button(QWizard.WizardButton.NextButton).setEnabled(True)
        else:
            self.status_label.setText(f"Fehler beim Download:\n{result_msg}")
            self.status_label.setStyleSheet("color: #EA4335; font-weight: bold;")
            self.install_btn.setEnabled(True)
            self.progress_bar.setVisible(False)


class OptionsPage(QWizardPage):
    def __init__(self, config, manager, parent=None):
        super().__init__(parent)
        self.config = config
        self.manager = manager
        
        self.setTitle("Einstellungen")
        self.setSubTitle("Wählen Sie einen Namen und Speicherort für das neue Konto.")
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 1. Profile Name
        name_label = QLabel("Name für diese Google Drive Verbindung (z. B. Privat, Arbeit):")
        layout.addWidget(name_label)
        self.name_input = QLineEdit()
        layout.addWidget(self.name_input)
        
        # 2. Directory choice
        dir_label = QLabel("Lokaler Mount-Ordner (hier finden Sie Ihre Google Drive Dateien):")
        layout.addWidget(dir_label)
        
        dir_layout = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setReadOnly(True)
        dir_layout.addWidget(self.dir_input)
        
        self.browse_btn = QPushButton("Durchsuchen...")
        self.browse_btn.clicked.connect(self.browse_folder)
        dir_layout.addWidget(self.browse_btn)
        layout.addLayout(dir_layout)
        
        # 3. Checkboxes
        layout.addSpacing(5)
        self.autostart_cb = QCheckBox("Google Drive beim Systemstart automatisch mounten")
        self.autostart_cb.setChecked(self.config.autostart)
        layout.addWidget(self.autostart_cb)
        
        self.mount_now_cb = QCheckBox("Nach Einrichtung direkt verbinden und Ordner öffnen")
        self.mount_now_cb.setChecked(True)
        layout.addWidget(self.mount_now_cb)
        
        # 4. Custom API checkbox and inputs
        self.custom_api_cb = QCheckBox("Eigene Google API-Zugangsdaten verwenden (Sehr empfohlen für Performance)")
        self.custom_api_cb.stateChanged.connect(self.toggle_custom_api_widget)
        layout.addWidget(self.custom_api_cb)
        
        self.custom_api_widget = QWidget()
        api_layout = QVBoxLayout(self.custom_api_widget)
        api_layout.setContentsMargins(15, 0, 15, 0)
        api_layout.setSpacing(8)
        
        self.help_api_btn = QPushButton("Wie erstelle ich meine eigenen API-Zugangsdaten? (Anleitung im Browser öffnen)")
        self.help_api_btn.setStyleSheet("color: #4285F4; text-decoration: underline; background: transparent; border: none; font-size: 11px; text-align: left; padding: 0;")
        self.help_api_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_api_btn.clicked.connect(self.open_api_guide)
        api_layout.addWidget(self.help_api_btn)
        
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("Client-ID:"))
        self.client_id_input = QLineEdit()
        self.client_id_input.setPlaceholderText("Google Client-ID hier einfügen")
        id_layout.addWidget(self.client_id_input)
        api_layout.addLayout(id_layout)
        
        secret_layout = QHBoxLayout()
        secret_layout.addWidget(QLabel("Client-Secret:"))
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setPlaceholderText("Google Client-Secret hier einfügen")
        secret_layout.addWidget(self.client_secret_input)
        api_layout.addLayout(secret_layout)
        
        self.custom_api_widget.setVisible(False)
        layout.addWidget(self.custom_api_widget)
        
        layout.addStretch()
        self.setLayout(layout)

    def toggle_custom_api_widget(self, state):
        show = state == Qt.CheckState.Checked.value
        self.custom_api_widget.setVisible(show)

    def open_api_guide(self):
        QDesktopServices.openUrl(QUrl("https://rclone.org/drive/#making-your-own-client-id"))

    def initializePage(self):
        # Suggest unique defaults
        existing_profiles = self.config.get_profiles()
        idx = len(existing_profiles) + 1
        
        suggested_name = "Google Drive" if idx == 1 else f"Google Drive {idx}"
        while self.config.get_profile(suggested_name):
            idx += 1
            suggested_name = f"Google Drive {idx}"
            
        self.name_input.setText(suggested_name)
        
        suggested_path = Path.home() / "GoogleDrive" if idx == 1 else Path.home() / f"GoogleDrive_{suggested_name.replace(' ', '')}"
        while any(p.get("mount_path") == str(suggested_path) for p in existing_profiles):
            idx += 1
            suggested_path = Path.home() / f"GoogleDrive_{idx}"
            
        self.dir_input.setText(str(suggested_path))

    def browse_folder(self):
        current_dir = self.dir_input.text()
        selected_dir = QFileDialog.getExistingDirectory(
            self, 
            "Wähle Google Drive Ordner", 
            current_dir,
            QFileDialog.Option.ShowDirsOnly
        )
        if selected_dir:
            self.dir_input.setText(selected_dir)

    def validatePage(self):
        profile_name = self.name_input.text().strip()
        if not profile_name:
            QMessageBox.warning(self, "Warnung", "Bitte geben Sie einen Namen für dieses Konto ein.")
            return False
            
        if self.config.get_profile(profile_name):
            QMessageBox.warning(self, "Warnung", f"Ein Profil mit dem Namen '{profile_name}' existiert bereits.")
            return False
            
        selected_path = self.dir_input.text().strip()
        if not selected_path:
            QMessageBox.warning(self, "Warnung", "Bitte wählen Sie einen Mount-Ordner.")
            return False
            
        # Check path conflicts with other profiles
        for p in self.config.get_profiles():
            if os.path.abspath(p.get("mount_path")) == os.path.abspath(selected_path):
                QMessageBox.warning(self, "Warnung", f"Der Pfad '{selected_path}' wird bereits vom Profil '{p.get('name')}' verwendet.")
                return False

        # Generate a unique remote name slug
        safe_slug = re.sub(r'[^a-zA-Z0-9]', '', profile_name.lower())
        if not safe_slug:
            safe_slug = "remote"
        remote_name = f"gdrive_{safe_slug}"
        
        # Ensure rclone remote name is unique
        idx = 1
        orig_remote = remote_name
        while self.manager.is_configured(remote_name):
            remote_name = f"{orig_remote}_{idx}"
            idx += 1

        use_custom_api = self.custom_api_cb.isChecked()
        client_id = self.client_id_input.text().strip()
        client_secret = self.client_secret_input.text().strip()
        
        if use_custom_api:
            if not client_id or not client_secret:
                QMessageBox.warning(self, "Warnung", "Bitte geben Sie sowohl eine Client-ID als auch ein Client-Secret ein, oder deaktivieren Sie die Option.")
                return False

        # Store wizard properties to pass to AuthPage
        self.wizard().setProperty("profile_name", profile_name)
        self.wizard().setProperty("mount_path", selected_path)
        self.wizard().setProperty("remote_name", remote_name)
        self.wizard().setProperty("autostart_profile", self.autostart_cb.isChecked())
        self.wizard().setProperty("mount_now", self.mount_now_cb.isChecked())
        self.wizard().setProperty("use_custom_api", use_custom_api)
        self.wizard().setProperty("client_id", client_id if use_custom_api else "")
        self.wizard().setProperty("client_secret", client_secret if use_custom_api else "")
        return True


class AuthPage(QWizardPage):
    def __init__(self, config, manager, parent=None):
        super().__init__(parent)
        self.config = config
        self.manager = manager
        self.auth_url = ""
        self.remote_name = ""
        
        self.setTitle("Google-Konto verknüpfen")
        self.setSubTitle("Melden Sie sich mit Ihrem Google-Konto an, um den Zugriff freizugeben.")
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.info_lbl = QLabel(
            "Nachdem Sie auf 'Anmelden' klicken, öffnet sich Ihr Webbrowser. "
            "Dort loggen Sie sich bei Google ein und bestätigen den Zugriff für rclone.\n\n"
            "Die Verbindung erfolgt sicher über Google OAuth direkt an Ihr System."
        )
        self.info_lbl.setWordWrap(True)
        layout.addWidget(self.info_lbl)
        
        self.card = QWidget()
        self.card.setObjectName("InnerCard")
        self.card.setStyleSheet("#InnerCard { background-color: #1a1a1e; border: 1px solid #2d2d34; border-radius: 8px; }")
        card_layout = QVBoxLayout(self.card)
        card_layout.setSpacing(12)
        
        self.login_btn = QPushButton("Jetzt Anmelden")
        self.login_btn.setObjectName("Primary")
        self.login_btn.clicked.connect(self.start_auth_flow)
        card_layout.addWidget(self.login_btn)
        
        self.status_lbl = QLabel("Bereit zum Anmelden.")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("color: #a0a0a9;")
        card_layout.addWidget(self.status_lbl)
        
        self.link_btn = QPushButton("Link manuell im Browser öffnen")
        self.link_btn.setStyleSheet("color: #4285F4; text-decoration: underline; background: transparent; border: none; font-weight: bold;")
        self.link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link_btn.setVisible(False)
        self.link_btn.clicked.connect(self.open_auth_link_manually)
        card_layout.addWidget(self.link_btn)
        
        layout.addWidget(self.card)
        layout.addStretch()
        self.setLayout(layout)

    def initializePage(self):
        self.wizard().button(QWizard.WizardButton.FinishButton).setEnabled(False)
        self.login_btn.setEnabled(True)
        self.link_btn.setVisible(False)
        self.status_lbl.setText("Bereit zum Anmelden.")
        self.status_lbl.setStyleSheet("color: #a0a0a9;")
        
        # Load parameters from wizard properties
        self.remote_name = self.wizard().property("remote_name")
        profile_name = self.wizard().property("profile_name")
        self.info_lbl.setText(
            f"Wir verknüpfen nun das Profil '{profile_name}' (interner Name: {self.remote_name}) mit Google.\n\n"
            "Nachdem Sie auf 'Jetzt Anmelden' klicken, öffnet sich Ihr Webbrowser. "
            "Dort loggen Sie sich bei Google ein und bestätigen den Zugriff für rclone."
        )

    def start_auth_flow(self):
        self.login_btn.setEnabled(False)
        self.status_lbl.setText("Starte rclone Verbindungsprozess...")
        self.status_lbl.setStyleSheet("color: #FBBC05; font-weight: bold;")
        
        client_id = self.wizard().property("client_id")
        client_secret = self.wizard().property("client_secret")
        
        success, err = self.manager.start_auth(
            self.remote_name, 
            self.handle_auth_output,
            client_id=client_id,
            client_secret=client_secret
        )
        if not success:
            self.status_lbl.setText(f"Fehler: {err}")
            self.status_lbl.setStyleSheet("color: #EA4335; font-weight: bold;")
            self.login_btn.setEnabled(True)
        else:
            # Connect the finished signal only once here
            try:
                self.manager.auth_process.finished.disconnect(self.on_auth_process_finished)
            except (TypeError, AttributeError):
                pass
            self.manager.auth_process.finished.connect(self.on_auth_process_finished)

    def handle_auth_output(self, text):
        if "http://127.0.0.1:53682/" in text:
            match = re.search(r"http://127.0.0.1:53682/auth\?state=\S+", text)
            if match:
                self.auth_url = match.group(0)
                self.status_lbl.setText("Bitte bestätigen Sie die Anmeldung im Webbrowser.")
                self.status_lbl.setStyleSheet("color: #FBBC05; font-weight: bold;")
                self.link_btn.setVisible(True)
                QDesktopServices.openUrl(QUrl(self.auth_url))

    def on_auth_process_finished(self, exit_code, exit_status):
        self.link_btn.setVisible(False)
        self.login_btn.setEnabled(True)
        
        if exit_code == 0 and self.manager.is_configured(self.remote_name):
            self.status_lbl.setText("✓ Verbindung erfolgreich eingerichtet!")
            self.status_lbl.setStyleSheet("color: #34A853; font-weight: bold;")
            self.login_btn.setVisible(False)
            
            # Save profile to config *after* successful authentication
            profile_name = self.wizard().property("profile_name")
            use_custom_api = self.wizard().property("use_custom_api")
            new_profile = {
                "name": profile_name,
                "remote_name": self.remote_name,
                "mount_path": self.wizard().property("mount_path"),
                "mount_on_start": True,
                "cache_mode": "full",
                "write_back_delay": "5s",
                "bw_limit": "",
                "use_custom_api": use_custom_api,
                "drive_chunk_size": "64M",
                "buffer_size": "64M",
                "vfs_read_ahead": "128M"
            }
            self.config.add_profile(new_profile)
            
            # Autostart configuration
            autostart_enabled = self.wizard().property("autostart_profile")
            self.config.autostart = autostart_enabled
            from gdrive_app.core.autostart import AutostartManager
            AutostartManager.set_autostart(autostart_enabled)
            
            # Enable finish button
            self.wizard().button(QWizard.WizardButton.FinishButton).setEnabled(True)
            self.wizard().next()
        else:
            if exit_code != 0:
                self.status_lbl.setText("✗ Anmeldung fehlgeschlagen oder abgebrochen.")
                self.status_lbl.setStyleSheet("color: #EA4335; font-weight: bold;")
            else:
                self.status_lbl.setText("Bereit zum Anmelden.")
                self.status_lbl.setStyleSheet("color: #a0a0a9;")

    def open_auth_link_manually(self):
        if self.auth_url:
            QDesktopServices.openUrl(QUrl(self.auth_url))
