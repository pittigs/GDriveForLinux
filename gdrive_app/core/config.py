import os
import json
from pathlib import Path

class AppConfig:
    CONFIG_DIR = Path.home() / ".config" / "gdrive-mount"
    CONFIG_FILE = CONFIG_DIR / "settings.json"
    RCLONE_CONF_FILE = CONFIG_DIR / "rclone.conf"

    DEFAULT_GLOBAL = {
        "autostart": True,
        "rclone_path": ""
    }

    DEFAULT_PROFILE = {
        "name": "Google Drive",
        "remote_name": "gdrive",
        "mount_path": str(Path.home() / "GoogleDrive"),
        "mount_on_start": True,
        "cache_mode": "full",
        "write_back_delay": "5s",
        "bw_limit": "",
        "keep_cached": False,
        "prefetch_enabled": True,
        "prefetch_remote_recent": True,
        "prefetch_siblings": True
    }

    def __init__(self):
        self.settings = {}
        self.load()

    def load(self):
        """Loads configuration and migrates older single-account config if present."""
        try:
            self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if self.CONFIG_FILE.exists():
                with open(self.CONFIG_FILE, "r") as f:
                    loaded_data = json.load(f)
                
                # Check if it is v1 format (contains single-account keys instead of 'profiles')
                if "profiles" not in loaded_data:
                    self.migrate_v1_to_v2(loaded_data)
                else:
                    self.settings = loaded_data
                    # Ensure global keys exist
                    if "global" not in self.settings:
                        self.settings["global"] = self.DEFAULT_GLOBAL.copy()
                    else:
                        self.settings["global"] = {**self.DEFAULT_GLOBAL, **self.settings["global"]}
            else:
                self.settings = {
                    "profiles": [],
                    "global": self.DEFAULT_GLOBAL.copy()
                }
                self.save()
        except Exception as e:
            print(f"Error loading configuration: {e}")
            self.settings = {
                "profiles": [],
                "global": self.DEFAULT_GLOBAL.copy()
            }

    def migrate_v1_to_v2(self, old_data):
        """Migrates single-account layout into a structured profile list."""
        print("[AppConfig] Migrating config layout from v1 to v2 (multi-account)...")
        
        # Merge old settings with default profile values
        profile = {
            "name": "Google Drive",
            "remote_name": old_data.get("remote_name", "gdrive"),
            "mount_path": old_data.get("mount_path", str(Path.home() / "GoogleDrive")),
            "mount_on_start": old_data.get("mount_on_start", True),
            "cache_mode": old_data.get("cache_mode", "full"),
            "write_back_delay": "5s",
            "bw_limit": ""
        }
        
        self.settings = {
            "profiles": [profile],
            "global": {
                "autostart": old_data.get("autostart", True),
                "rclone_path": old_data.get("rclone_path", "")
            }
        }
        self.save()

    def save(self):
        """Saves current configuration to the settings file."""
        try:
            self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving configuration: {e}")

    # Profile management methods
    def get_profiles(self):
        profiles = self.settings.get("profiles", [])
        # Ensure all default keys are present in each profile
        for i, profile in enumerate(profiles):
            self.settings["profiles"][i] = {**self.DEFAULT_PROFILE, **profile}
        return self.settings["profiles"]

    def get_profile(self, name):
        for profile in self.get_profiles():
            if profile.get("name") == name:
                return profile
        return None

    def add_profile(self, profile):
        if "profiles" not in self.settings:
            self.settings["profiles"] = []
            
        # Merge with default profile values to ensure all keys are present
        merged_profile = {**self.DEFAULT_PROFILE, **profile}
        self.settings["profiles"].append(merged_profile)
        self.save()

    def update_profile(self, name, updated_profile):
        profiles = self.get_profiles()
        for idx, profile in enumerate(profiles):
            if profile.get("name") == name:
                profiles[idx] = {**self.DEFAULT_PROFILE, **updated_profile}
                self.settings["profiles"] = profiles
                self.save()
                return True
        return False

    def remove_profile(self, name):
        profiles = self.get_profiles()
        new_profiles = [p for p in profiles if p.get("name") != name]
        if len(new_profiles) != len(profiles):
            self.settings["profiles"] = new_profiles
            self.save()
            return True
        return False

    # Global properties
    @property
    def autostart(self):
        return self.settings.get("global", {}).get("autostart", self.DEFAULT_GLOBAL["autostart"])

    @autostart.setter
    def autostart(self, value):
        if "global" not in self.settings:
            self.settings["global"] = self.DEFAULT_GLOBAL.copy()
        self.settings["global"]["autostart"] = bool(value)
        self.save()

    @property
    def rclone_path(self):
        return self.settings.get("global", {}).get("rclone_path", self.DEFAULT_GLOBAL["rclone_path"])

    @rclone_path.setter
    def rclone_path(self, value):
        if "global" not in self.settings:
            self.settings["global"] = self.DEFAULT_GLOBAL.copy()
        self.settings["global"]["rclone_path"] = str(value)
        self.save()

    @property
    def rclone_config_path(self):
        return str(self.RCLONE_CONF_FILE)
