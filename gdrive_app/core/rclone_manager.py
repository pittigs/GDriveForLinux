import os
import sys
import shutil
import zipfile
import urllib.request
import subprocess
import json
import configparser
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QProcess

class RcloneDownloader(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, dest_dir):
        super().__init__()
        self.dest_dir = Path(dest_dir)
        self.bin_dir = self.dest_dir / "bin"

    def run(self):
        try:
            self.bin_dir.mkdir(parents=True, exist_ok=True)
            zip_path = self.dest_dir / "rclone.zip"
            
            # 1. Download
            self.status.emit("Downloading latest rclone...")
            url = "https://downloads.rclone.org/rclone-current-linux-amd64.zip"
            
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)'}
            )
            
            with urllib.request.urlopen(req) as response:
                total_size = int(response.info().get('Content-Length', 0))
                bytes_downloaded = 0
                chunk_size = 1024 * 16
                
                with open(zip_path, 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((bytes_downloaded / total_size) * 100)
                            self.progress.emit(percent)
            
            # 2. Extract
            self.status.emit("Extracting files...")
            self.progress.emit(90)
            
            extract_dir = self.dest_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Find the rclone binary inside the extracted folder
            rclone_bin_src = None
            for root, dirs, files in os.walk(extract_dir):
                if "rclone" in files:
                    candidate = Path(root) / "rclone"
                    if candidate.is_file() and not candidate.is_symlink():
                        rclone_bin_src = candidate
                        break
            
            if not rclone_bin_src:
                raise FileNotFoundError("rclone binary not found in zip package")
            
            # Copy to target destination
            target_bin_path = self.bin_dir / "rclone"
            if target_bin_path.exists():
                target_bin_path.unlink()
                
            shutil.copy2(rclone_bin_src, target_bin_path)
            
            # Make executable
            os.chmod(target_bin_path, 0o755)
            
            # Clean up
            zip_path.unlink()
            shutil.rmtree(extract_dir)
            
            self.progress.emit(100)
            self.status.emit("Rclone installation complete!")
            self.finished.emit(True, str(target_bin_path))
            
        except Exception as e:
            self.finished.emit(False, str(e))


class RcloneManager(QObject):
    # Signals now accept profile name as their first argument for multi-account routing
    mount_status_changed = pyqtSignal(str, bool, str) # (profile_name, is_mounted, status_message)
    log_received = pyqtSignal(str, str) # (profile_name, text_log)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.mount_processes = {} # Maps profile_name -> QProcess
        self.auth_process = None
        self.current_auth_profile = None
        
        # Local paths
        self.app_dir = Path.home() / ".local" / "share" / "gdrive-mount"
        self.app_dir.mkdir(parents=True, exist_ok=True)
        
    def find_rclone(self):
        """Checks if rclone is available. Returns the path or None."""
        config_path = self.config.rclone_path
        if config_path and os.path.exists(config_path) and os.access(config_path, os.X_OK):
            return config_path
            
        local_path = self.app_dir / "bin" / "rclone"
        if local_path.exists() and os.access(local_path, os.X_OK):
            self.config.rclone_path = str(local_path)
            return str(local_path)
            
        system_path = shutil.which("rclone")
        if system_path:
            self.config.rclone_path = system_path
            return system_path
            
        return None

    def is_installed(self):
        return self.find_rclone() is not None

    def get_downloader(self):
        return RcloneDownloader(self.app_dir)

    def is_configured(self, remote_name=None):
        """Checks if a specific remote (or any remote) exists in rclone.conf."""
        config_file = Path(self.config.rclone_config_path)
        if not config_file.exists():
            return False
            
        try:
            parser = configparser.ConfigParser()
            parser.read(config_file)
            if remote_name:
                return remote_name in parser.sections()
            else:
                # Returns True if at least one defined profile exists in rclone config
                profiles = self.config.get_profiles()
                if not profiles:
                    return False
                return any(p.get("remote_name") in parser.sections() for p in profiles)
        except Exception as e:
            print(f"Error checking rclone config: {e}")
            return False

    def remove_configuration(self, remote_name):
        """Removes the remote configuration from rclone.conf."""
        config_file = Path(self.config.rclone_config_path)
        if not config_file.exists():
            return True
            
        try:
            parser = configparser.ConfigParser()
            parser.read(config_file)
            if remote_name in parser.sections():
                parser.remove_section(remote_name)
                with open(config_file, "w") as f:
                    parser.write(f)
            return True
        except Exception as e:
            print(f"Error deleting config section '{remote_name}': {e}")
            return False

    def start_auth(self, remote_name, on_output_callback):
        """Starts the Google Drive authentication subprocess for a remote."""
        rclone_bin = self.find_rclone()
        if not rclone_bin:
            return False, "rclone binary not found"
            
        if self.auth_process and self.auth_process.state() == QProcess.ProcessState.Running:
            return False, "Auth process already running"

        self.auth_process = QProcess(self)
        self.auth_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        
        args = [
            "--config", self.config.rclone_config_path,
            "config", "create",
            remote_name,
            "drive",
            "scope=drive"
        ]
        
        self.current_auth_profile = remote_name
        self.auth_process.readyReadStandardOutput.connect(
            lambda: on_output_callback(self.auth_process.readAllStandardOutput().data().decode("utf-8", errors="replace"))
        )
        
        self.auth_process.start(rclone_bin, args)
        return True, ""

    def cancel_auth(self):
        if self.auth_process and self.auth_process.state() == QProcess.ProcessState.Running:
            self.auth_process.terminate()
            self.auth_process.waitForFinished(2000)
            self.auth_process.kill()
        self.current_auth_profile = None

    def start_mount(self, profile_name):
        """Starts mounting the specific Google Drive remote profile."""
        profile = self.config.get_profile(profile_name)
        if not profile:
            return False, f"Profile '{profile_name}' not found"

        rclone_bin = self.find_rclone()
        if not rclone_bin:
            self.mount_status_changed.emit(profile_name, False, "Fehler: rclone nicht gefunden.")
            return False, "rclone binary not found"

        remote_name = profile.get("remote_name")
        if not self.is_configured(remote_name):
            self.mount_status_changed.emit(profile_name, False, "Fehler: Google Drive nicht konfiguriert.")
            return False, "Google Drive remote not configured"

        # Check/create mount folder
        mount_path = Path(profile.get("mount_path"))
        try:
            mount_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.mount_status_changed.emit(profile_name, False, f"Fehler beim Erstellen des Mount-Ordners: {e}")
            return False, f"Could not create mount folder: {e}"

        # If it is mounted in /proc/mounts but our process is not running, it is a ghost mount.
        # Clean it up automatically before mounting.
        is_mounted = self.is_currently_mounted(profile_name)
        active_process = self.mount_processes.get(profile_name)
        is_process_running = active_process and active_process.state() == QProcess.ProcessState.Running
        
        if is_mounted and not is_process_running:
            self.log_received.emit(profile_name, "[System] Ghost Mount erkannt. Bereinige Altlasten...\n")
            self.stop_mount(profile_name)
            # Wait briefly to let unmount settle
            QThread.msleep(500)

        # If already mounted and process is active, we are fine
        if self.is_currently_mounted(profile_name) and is_process_running:
            return True, "Already mounted"
            
        if active_process and active_process.state() == QProcess.ProcessState.Running:
            active_process.terminate()
            active_process.waitForFinished(1000)
            
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        
        # Build command arguments
        cache_mode = profile.get("cache_mode", "full")
        keep_cached = profile.get("keep_cached", False)
        
        cache_max_age = "9999h" if keep_cached else "24h"
        cache_max_size = "off" if keep_cached else "10G"
        
        args = [
            "--config", self.config.rclone_config_path,
            "mount",
            f"{remote_name}:",
            str(mount_path),
            "--vfs-cache-mode", cache_mode,
            "--vfs-cache-max-age", cache_max_age,
            "--vfs-cache-max-size", cache_max_size
        ]
        
        # Add VFS write-back delay if configured
        write_back = profile.get("write_back_delay", "5s").strip()
        if write_back:
            args.extend(["--vfs-write-back", write_back])
            
        # Add Upload/Download limit if configured
        bw_limit = profile.get("bw_limit", "").strip()
        if bw_limit:
            args.extend(["--bwlimit", bw_limit])
            
        args.append("-v") # verbose logs
        
        process.readyReadStandardOutput.connect(lambda: self._handle_mount_logs(profile_name))
        process.finished.connect(lambda exit_code, exit_status: self._handle_mount_finished(profile_name, exit_code, exit_status))
        
        self.mount_processes[profile_name] = process
        process.start(rclone_bin, args)
        
        self.mount_status_changed.emit(profile_name, False, "Verbinde...")
        return True, ""

    def _handle_mount_logs(self, profile_name):
        process = self.mount_processes.get(profile_name)
        if not process:
            return
        data = process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self.log_received.emit(profile_name, data)

    def _handle_mount_finished(self, profile_name, exit_code, exit_status):
        self.mount_status_changed.emit(profile_name, False, "Nicht verbunden")
        self.log_received.emit(profile_name, f"\n[App] rclone mount Prozess beendet mit Code {exit_code} (Status: {exit_status})\n")
        if profile_name in self.mount_processes:
            # Clean process mapping but keep profile settings
            del self.mount_processes[profile_name]

    def stop_mount(self, profile_name):
        """Stops the mount and cleanly unmounts the directory for a profile."""
        profile = self.config.get_profile(profile_name)
        if not profile:
            return False
            
        process = self.mount_processes.get(profile_name)
        if process and process.state() == QProcess.ProcessState.Running:
            process.terminate()
            if not process.waitForFinished(3000):
                process.kill()
            if profile_name in self.mount_processes:
                del self.mount_processes[profile_name]
                
        # Force unmount if needed
        mount_path = str(profile.get("mount_path"))
        if self.is_currently_mounted(profile_name):
            try:
                subprocess.run(["fusermount3", "-u", mount_path], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if self.is_currently_mounted(profile_name):
                    subprocess.run(["umount", mount_path], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error executing force unmount for '{profile_name}': {e}")
                
        self.mount_status_changed.emit(profile_name, False, "Nicht verbunden")
        return True

    def stop_all_mounts(self):
        """Stops all active mounts. Called during app teardown."""
        profiles = list(self.mount_processes.keys())
        for profile_name in profiles:
            self.stop_mount(profile_name)

    def is_currently_mounted(self, profile_name):
        """Determines if the mount is active by checking /proc/mounts and os.path.ismount."""
        profile = self.config.get_profile(profile_name)
        if not profile:
            return False
            
        path = str(profile.get("mount_path"))
        try:
            # Check proc mounts first to detect ghost mounts
            if os.path.exists('/proc/mounts'):
                with open('/proc/mounts', 'r') as f:
                    mounts = f.read()
                abs_path = os.path.abspath(path)
                if abs_path in mounts or path in mounts:
                    return True
        except Exception as e:
            print(f"Error checking /proc/mounts: {e}")
            
        try:
            if os.path.exists(path):
                return os.path.ismount(path)
        except Exception:
            pass
            
        return False

    def get_space_stats(self, profile_name):
        """Runs rclone about to fetch quota statistics. Returns dict or None."""
        profile = self.config.get_profile(profile_name)
        if not profile:
            return None
            
        rclone_bin = self.find_rclone()
        remote_name = profile.get("remote_name")
        if not rclone_bin or not self.is_configured(remote_name):
            return None
            
        try:
            args = [
                rclone_bin,
                "--config", self.config.rclone_config_path,
                "--non-interactive",
                "about",
                f"{remote_name}:",
                "--json"
            ]
            
            res = subprocess.run(args, capture_output=True, text=True, timeout=8)
            if res.returncode == 0:
                return json.loads(res.stdout)
        except Exception as e:
            print(f"Error fetching storage stats for '{profile_name}': {e}")
            
        return None
