import os
import time
import json
import subprocess
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

class PrefetchManager(QThread):
    # Signals for updating the GUI and logging
    status_changed = pyqtSignal(str, str)  # (profile_name, status_text)
    file_prefetched = pyqtSignal(str, str, str)  # (profile_name, file_path, reason)
    log_message = pyqtSignal(str, str)  # (profile_name, message)

    def __init__(self, config, rclone_manager):
        super().__init__()
        self.config = config
        self.rclone_manager = rclone_manager
        self.is_running = True
        
        # Prefetch queue: list of dicts: {"profile_name": str, "relative_path": str, "reason": str}
        self.queue = []
        
        # State tracking: profile_name -> dict of relative_path -> mtime
        self.last_cache_states = {}
        
        # Last remote check timestamp: profile_name -> float
        self.last_remote_checks = {}
        
        # Session prefetch counter to prevent runaway downloads
        self.session_prefetched_counts = {}
        
        # General config values
        self.max_size_for_full_prefetch = 15 * 1024 * 1024  # 15 MB
        self.large_file_chunk_limit = 2 * 1024 * 1024      # 2 MB (prefetch beginning of large files)
        self.session_limit = 50                             # Max files to prefetch per mount session
        self.remote_check_interval = 300                     # 5 minutes
        
    def stop(self):
        """Stops the thread loop and wait for it to terminate."""
        self.is_running = False
        self.wait()

    def run(self):
        self.log_message.emit("System", "PrefetchManager-Thread gestartet.")
        
        while self.is_running:
            profiles = self.config.get_profiles()
            for profile in profiles:
                if not self.is_running:
                    break
                    
                name = profile.get("name")
                remote_name = profile.get("remote_name")
                mount_path = Path(profile.get("mount_path"))
                
                # Check if profile is active, mounted, and has prefetching enabled
                is_mounted = self.rclone_manager.is_currently_mounted(name)
                prefetch_enabled = profile.get("prefetch_enabled", True)
                
                if is_mounted and prefetch_enabled:
                    # Initialize states for newly mounted profiles
                    if name not in self.last_cache_states:
                        self.last_cache_states[name] = self._scan_vfs_cache(remote_name)
                        self.last_remote_checks[name] = 0
                        self.session_prefetched_counts[name] = 0
                        self.status_changed.emit(name, "Bereit")
                        self.log_message.emit(name, "[Prediction] Intelligentes Vorab-Herunterladen aktiviert.")

                    # 1. Sibling Prefetching (Monitor local VFS cache changes)
                    if profile.get("prefetch_siblings", True):
                        self._check_local_cache_access(profile)

                    # 2. Remote Activity Prefetching (Periodic query of recent changes)
                    if profile.get("prefetch_remote_recent", True):
                        now = time.time()
                        last_check = self.last_remote_checks.get(name, 0)
                        if now - last_check > self.remote_check_interval:
                            self._check_remote_recent_changes(profile)
                            self.last_remote_checks[name] = now

                    # 3. Process the queue for this profile
                    self._process_queue(profile)
                else:
                    # Clean up states when unmounted or disabled
                    if name in self.last_cache_states:
                        del self.last_cache_states[name]
                    if name in self.last_remote_checks:
                        del self.last_remote_checks[name]
                    if name in self.session_prefetched_counts:
                        del self.session_prefetched_counts[name]
                    
                    # Remove queued items for this profile
                    self.queue = [item for item in self.queue if item["profile_name"] != name]
                    
                    if not prefetch_enabled:
                        self.status_changed.emit(name, "Deaktiviert")
                    else:
                        self.status_changed.emit(name, "Nicht verbunden")

            # Sleep 5 seconds between iterations
            for _ in range(50):
                if not self.is_running:
                    break
                self.msleep(100) # Sleep 100ms in a loop to react quickly to shutdown

        self.log_message.emit("System", "PrefetchManager-Thread beendet.")

    def _scan_vfs_cache(self, remote_name):
        """Scans the local rclone VFS cache for this remote and returns relative paths -> mtimes."""
        cache_state = {}
        vfs_cache_base = Path.home() / ".cache" / "rclone" / "vfs" / remote_name
        
        if not vfs_cache_base.exists():
            return cache_state
            
        try:
            for root, _, files in os.walk(vfs_cache_base):
                for file in files:
                    full_path = Path(root) / file
                    # Skip temporary rclone state files, metadata, or cryptomator backups if trash
                    if file.endswith(".partial") or ".Trash-1000" in str(full_path):
                        continue
                    try:
                        rel_path = full_path.relative_to(vfs_cache_base)
                        mtime = full_path.stat().st_mtime
                        cache_state[str(rel_path)] = mtime
                    except Exception:
                        pass
        except Exception as e:
            # Silently catch directory read errors
            pass
            
        return cache_state

    def _check_local_cache_access(self, profile):
        """Compares current VFS cache with the last state to find newly accessed files and queues siblings."""
        name = profile.get("name")
        remote_name = profile.get("remote_name")
        mount_path = Path(profile.get("mount_path"))
        
        current_state = self._scan_vfs_cache(remote_name)
        old_state = self.last_cache_states.get(name, {})
        
        accessed_files = []
        
        for rel_path, mtime in current_state.items():
            # If a file is new or has a new mtime, it was accessed/modified
            if rel_path not in old_state or mtime > old_state[rel_path]:
                accessed_files.append(rel_path)
                
        # Update cache state
        self.last_cache_states[name] = current_state
        
        # Trigger prefetching for siblings of accessed files
        for rel_path in accessed_files:
            file_path = Path(rel_path)
            parent_dir = file_path.parent
            
            # Sibling directory on the mount
            mount_parent = mount_path / parent_dir
            if not mount_parent.is_dir():
                continue
                
            self.log_message.emit(name, f"[Prediction] Dateizugriff auf '{rel_path}' erkannt. Analysiere Ordner...")
            
            try:
                # Find sibling files in the same directory
                with os.scandir(mount_parent) as entries:
                    siblings = []
                    for entry in entries:
                        if entry.is_file() and not entry.name.startswith('.'):
                            # Relative path of the sibling
                            sibling_rel = str(parent_dir / entry.name) if str(parent_dir) != "." else entry.name
                            siblings.append((sibling_rel, entry.stat().st_size, entry.stat().st_mtime))
                            
                    # Sort siblings by modification time (newest first)
                    siblings.sort(key=lambda x: x[2], reverse=True)
                    
                    # Queue up to 5 sibling files that are not already cached
                    queued_count = 0
                    for sib_rel, sib_size, _ in siblings:
                        if queued_count >= 5:
                            break
                        if sib_rel == rel_path:
                            continue  # Skip the accessed file itself
                        if sib_rel in current_state:
                            continue  # Already cached
                            
                        # Check if already queued
                        if any(item["relative_path"] == sib_rel and item["profile_name"] == name for item in self.queue):
                            continue
                            
                        self.queue.append({
                            "profile_name": name,
                            "relative_path": sib_rel,
                            "reason": f"Nachbardatei von '{file_path.name}'",
                            "size": sib_size
                        })
                        queued_count += 1
                        
                    if queued_count > 0:
                        self.log_message.emit(name, f"[Prediction] {queued_count} Nachbardateien in Download-Warteschlange eingereiht.")
            except Exception as e:
                self.log_message.emit(name, f"[Prediction] Fehler beim Suchen von Nachbardateien: {e}")

    def _check_remote_recent_changes(self, profile):
        """Runs rclone lsjson to find files modified in the last 24h and queues them."""
        name = profile.get("name")
        remote_name = profile.get("remote_name")
        rclone_bin = self.config.rclone_path or self.rclone_manager.find_rclone()
        
        if not rclone_bin:
            return
            
        self.log_message.emit(name, "[Prediction] Suche auf Google Drive nach kürzlich bearbeiteten Dateien...")
        
        try:
            # Build rclone command
            cmd = [
                rclone_bin,
                "--config", self.config.rclone_config_path,
                "lsjson",
                f"{remote_name}:",
                "--max-age", "24h",
                "--files-only",
                "--recursive",
                "--exclude", "**/.*/**",
                "--exclude", "**/.venv/**",
                "--exclude", "**/.git/**",
                "--exclude", "**/.Trash-1000/**"
            ]
            
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                self.log_message.emit(name, f"[Prediction] Remote-Scan-Fehler: {res.stderr.strip()}")
                return
                
            files_list = json.loads(res.stdout)
            if not files_list:
                self.log_message.emit(name, "[Prediction] Keine kürzlich geänderten Dateien gefunden.")
                return
                
            # Filter and add to queue
            queued_count = 0
            current_cache = self.last_cache_states.get(name, {})
            
            for file_info in files_list:
                rel_path = file_info.get("Path")
                size = file_info.get("Size", 0)
                if not rel_path:
                    continue
                    
                # Skip if already cached
                if rel_path in current_cache:
                    continue
                    
                # Skip if already queued
                if any(item["relative_path"] == rel_path and item["profile_name"] == name for item in self.queue):
                    continue
                    
                # Limit size or extensions if needed, here we just queue everything and handle sizes during prefetching
                self.queue.append({
                    "profile_name": name,
                    "relative_path": rel_path,
                    "reason": "kürzlich geändert",
                    "size": size
                })
                queued_count += 1
                
            if queued_count > 0:
                self.log_message.emit(name, f"[Prediction] {queued_count} kürzlich geänderte Dateien von Google Drive eingereiht.")
        except subprocess.TimeoutExpired:
            self.log_message.emit(name, "[Prediction] Zeitüberschreitung bei der Suche nach kürzlich bearbeiteten Dateien.")
        except Exception as e:
            self.log_message.emit(name, f"[Prediction] Fehler beim Remote-Scan: {e}")

    def _process_queue(self, profile):
        """Fetches the next file in the queue for this profile."""
        name = profile.get("name")
        mount_path = Path(profile.get("mount_path"))
        
        # Get items in queue for this profile
        profile_queue = [item for item in self.queue if item["profile_name"] == name]
        
        if not profile_queue:
            return
            
        # Check session limit to prevent runaway bandwidth usage
        count = self.session_prefetched_counts.get(name, 0)
        if count >= self.session_limit:
            self.status_changed.emit(name, "Limit erreicht (Pause)")
            # Remove all queued files for this profile since limit is hit
            self.queue = [item for item in self.queue if item["profile_name"] != name]
            self.log_message.emit(name, f"[Prediction] Limit von {self.session_limit} Vorab-Downloads für diese Sitzung erreicht. Pausiert.")
            return
            
        # Update status
        self.status_changed.emit(name, f"Vorab-Herunterladen ({len(profile_queue)} ausstehend)")
        
        # Get next item
        item = profile_queue[0]
        self.queue.remove(item)
        
        rel_path = item["relative_path"]
        reason = item["reason"]
        file_size = item.get("size", 0)
        full_path = mount_path / rel_path
        
        # Double check if file actually exists on mount
        if not full_path.exists():
            return
            
        try:
            # Determine limit: read fully if small, otherwise read first chunk
            chunk_limit = self.max_size_for_full_prefetch
            if file_size > self.max_size_for_full_prefetch:
                chunk_limit = self.large_file_chunk_limit
                self.log_message.emit(name, f"[Prediction] Lade Anfang von '{rel_path}' ({reason}, Größe: {file_size / (1024**2):.1f} MB)...")
            else:
                self.log_message.emit(name, f"[Prediction] Lade '{rel_path}' vollständig ({reason}, Größe: {file_size / 1024:.1f} KB)...")
                
            # Perform read
            total_read = 0
            start_time = time.time()
            
            with open(full_path, 'rb') as f:
                while total_read < chunk_limit and self.is_running:
                    chunk = f.read(256 * 1024) # 256 KB chunks
                    if not chunk:
                        break
                    total_read += len(chunk)
                    
                    # Yield CPU/I/O briefly
                    self.msleep(10)
                    
            if not self.is_running:
                return
                
            elapsed = time.time() - start_time
            self.session_prefetched_counts[name] = count + 1
            self.file_prefetched.emit(name, rel_path, reason)
            
            # Throttle subsequent fetches to preserve internet bandwidth
            time.sleep(1.0)
            
        except Exception as e:
            self.log_message.emit(name, f"[Prediction] Fehler beim Vorab-Laden von '{rel_path}': {e}")
            
        # Check if queue became empty
        remaining = [item for item in self.queue if item["profile_name"] == name]
        if not remaining:
            self.status_changed.emit(name, "Bereit")
