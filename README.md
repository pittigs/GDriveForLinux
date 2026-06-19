# Google Drive Mount für Linux (GUI)

Eine elegante, native PyQt6-Desktopanwendung für Linux, die das automatische Einhängen (Mounten) von Google Drive-Konten über `rclone` und FUSE ermöglicht – vergleichbar mit dem offiziellen Client unter Windows.

---

## Hauptfunktionen

- **Multi-Account-Unterstützung**: Richte mehrere Profile (z. B. "Privat", "Arbeit") ein und mounte sie gleichzeitig in verschiedene Verzeichnisse.
- **Benutzerfreundlicher Einrichtungs-Assistent**: Führe die Google Drive Authentifizierung direkt im Webbrowser durch – die App konfiguriert rclone automatisch im Hintergrund.
- **Offline-Verfügbarkeit (Lokal Speichern)**: Optionale dauerhafte lokale Zwischenspeicherung (Cache-Modus `full`, `--vfs-cache-max-age 9999h` und `--vfs-cache-max-size off`), damit Dateien lokal verfügbar bleiben und nicht jedes Mal neu heruntergeladen werden müssen.
- **Optimierte Performance & Limits**: Einstellbare Upload-/Download-Bandbreitenbegrenzungen sowie konfigurierbare VFS Write-Back-Verzögerungen für flüssigeres Arbeiten.
- **Hintergrundbetrieb & Tray-Icon**: Die App minimiert sich in das System-Tray. Über das Tray-Menü können einzelne Konten schnell per Klick verbunden oder getrennt werden.
- **Dateimanager-Integration (Sidebar)**: Fügt verbundene Laufwerke automatisch der Dolphin-Places-Sidebar (KDE) und den GTK-Lesezeichen (GNOME Files / Nautilus) hinzu und entfernt sie beim Trennen wieder.
- **Verbindungsüberwachung & Auto-Recovery**: Erkennt Netzwerkänderungen. Bei Verbindungsabbruch zeigt die App "Warte auf Netzwerk..." und verbindet sich vollautomatisch neu, sobald das Internet wieder verfügbar ist.
- **Autostart-Funktion**: Startet auf Wunsch minimiert direkt beim Systemstart und bindet ausgewählte Konten sofort ein.
- **Ghost-Mount-Bereinigung**: Erkennt verwaiste FUSE-Mounts (z. B. nach einem Systemabsturz) und bereinigt diese automatisch vor einem neuen Verbindungsaufbau.

---

## Voraussetzungen

### 1. Python 3 & PyQt6
Die Anwendung basiert auf Python 3 und PyQt6. Installiere die Abhängigkeiten über den Paketmanager deiner Distribution:

**Arch Linux / CachyOS / Manjaro:**
```bash
sudo pacman -S python python-pyqt6
```

**Ubuntu / Debian / Linux Mint:**
```bash
sudo apt update
sudo apt install python3 python3-pyqt6
```

**Fedora:**
```bash
sudo dnf install python3 python3-qt5 # bzw. python3-pyqt6
```

*(Alternativ über Pip: `pip install PyQt6`)*

### 2. FUSE 3
Für das Mounten wird FUSE 3 benötigt:
- **Arch/CachyOS**: `sudo pacman -S fuse3`
- **Ubuntu/Debian**: `sudo apt install fuse3`

### 3. Rclone
**Hinweis**: Du musst `rclone` nicht zwingend global installieren! Wenn kein systemweites `rclone` gefunden wird, lädt die App beim ersten Start automatisch die aktuellste offizielle Version herunter und speichert sie lokal unter `~/.local/share/gdrive-mount/bin/rclone`.

---

## Installation

Um die App in dein Anwendungsmenü des Desktops (z. B. GNOME, KDE) zu integrieren:

1. Navigiere in das Projektverzeichnis:
   ```bash
   cd ~/Dokumente/GDriveForLinux
   ```
2. Mache das Installationsskript ausführbar und führe es aus:
   ```bash
   chmod +x install_desktop.sh run.sh
   ./install_desktop.sh
   ```

Das Skript erstellt eine Desktop-Verknüpfung unter `~/.local/share/applications/gdrive-mount.desktop` mit den korrekten Pfaden. Die App ist danach sofort in deinem Anwendungsmenü unter dem Namen **Google Drive Mount** zu finden und kann gestartet werden.

---

## Verwendung der App

### 1. Ein erstes Konto hinzufügen
- Beim ersten Start öffnet sich der **Einrichtungs-Assistent**.
- **Schritt 1 (Optionen)**: Wähle einen Profilnamen (z. B. `Google Drive`) und das lokale Verzeichnis, in das die Dateien gemountet werden sollen (Standard: `~/GoogleDrive`).
- **Schritt 2 (Verbindung)**: Klicke auf "Jetzt Anmelden". Es öffnet sich dein Standardbrowser. Melde dich mit deinem Google-Konto an und erteile rclone die Freigabe.
- Sobald im Browser "Success!" steht, kannst du den Assistenten abschließen.

### 2. Dashboard & Kontoverwaltung
Im Hauptfenster siehst du Karten für all deine Konten:
- **Verbinden / Trennen**: Klicke auf den Button, um den Mount zu starten oder zu beenden.
- **Ordner öffnen**: Öffnet das gemountete Verzeichnis direkt in deinem Dateimanager.
- **Bearbeiten**: Hier kannst du erweiterte Einstellungen festlegen:
  - *Automatisches Mounten beim App-Start*.
  - *Lokal speichern (Offline-Verfügbarkeit)* aktivieren/deaktivieren.
  - *VFS Cache-Modus* ändern.
  - *Schreibverzögerung (Write-Back Delay)* einstellen.
  - *Bandbreitenlimit* setzen (z. B. `5M` für 5 MB/s).
- **Löschen (Rot)**: Entfernt das Profil und die rclone-Konfiguration.

### 3. Tray-Icon & Hintergrundmodus
- Wenn du das Hauptfenster schließt, läuft die App unsichtbar im System-Tray weiter.
- **Rechtsklick auf das Tray-Icon**: Zeigt eine Checkliste aller Konten an. Durch Anklicken eines Kontos kannst du es direkt verbinden oder trennen.
- **Linksklick auf das Tray-Icon**: Öffnet das Dashboard wieder.
- Über **Beenden** im Tray-Kontextmenü wird die App komplett geschlossen (dabei werden alle aktiven FUSE-Mounts automatisch sauber ausgehängt).

---

## Projektstruktur

```
GDriveForLinux/
├── run.sh                  # Startskript (setzt PYTHONPATH und startet die App)
├── install_desktop.sh      # Desktop-Integrationsskript (erstellt .desktop-Eintrag)
├── gdrive-mount.desktop    # Template für den Desktop-Starter
├── README.md               # Diese Dokumentation
└── gdrive_app/             # Python-Paket der Anwendung
    ├── main.py             # Haupteinstiegspunkt & Single-Instance-Sperre
    ├── assets/
    │   └── icon.svg        # Google Drive App-Icon
    ├── core/
    │   ├── config.py       # Einstellungs- und Profilverwaltung (settings.json)
    │   ├── rclone_manager.py # Mount-Steuerung per QProcess & FUSE-Prüfungen
    │   ├── sidebar.py      # Dolphin Places & GTK Bookmarks Integration
    │   ├── autostart.py    # Desktop-Autostart-Verwaltung (autostart.desktop)
    │   └── network.py      # Verbindungsüberwachung (Socket-Ping)
    └── gui/
        ├── styles.py       # Premium Dark-Theme Stylesheet (QSS)
        ├── wizard.py       # Mehrseitiger Einrichtungsassistent
        ├── main_window.py  # Haupt-Dashboard & Log-Konsole
        ├── profile_dialog.py # Profil-Editor (Bandbreite, Cache, Autostart)
        └── tray_icon.py    # System-Tray Integration & Desktop-Meldungen
```
