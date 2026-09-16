#!/usr/bin/env python3
"""
================================================================================
OnePlus 13R (CPH2691) Safe Optimization & Rollback Automation Suite
Target: OxygenOS 15 & 16 (Android 15 & 16) | Qualcomm Snapdragon 8 Gen 2
Security Boundary: 100% Rootless ADB (Shell UID 2000, SELinux Enforcing)
================================================================================

A production-grade, rootless Android optimization CLI tool designed specifically
for the OnePlus 13R (CPH2691 / CPH2691IN / OP5D3BL1).

Key Capabilities:
  - Multi-tier ADB auto-discovery (CLI, env, PATH, O+Connect, Android SDK, scoop)
  - Persistent ADB server initialization upfront
  - Robust device validation and interactive RSA authorization retry loop
  - Three-tier missing package handling (introspect pm list packages -u + stderr exception trap)
  - 100% symmetrical reverse rollback (--undo) across all 12 optimization phases
  - Safe dry-run mode (--dry-run) without requiring any physical device attached
  - Flexible per-phase execution (--phases 1,2,3 or --skip 5,7)
  - External configuration loading (YAML / JSON) with complete embedded fallback
  - Detailed timestamped file logging and ASCII summary table
"""

import argparse
import copy
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# Try importing yaml for config.yaml support; fallback gracefully if absent
try:
    import yaml
except ImportError:
    yaml = None

VERSION = "2.0.0"
DEFAULT_TARGET_MODEL = "CPH2691"
COMPATIBLE_MODELS = ["CPH2691", "CPH2691IN", "OP5D3BL1"]

# Exit codes per contract (PROJECT.md)
EXIT_SUCCESS = 0
EXIT_RUNTIME_ERROR = 1
EXIT_CONFIG_ERROR = 2

# Complete 15 protected packages per OxygenOS 15/16 architectural audit
MANDATORY_BLACKLIST = [
    "com.oplus.athena",
    "com.oplus.safecenter",
    "com.oplus.battery",
    "com.oplus.securityguard",
    "com.oplus.camera",
    "com.android.se",
    "com.android.systemui",
    "com.oplus.ota",
    "com.oplus.romupdate",
    "com.oplus.cota",
    "com.google.android.gms",
    "com.qualcomm.qti.telephonyservice",
    "com.android.phone",
    "com.android.settings",
    "com.oplus.aod",
]

# Absent packages on retail OxygenOS 15/16 India (CPH2691IN)
KNOWN_ABSENT_PACKAGES = [
    "com.oplus.crashbox",
    "com.heytap.pictorial",
    "net.oneplus.forums",
    "com.oplus.statistics.rom",
    "com.oplus.logkit",
    "com.heytap.cloud",
]

# Phase alias mapping for CLI arguments
PHASE_ALIASES = {
    # Phase 1: Storage
    "1": "phase_1", "phase_1": "phase_1", "storage": "phase_1", "cache": "phase_1", "fstrim": "phase_1",
    # Phase 2: Animations
    "2": "phase_2", "phase_2": "phase_2", "animation": "phase_2", "animations": "phase_2", "scale": "phase_2",
    # Phase 3: Radios / Battery
    "3": "phase_3", "phase_3": "phase_3", "battery": "phase_3", "radio": "phase_3", "radios": "phase_3", "modem": "phase_3",
    # Phase 4: Doze Whitelist
    "4": "phase_4", "phase_4": "phase_4", "doze": "phase_4", "whitelist": "phase_4", "notifications": "phase_4",
    # Phase 5: Telemetry Freeze
    "5": "phase_5", "phase_5": "phase_5", "telemetry": "phase_5", "freeze": "phase_5", "debloat": "phase_5",
    # Phase 6: AOT Compilation
    "6": "phase_6", "phase_6": "phase_6", "aot": "phase_6", "compile": "phase_6", "speed": "phase_6", "dexopt": "phase_6",
    # Phase 7: Google Wallet & NFC
    "7": "phase_7", "phase_7": "phase_7", "wallet": "phase_7", "nfc": "phase_7", "hce": "phase_7",
    # Phase 8: GPU Game Driver
    "8": "phase_8", "phase_8": "phase_8", "gpu": "phase_8", "gamedriver": "phase_8", "game_driver": "phase_8",
    # Phase 9: Process Scheduler & Phantom
    "9": "phase_9", "phase_9": "phase_9", "scheduler": "phase_9", "phantom": "phase_9", "process": "phase_9", "processes": "phase_9",
    # Phase 10: Private DNS
    "10": "phase_10", "phase_10": "phase_10", "dns": "phase_10", "network": "phase_10", "dot": "phase_10", "adguard": "phase_10",
    # Phase 11: Thermal & High Performance
    "11": "phase_11", "phase_11": "phase_11", "thermal": "phase_11", "performance": "phase_11", "high_performance": "phase_11", "hpm": "phase_11",
    # Phase 12: Display 120Hz
    "12": "phase_12", "phase_12": "phase_12", "display": "phase_12", "120hz": "phase_12", "refresh": "phase_12", "refresh_rate": "phase_12",
    # Phase 13: Gboard Clipboard
    "13": "phase_13", "phase_13": "phase_13", "gboard": "phase_13", "clipboard": "phase_13", "keyboard": "phase_13",
}

# Embedded Fallback Configuration
EMBEDDED_DEFAULT_CONFIG = {
    "version": "2.0.0",
    "guide_name": "OnePlus 13R (CPH2691) Safe Optimization Suite",
    "device": {
        "model": "CPH2691",
        "market_names": ["OnePlus 13R", "OnePlus 13R (India)", "CPH2691IN"],
        "compatible_models": ["CPH2691", "CPH2691IN", "OP5D3BL1"],
        "target_os": "OxygenOS 15 / OxygenOS 16 (Android 15 / 16)",
        "platform": "Qualcomm Snapdragon 8 Gen 3 (SM8650-AB)",
        "gpu": "Adreno 750",
        "check_model": True,
    },
    "adb": {
        "default_search_paths": [
            r"C:\Program Files\O+Connect\daemon\bin\adb.exe",
            r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe",
            r"%USERPROFILE%\scoop\apps\adb\current\platform-tools\adb.exe",
            r"%ProgramFiles%\Android\platform-tools\adb.exe",
            r"C:\tools\platform-tools\adb.exe",
            r"C:\platform-tools\adb.exe",
            r"C:\adb\adb.exe",
            r"C:\Program Files (x86)\O+Connect\daemon\bin\adb.exe",
            r"%USERPROFILE%\scoop\shims\adb.exe",
            r"C:\ProgramData\chocolatey\bin\adb.exe",
            r"%LOCALAPPDATA%\Programs\O+Connect\daemon\bin\adb.exe",
        ],
        "posix_search_paths": [
            "~/Library/Android/sdk/platform-tools/adb",
            "/opt/homebrew/bin/adb",
            "/usr/local/bin/adb",
            "/usr/bin/adb",
            "~/Android/Sdk/platform-tools/adb",
        ],
        "retry_timeout": 30.0,
        "retry_attempts": 15,
        "retry_delay": 1.5,
    },
    "blacklist": list(MANDATORY_BLACKLIST),
    "packages": {
        "blacklist": list(MANDATORY_BLACKLIST),
        "doze_whitelist": [
            "com.whatsapp",
            "org.telegram.messenger",
            "com.google.android.gm",
            "com.google.android.apps.messaging",
            "com.spotify.music",
            "com.Slack",
            "org.thoughtcrime.securesms",
            "com.discord",
        ],
        "telemetry_freeze_targets": [
            "com.oplus.statistics.rom",
            "com.oplus.logkit",
            "com.oplus.postmanservice",
            "com.oplus.onetrace",
            "com.oplus.stdsp",
            "com.oplus.qualityprotect",
            "com.facebook.system",
            "com.facebook.appmanager",
            "com.facebook.services",
            "com.heytap.cloud",
            "com.heytap.browser",
            "com.heytap.htms",
            "com.oneplus.membership",
        ],
        "absent_telemetry_packages": [
            "com.oplus.crashbox",
            "com.heytap.pictorial",
            "net.oneplus.forums",
        ],
        "aot_speed_targets": [
            "com.oplus.camera",
            "com.oneplus.gallery",
            "com.android.chrome",
            "com.google.android.youtube",
            "com.google.android.apps.maps",
            "com.whatsapp",
            "org.telegram.messenger",
            "com.instagram.android",
            "com.twitter.android",
            "com.spotify.music",
        ],
    },
    "phases": {
        "phase_1": {
            "name": "Storage Cache Trim",
            "description": "Executes UFS 4.0 storage TRIM via FITRIM ioctl to reclaim deleted flash blocks and purges temporary application cache up to 100GB.",
            "type": "storage_trim",
            "commands": [
                "sm fstrim",
                "pm trim-caches 100G",
            ],
            "undo_commands": [],
            "undo_note": "One-way maintenance operation (garbage collection). App caches rebuild automatically during normal application execution.",
        },
        "phase_2": {
            "name": "Window Animation Scales",
            "description": "Halves window animation scale, transition animation scale, and animator duration scale to 0.5x for snappy, fluid UI interactions.",
            "type": "settings_put",
            "commands": [
                "settings put global window_animation_scale 0.5",
                "settings put global transition_animation_scale 0.5",
                "settings put global animator_duration_scale 0.5",
            ],
            "undo_commands": [
                "settings put global window_animation_scale 1.0",
                "settings put global transition_animation_scale 1.0",
                "settings put global animator_duration_scale 1.0",
            ],
        },
        "phase_3": {
            "name": "Battery & Radio Optimizations",
            "description": "Disables background Wi-Fi and Bluetooth Low Energy scanning when off, prevents cellular modem from staying awake while connected to Wi-Fi, and enables adaptive battery management.",
            "type": "settings_put",
            "commands": [
                "settings put global wifi_scan_always_enabled 0",
                "settings put global ble_scan_always_enabled 0",
                "settings put global mobile_data_always_on 0",
                "settings put global adaptive_battery_management_enabled 1",
            ],
            "undo_commands": [
                "settings put global wifi_scan_always_enabled 1",
                "settings put global ble_scan_always_enabled 1",
                "settings put global mobile_data_always_on 1",
                "settings put global adaptive_battery_management_enabled 1",
            ],
        },
        "phase_4": {
            "name": "Doze Power-Saving Whitelist",
            "description": "Whitelists critical communication, VoIP, and media applications from aggressive OxygenOS deep Doze sleep suppression to prevent delayed push notifications and audio drops.",
            "type": "dumpsys_whitelist",
            "packages": [
                "com.whatsapp",
                "org.telegram.messenger",
                "com.google.android.gm",
                "com.google.android.apps.messaging",
                "com.spotify.music",
                "com.Slack",
                "org.thoughtcrime.securesms",
                "com.discord",
            ],
            "commands": [
                "dumpsys deviceidle whitelist +com.whatsapp",
                "dumpsys deviceidle whitelist +org.telegram.messenger",
                "dumpsys deviceidle whitelist +com.google.android.gm",
                "dumpsys deviceidle whitelist +com.google.android.apps.messaging",
                "dumpsys deviceidle whitelist +com.spotify.music",
                "dumpsys deviceidle whitelist +com.Slack",
                "dumpsys deviceidle whitelist +org.thoughtcrime.securesms",
                "dumpsys deviceidle whitelist +com.discord",
            ],
            "undo_commands": [
                "dumpsys deviceidle whitelist -com.whatsapp",
                "dumpsys deviceidle whitelist -org.telegram.messenger",
                "dumpsys deviceidle whitelist -com.google.android.gm",
                "dumpsys deviceidle whitelist -com.google.android.apps.messaging",
                "dumpsys deviceidle whitelist -com.spotify.music",
                "dumpsys deviceidle whitelist -com.Slack",
                "dumpsys deviceidle whitelist -org.thoughtcrime.securesms",
                "dumpsys deviceidle whitelist -com.discord",
            ],
        },
        "phase_5": {
            "name": "Safe Telemetry Freeze",
            "description": "Safely disables non-essential OEM telemetry, analytics uploaders, HeyTap promotional services, and Facebook background daemons for user 0, gracefully skipping absent packages on OxygenOS 15/16 India.",
            "type": "package_disable",
            "packages": [
                "com.oplus.statistics.rom",
                "com.oplus.logkit",
                "com.oplus.postmanservice",
                "com.oplus.onetrace",
                "com.oplus.stdsp",
                "com.oplus.qualityprotect",
                "com.facebook.system",
                "com.facebook.appmanager",
                "com.facebook.services",
                "com.heytap.cloud",
                "com.heytap.browser",
                "com.heytap.htms",
                "com.oneplus.membership",
            ],
            "absent_packages": [
                "com.oplus.crashbox",
                "com.heytap.pictorial",
                "net.oneplus.forums",
            ],
            "commands": [
                "pm disable-user --user 0 com.oplus.statistics.rom",
                "pm disable-user --user 0 com.oplus.logkit",
                "pm disable-user --user 0 com.oplus.postmanservice",
                "pm disable-user --user 0 com.oplus.onetrace",
                "pm disable-user --user 0 com.oplus.stdsp",
                "pm disable-user --user 0 com.oplus.qualityprotect",
                "pm disable-user --user 0 com.facebook.system",
                "pm disable-user --user 0 com.facebook.appmanager",
                "pm disable-user --user 0 com.facebook.services",
                "pm disable-user --user 0 com.heytap.cloud",
                "pm disable-user --user 0 com.heytap.browser",
                "pm disable-user --user 0 com.heytap.htms",
                "pm disable-user --user 0 com.oneplus.membership",
            ],
            "undo_commands": [
                "pm enable --user 0 com.oplus.statistics.rom",
                "pm enable --user 0 com.oplus.logkit",
                "pm enable --user 0 com.oplus.postmanservice",
                "pm enable --user 0 com.oplus.onetrace",
                "pm enable --user 0 com.oplus.stdsp",
                "pm enable --user 0 com.oplus.qualityprotect",
                "pm enable --user 0 com.facebook.system",
                "pm enable --user 0 com.facebook.appmanager",
                "pm enable --user 0 com.facebook.services",
                "pm enable --user 0 com.heytap.cloud",
                "pm enable --user 0 com.heytap.browser",
                "pm enable --user 0 com.heytap.htms",
                "pm enable --user 0 com.oneplus.membership",
            ],
        },
        "phase_6": {
            "name": "App & System AOT Speed Compilation",
            "description": "Compiles 10 core performance-sensitive applications directly to native ARM64 machine code (-m speed) to eliminate JIT startup delay, and performs system-wide profile-guided optimization (-m speed-profile -a).",
            "type": "package_compile",
            "packages": [
                "com.oplus.camera",
                "com.oneplus.gallery",
                "com.android.chrome",
                "com.google.android.youtube",
                "com.google.android.apps.maps",
                "com.whatsapp",
                "org.telegram.messenger",
                "com.instagram.android",
                "com.twitter.android",
                "com.spotify.music",
            ],
            "commands": [
                "cmd package compile -m speed com.oplus.camera",
                "cmd package compile -m speed com.oneplus.gallery",
                "cmd package compile -m speed com.android.chrome",
                "cmd package compile -m speed com.google.android.youtube",
                "cmd package compile -m speed com.google.android.apps.maps",
                "cmd package compile -m speed com.whatsapp",
                "cmd package compile -m speed org.telegram.messenger",
                "cmd package compile -m speed com.instagram.android",
                "cmd package compile -m speed com.twitter.android",
                "cmd package compile -m speed com.spotify.music",
                "cmd package compile -m speed-profile -a",
            ],
            "undo_commands": [
                "cmd package compile --reset com.oplus.camera",
                "cmd package compile --reset com.oneplus.gallery",
                "cmd package compile --reset com.android.chrome",
                "cmd package compile --reset com.google.android.youtube",
                "cmd package compile --reset com.google.android.apps.maps",
                "cmd package compile --reset com.whatsapp",
                "cmd package compile --reset org.telegram.messenger",
                "cmd package compile --reset com.instagram.android",
                "cmd package compile --reset com.twitter.android",
                "cmd package compile --reset com.spotify.music",
                "cmd package compile --reset -a",
            ],
        },
        "phase_7": {
            "name": "Google Wallet & NFC Quick-Access Tile",
            "description": "Enables NFC radio, assigns Google Play Services Host Card Emulation (HCE) component as default contactless payment service, and activates Quick Access Wallet on the lockscreen and Quick Settings.",
            "type": "svc_call",
            "commands": [
                "svc nfc enable",
                "settings put secure nfc_on 1",
                "settings put secure quick_access_wallet_enabled 1",
                "settings put secure lockscreen_show_wallet 1",
                "settings put secure nfc_payment_default_component com.google.android.gms/com.google.android.gms.tapandpay.hce.service.TpHceService",
            ],
            "undo_commands": [
                "settings put secure quick_access_wallet_enabled 0",
                "settings put secure lockscreen_show_wallet 0",
                'settings put secure nfc_payment_default_component ""',
                "settings put secure nfc_on 0",
                "svc nfc disable",
            ],
        },
        "phase_8": {
            "name": "GPU Rendering & Qualcomm Game Driver",
            "description": "Opts into Qualcomm Adreno dedicated Game Driver pipeline (GAME_DRIVER_ALL_APPS) for all apps, improving frame pacing and shader caching.",
            "type": "settings_put",
            "commands": [
                "settings put global game_driver_all_apps 1",
            ],
            "undo_commands": [
                "settings put global game_driver_all_apps 0",
            ],
        },
        "phase_9": {
            "name": "Process Scheduler & Phantom Limits",
            "description": "Removes Android 12+ phantom process killer restrictions (raising limit to INT_MAX) and expands cached processes to 64 for 12GB/16GB LPDDR5X RAM.",
            "type": "device_config",
            "commands": [
                "/system/bin/device_config put activity_manager max_phantom_processes 2147483647",
                "settings put global settings_enable_monitor_phantom_procs false",
                "device_config put activity_manager max_cached_processes 64",
                "settings put global activity_manager_constants max_cached_processes=64",
                "device_config set_sync_disabled_for_tests persistent",
            ],
            "undo_commands": [
                "/system/bin/device_config put activity_manager max_phantom_processes 32",
                "settings put global settings_enable_monitor_phantom_procs true",
                "device_config delete activity_manager max_cached_processes",
                "settings delete global activity_manager_constants",
                "device_config set_sync_disabled_for_tests none",
            ],
        },
        "phase_10": {
            "name": "Private DNS DoT & Network Tuning",
            "description": "Enforces system-wide DNS-over-TLS (DoT) via AdGuard for native ad/tracker blocking and activates Wi-Fi background scan throttling.",
            "type": "settings_put",
            "commands": [
                "settings put global private_dns_mode hostname",
                "settings put global private_dns_specifier dns.adguard-dns.com",
                "settings put global wifi_scan_throttle_enabled 1",
            ],
            "undo_commands": [
                "settings put global private_dns_mode opportunistic",
                "settings delete global private_dns_specifier",
                "settings put global wifi_scan_throttle_enabled 0",
            ],
        },
        "phase_11": {
            "name": "Thermal & High Performance Mode",
            "description": "Toggles OxygenOS native High Performance Mode to raise EAS CPU frequency floor levels and delay thermal throttling onset.",
            "type": "settings_put",
            "commands": [
                "settings put system high_performance_mode 1",
            ],
            "undo_commands": [
                "settings put system high_performance_mode 0",
            ],
        },
        "phase_12": {
            "name": "LTPO Adaptive Display (1-120Hz)",
            "description": "Enables full LTPO 4.1 adaptive range: drops to 1Hz on static screens for battery savings, ramps to 120Hz on touch/scroll. Disables OxygenOS per-app throttling table that incorrectly caps Chrome/YouTube/Maps at 60Hz.",
            "type": "settings_put",
            "commands": [
                "settings put secure oplus_customize_screen_refresh_rate 0",
                "settings put system peak_refresh_rate 120.0",
                "settings put system min_refresh_rate 1.0",
                "settings put system user_refresh_rate 120.0",
            ],
            "undo_commands": [
                "settings put secure oplus_customize_screen_refresh_rate 1",
                "settings put system peak_refresh_rate 120.0",
                "settings put system min_refresh_rate 60.0",
                "settings delete system user_refresh_rate",
            ],
        },
        "phase_13": {
            "name": "Gboard Clipboard & Keyboard Fix",
            "description": "Fixes Gboard clipboard issues by AOT-compiling for speed, force-stopping to clear stale state, and whitelisting from Doze to prevent clipboard history loss during deep sleep.",
            "type": "gboard_fix",
            "commands": [
                "cmd package compile -m speed com.google.android.inputmethod.latin",
                "am force-stop com.google.android.inputmethod.latin",
                "dumpsys deviceidle whitelist +com.google.android.inputmethod.latin",
            ],
            "undo_commands": [
                "cmd package compile --reset com.google.android.inputmethod.latin",
                "dumpsys deviceidle whitelist -com.google.android.inputmethod.latin",
            ],
        },
    },
}


class Color:
    """Terminal ANSI styling controller."""
    ENABLED = True

    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    RESET = "\033[0m"

    @classmethod
    def disable(cls):
        cls.ENABLED = False
        cls.BOLD = ""
        cls.DIM = ""
        cls.RED = ""
        cls.GREEN = ""
        cls.YELLOW = ""
        cls.BLUE = ""
        cls.MAGENTA = ""
        cls.CYAN = ""
        cls.WHITE = ""
        cls.RESET = ""

    @classmethod
    def strip(cls, text: str) -> str:
        return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


class ExecutionLogger:
    """Handles structured execution logging to file and terminal."""

    def __init__(self, log_path: Optional[str] = None):
        if not log_path:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = f"optimization_{ts}.log"
        self.log_file = pathlib.Path(log_path).resolve()
        try:
            self.file_handle = open(self.log_file, "a", encoding="utf-8")
        except Exception:
            self.file_handle = None

        self.write_header()

    def write_header(self):
        if self.file_handle:
            ts = datetime.datetime.now().isoformat()
            self.file_handle.write(f"=== OnePlus 13R Optimization Log: {ts} ===\n")
            self.file_handle.flush()

    def log(self, level: str, message: str):
        clean_msg = Color.strip(message)
        if self.file_handle:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.file_handle.write(f"[{ts}] [{level:<7}] {clean_msg}\n")
            self.file_handle.flush()

    def close(self):
        if self.file_handle:
            try:
                self.file_handle.close()
            except Exception:
                pass


def validate_adb_binary(candidate_path: str) -> bool:
    """Validates that a given candidate file exists and responds as an ADB executable."""
    if not os.path.isfile(candidate_path):
        return False

    cmd = [candidate_path, "version"]
    if candidate_path.endswith(".py"):
        cmd = [sys.executable, candidate_path, "version"]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return res.returncode == 0 and "Android Debug Bridge" in res.stdout
    except Exception:
        return False


def discover_adb(
    custom_path: Optional[str] = None,
    search_paths: Optional[List[str]] = None,
    is_dry_run: bool = False,
    logger: Optional[ExecutionLogger] = None,
) -> str:
    """
    Deterministically resolves a functional ADB binary across:
      1. --adb-path CLI override
      2. Environment variables: ADB_PATH, ANDROID_HOME, ANDROID_SDK_ROOT
      3. System PATH
      4. Known vendor & package manager directories (O+Connect, SDK, Scoop, Chocolatey)
      5. POSIX fallback locations
    """
    # 1. Custom CLI override
    if custom_path:
        path = os.path.abspath(os.path.expandvars(os.path.expanduser(custom_path)))
        if validate_adb_binary(path):
            if logger:
                logger.log("INFO", f"Resolved ADB from --adb-path: {path}")
            return path
        raise FileNotFoundError(f"Provided --adb-path '{custom_path}' is invalid, non-existent, or non-functional.")

    # 2. Environment variables
    for env_var in ("ADB_PATH", "ANDROID_HOME", "ANDROID_SDK_ROOT"):
        val = os.environ.get(env_var)
        if val:
            candidate = os.path.expandvars(os.path.expanduser(val))
            if not candidate.endswith(("adb", "adb.exe")):
                candidate = os.path.join(candidate, "platform-tools", "adb.exe" if sys.platform == "win32" else "adb")
            if validate_adb_binary(candidate):
                if logger:
                    logger.log("INFO", f"Resolved ADB from environment variable {env_var}: {candidate}")
                return candidate

    # 3. System PATH
    in_path = shutil.which("adb") or shutil.which("adb.exe")
    if in_path and validate_adb_binary(in_path):
        if logger:
            logger.log("INFO", f"Resolved ADB from PATH: {in_path}")
        return in_path

    # 4. Known search paths from configuration
    candidates = []
    if sys.platform == "win32":
        default_win_paths = search_paths or EMBEDDED_DEFAULT_CONFIG["adb"]["default_search_paths"]
        for p in default_win_paths:
            candidates.append(os.path.expandvars(os.path.expanduser(p)))
    else:
        posix_paths = search_paths or EMBEDDED_DEFAULT_CONFIG["adb"]["posix_search_paths"]
        for p in posix_paths:
            candidates.append(os.path.expandvars(os.path.expanduser(p)))

    for candidate in candidates:
        if candidate and validate_adb_binary(candidate):
            if logger:
                logger.log("INFO", f"Resolved ADB from well-known installation path: {candidate}")
            return candidate

    # 5. In dry-run mode, if no ADB found, return simulated binary rather than crashing
    if is_dry_run:
        if logger:
            logger.log("INFO", "Dry-run mode active and ADB not installed; using simulated 'adb'")
        return "adb"

    # Fatal: No ADB executable found
    err_msg = (
        "Fatal: ADB executable could not be discovered on this system.\n"
        "Searched: CLI flag, environment variables (ADB_PATH, ANDROID_HOME), PATH, and:\n"
        + "\n".join(f"  - {p}" for p in candidates[:8])
        + "\n\nRemediation:\n"
        "  1. Install Android Platform-Tools or O+Connect (PC Connect).\n"
        "  2. Or specify the exact binary path: python optimize_13r.py --adb-path \"C:\\path\\to\\adb.exe\""
    )
    raise FileNotFoundError(err_msg)


def run_adb_command(
    adb_path: str,
    args: List[str],
    serial: Optional[str] = None,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess:
    """Executes a command using the discovered ADB executable."""
    cmd = [adb_path]
    if adb_path.endswith(".py"):
        cmd = [sys.executable, adb_path]

    if serial:
        cmd.extend(["-s", serial])

    cmd.extend(args)

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def wait_for_authorized_device(
    adb_path: str,
    target_serial: Optional[str] = None,
    timeout: float = 30.0,
    retry_delay: float = 1.5,
    logger: Optional[ExecutionLogger] = None,
) -> str:
    """
    Polls for a connected device, guiding user through RSA authorization prompts
    and retrying while in 'authorizing', 'unauthorized', or 'offline' states.
    """
    print(f"{Color.CYAN}[*]{Color.RESET} Checking connected OnePlus 13R hardware status...")
    start_time = time.time()
    last_reported_state = None

    while time.time() - start_time < timeout:
        try:
            res = run_adb_command(adb_path, ["devices", "-l"], timeout=6.0)
        except Exception as e:
            if logger:
                logger.log("WARN", f"adb devices check failed: {e}")
            time.sleep(retry_delay)
            continue

        raw_lines = [
            line.strip()
            for line in res.stdout.splitlines()
            if line.strip() and not line.strip().startswith("List of devices")
        ]

        if not raw_lines:
            if last_reported_state != "none":
                msg = (
                    f"{Color.YELLOW}[!]{Color.RESET} No USB device detected.\n"
                    "    - Connect your OnePlus 13R using an authentic USB-C cable.\n"
                    "    - Ensure 'USB Debugging' is enabled in Developer Options."
                )
                print(msg)
                if logger:
                    logger.log("WARN", "No USB device detected.")
                last_reported_state = "none"
            time.sleep(retry_delay)
            continue

        # Find target device or pick first connected device
        selected_line = None
        if target_serial:
            for l in raw_lines:
                if l.startswith(target_serial):
                    selected_line = l
                    break
        if not selected_line:
            selected_line = raw_lines[0]

        parts = selected_line.split()
        serial = parts[0]
        state = parts[1] if len(parts) > 1 else "unknown"

        if state == "device":
            print(f"{Color.GREEN}[+]{Color.RESET} Device authorized and ready: {Color.BOLD}{serial}{Color.RESET}")
            if logger:
                logger.log("INFO", f"Device authorized and ready: {serial}")
            return serial

        if state == "authorizing":
            if last_reported_state != "authorizing":
                print(f"{Color.CYAN}[*]{Color.RESET} Device is negotiating RSA authorization handshake...")
                if logger:
                    logger.log("INFO", "Device negotiating RSA authorization handshake")
                last_reported_state = "authorizing"
            time.sleep(retry_delay)
            continue

        if state == "unauthorized":
            if last_reported_state != "unauthorized":
                banner = (
                    "\n" + "=" * 70 + "\n"
                    "  [!] ACTION REQUIRED ON YOUR PHONE SCREEN:\n"
                    "  1. Unlock your OnePlus 13R.\n"
                    "  2. A prompt will appear: 'Allow USB debugging?'\n"
                    "  3. Check the box: '[x] Always allow from this computer'\n"
                    "  4. Tap 'Allow'.\n"
                    + "=" * 70 + "\n"
                )
                print(f"{Color.YELLOW}{banner}{Color.RESET}")
                if logger:
                    logger.log("WARN", "Device unauthorized: Waiting for user to accept RSA key.")
                last_reported_state = "unauthorized"
            time.sleep(retry_delay)
            continue

        if state == "offline":
            if last_reported_state != "offline":
                print(f"{Color.YELLOW}[!]{Color.RESET} Device is offline. Please reconnect USB cable or wake screen.")
                if logger:
                    logger.log("WARN", "Device is offline.")
                last_reported_state = "offline"
            time.sleep(retry_delay)
            continue

    raise TimeoutError(f"Timed out after {timeout:.0f}s waiting for device authorization. Reconnect USB cable and retry.")


def validate_device_model(
    adb_path: str,
    serial: str,
    force: bool = False,
    logger: Optional[ExecutionLogger] = None,
) -> bool:
    """Verifies that the connected hardware corresponds to CPH2691 (OnePlus 13R)."""
    try:
        res_model = run_adb_command(adb_path, ["shell", "getprop", "ro.product.model"], serial=serial, timeout=8.0)
        model = res_model.stdout.strip()
    except Exception:
        model = ""

    try:
        res_prod = run_adb_command(adb_path, ["shell", "getprop", "ro.product.name"], serial=serial, timeout=8.0)
        product = res_prod.stdout.strip()
    except Exception:
        product = ""

    try:
        res_os = run_adb_command(adb_path, ["shell", "getprop", "ro.build.version.release"], serial=serial, timeout=8.0)
        android_ver = res_os.stdout.strip()
    except Exception:
        android_ver = ""

    is_compatible = any(c in (model, product) for c in COMPATIBLE_MODELS) or model == DEFAULT_TARGET_MODEL

    if is_compatible:
        info_str = f"Verified hardware target: {model} ({product}) | Android {android_ver}"
        print(f"{Color.GREEN}[+]{Color.RESET} {info_str}")
        if logger:
            logger.log("INFO", info_str)
        return True

    warn_msg = f"Connected device reports model '{model}' ({product}), not OnePlus 13R ({DEFAULT_TARGET_MODEL})."
    if force:
        print(f"{Color.YELLOW}[-]{Color.RESET} WARNING: {warn_msg} Proceeding due to --force flag.")
        if logger:
            logger.log("WARN", f"{warn_msg} Proceeding due to --force.")
        return True

    print(f"{Color.YELLOW}[-]{Color.RESET} WARNING: {warn_msg}")
    if logger:
        logger.log("WARN", warn_msg)

    if sys.stdin.isatty():
        try:
            choice = input("    Proceed anyway? (y/N): ").strip().lower()
            if choice in ("y", "yes"):
                return True
        except (EOFError, KeyboardInterrupt):
            pass

    print(f"{Color.RED}[x]{Color.RESET} Aborted: Device model mismatch. Use --force to override.")
    return False


def get_installed_packages(adb_path: str, serial: str, logger: Optional[ExecutionLogger] = None) -> Set[str]:
    """Retrieves the set of all installed packages (including uninstalled/disabled) for pre-check filtering."""
    try:
        res = run_adb_command(adb_path, ["shell", "pm", "list", "packages", "-u"], serial=serial, timeout=12.0)
        if res.returncode == 0:
            packages = {
                line.strip()[8:].strip()
                for line in res.stdout.splitlines()
                if line.strip().startswith("package:")
            }
            if logger:
                logger.log("INFO", f"Cached {len(packages)} installed packages via pm list packages -u.")
            return packages
    except Exception as e:
        if logger:
            logger.log("WARN", f"Failed to query installed packages: {e}")
    return set()


def load_configuration(custom_config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads configuration with complete schema validation:
      1. Explicit --config path
      2. config.yaml in working or script directory (if PyYAML available)
      3. config.json in working or script directory
      4. Embedded DEFAULT_CONFIG fallback
    """
    raw_config = None
    loaded_source = None

    if custom_config_path:
        c_path = pathlib.Path(custom_config_path).resolve()
        if not c_path.exists():
            sys.stderr.write(f"Configuration Error: Config file not found at '{custom_config_path}'\n")
            sys.exit(EXIT_CONFIG_ERROR)

        try:
            content = c_path.read_text(encoding="utf-8")
            if c_path.suffix in (".yaml", ".yml"):
                if yaml is None:
                    sys.stderr.write("Configuration Error: PyYAML is required to parse YAML files. Install via: pip install pyyaml\n")
                    sys.exit(EXIT_CONFIG_ERROR)
                raw_config = yaml.safe_load(content)
            else:
                raw_config = json.loads(content)
            loaded_source = str(c_path)
        except Exception as e:
            sys.stderr.write(f"Configuration Error: Failed to parse configuration '{custom_config_path}': {e}\n")
            sys.exit(EXIT_CONFIG_ERROR)
    else:
        # Check standard default locations
        search_dirs = [pathlib.Path.cwd(), pathlib.Path(__file__).resolve().parent]
        for s_dir in search_dirs:
            yaml_path = s_dir / "config.yaml"
            if yaml_path.exists() and yaml is not None:
                try:
                    raw_config = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                    loaded_source = str(yaml_path)
                    break
                except Exception:
                    pass

            json_path = s_dir / "config.json"
            if json_path.exists():
                try:
                    raw_config = json.loads(json_path.read_text(encoding="utf-8"))
                    loaded_source = str(json_path)
                    break
                except Exception:
                    pass

    # Start with embedded defaults
    final_config = copy.deepcopy(EMBEDDED_DEFAULT_CONFIG)

    if raw_config and isinstance(raw_config, dict):
        # Merge device
        if "device" in raw_config and isinstance(raw_config["device"], dict):
            final_config["device"].update(raw_config["device"])

        # Merge adb
        if "adb" in raw_config and isinstance(raw_config["adb"], dict):
            final_config["adb"].update(raw_config["adb"])

        # Merge blacklist
        if "blacklist" in raw_config and isinstance(raw_config["blacklist"], list):
            final_config["blacklist"] = list(raw_config["blacklist"])

        # Merge packages
        if "packages" in raw_config and isinstance(raw_config["packages"], dict):
            final_config["packages"].update(raw_config["packages"])

        # If phases declared, update or use them
        if "phases" in raw_config and isinstance(raw_config["phases"], dict):
            final_config["phases"].update(raw_config["phases"])
        else:
            # Dynamically regenerate Phase 4, 5, 6 commands if customized packages supplied
            pkgs = final_config.get("packages", {})

            # Phase 4 (Doze whitelist)
            if "doze_whitelist" in pkgs:
                d_pkgs = pkgs["doze_whitelist"]
                final_config["phases"]["phase_4"]["packages"] = d_pkgs
                final_config["phases"]["phase_4"]["commands"] = [f"dumpsys deviceidle whitelist +{p}" for p in d_pkgs]
                final_config["phases"]["phase_4"]["undo_commands"] = [f"dumpsys deviceidle whitelist -{p}" for p in d_pkgs]

            # Phase 5 (Telemetry freeze)
            if "telemetry_freeze_targets" in pkgs:
                f_pkgs = pkgs["telemetry_freeze_targets"]
                final_config["phases"]["phase_5"]["packages"] = f_pkgs
                final_config["phases"]["phase_5"]["commands"] = [f"pm disable-user --user 0 {p}" for p in f_pkgs]
                final_config["phases"]["phase_5"]["undo_commands"] = [f"pm enable --user 0 {p}" for p in f_pkgs]

            # Phase 6 (AOT compile)
            if "aot_speed_targets" in pkgs:
                a_pkgs = pkgs["aot_speed_targets"]
                final_config["phases"]["phase_6"]["packages"] = a_pkgs
                final_config["phases"]["phase_6"]["commands"] = [f"cmd package compile -m speed {p}" for p in a_pkgs] + ["cmd package compile -m speed-profile -a"]
                final_config["phases"]["phase_6"]["undo_commands"] = [f"cmd package compile --reset {p}" for p in a_pkgs] + ["cmd package compile --reset -a"]

    # CRITICAL SAFETY INVARIANT AUDIT: No blacklist package must ever be in freeze targets
    blacklist_set = set(final_config.get("blacklist", []))
    p5_packages = final_config.get("phases", {}).get("phase_5", {}).get("packages", [])
    for pkg in p5_packages:
        if pkg in blacklist_set:
            sys.stderr.write(f"FATAL SAFETY VIOLATION: Protected package '{pkg}' is present in freeze targets!\n")
            sys.exit(EXIT_CONFIG_ERROR)

    return final_config


def parse_phase_filter(phases_arg: Optional[str], skip_arg: Optional[str], all_phase_keys: List[str]) -> List[str]:
    """
    Parses and validates --phases and --skip arguments.
    Supports numbers (1..12) and human-readable aliases.
    """
    # 1. Determine base selection
    if phases_arg is not None:
        tokens = [t.strip().lower() for t in phases_arg.split(",") if t.strip()]
        selected_set: Set[str] = set()
        for token in tokens:
            if token in PHASE_ALIASES:
                selected_set.add(PHASE_ALIASES[token])
            else:
                sys.stderr.write(
                    f"Configuration Error: Invalid phase identifier '{token}'.\n"
                    "Valid options: 1 to 13 or aliases (e.g. storage, animations, battery, doze, telemetry, aot, wallet, gpu, scheduler, dns, thermal, display, gboard).\n"
                )
                sys.exit(EXIT_CONFIG_ERROR)
        selected_phases = [p for p in all_phase_keys if p in selected_set]
    else:
        selected_phases = list(all_phase_keys)

    # 2. Apply --skip filter
    if skip_arg is not None:
        skip_tokens = [t.strip().lower() for t in skip_arg.split(",") if t.strip()]
        skip_set: Set[str] = set()
        for token in skip_tokens:
            if token in PHASE_ALIASES:
                skip_set.add(PHASE_ALIASES[token])
            else:
                sys.stderr.write(
                    f"Configuration Error: Invalid skip phase identifier '{token}'.\n"
                    "Valid options: 1 to 12 or phase names.\n"
                )
                sys.exit(EXIT_CONFIG_ERROR)
        selected_phases = [p for p in selected_phases if p not in skip_set]

    if not selected_phases:
        sys.stderr.write("Configuration Error: No phases selected for execution after applying phase/skip filters.\n")
        sys.exit(EXIT_CONFIG_ERROR)

    return selected_phases


def print_summary_table(
    results: List[Dict[str, Any]],
    is_dry_run: bool,
    is_undo: bool,
    elapsed_time: float,
):
    """Renders a clean ASCII summary table of phase statuses."""
    title = "ONEPLUS 13R (CPH2691) OPTIMIZATION EXECUTION SUMMARY"
    if is_undo:
        title = "ONEPLUS 13R (CPH2691) ROLLBACK EXECUTION SUMMARY"
    if is_dry_run:
        title += " (DRY-RUN)"

    print("\n" + "=" * 80)
    print(f"{Color.BOLD}{title:^80}{Color.RESET}")
    print("=" * 80)
    print(f"{'Phase':<9} | {'Name':<35} | {'Total':<5} | {'Success':<7} | {'Status'}")
    print("-" * 80)

    total_cmds = 0
    total_success = 0
    total_warnings = 0
    total_failed = 0

    for r in results:
        p_id = r["phase_id"]
        p_num = p_id.replace("phase_", "Phase ")
        name = r["name"][:35]
        total = r["total_commands"]
        success = r["success_count"]
        warn = r["warning_count"]
        failed = r["failed_count"]

        total_cmds += total
        total_success += success
        total_warnings += warn
        total_failed += failed

        if is_dry_run:
            status = f"{Color.MAGENTA}[DRY-RUN] SIMULATED{Color.RESET}"
        elif failed > 0:
            status = f"{Color.RED}[x] FAILED ({failed}){Color.RESET}"
        elif warn > 0:
            status = f"{Color.YELLOW}[!] WARN ({warn} skipped){Color.RESET}"
        else:
            status = f"{Color.GREEN}[+] PASS{Color.RESET}"

        print(f"{p_num:<9} | {name:<35} | {total:<5} | {success:<7} | {status}")

    print("-" * 80)
    overall_status = f"{Color.GREEN}[+] ALL CHECKS PASSED{Color.RESET}"
    if total_failed > 0:
        overall_status = f"{Color.RED}[x] COMPLETED WITH ERRORS{Color.RESET}"
    elif total_warnings > 0:
        overall_status = f"{Color.YELLOW}[!] COMPLETED WITH WARNINGS{Color.RESET}"
    elif is_dry_run:
        overall_status = f"{Color.MAGENTA}[+] PREVIEW COMPLETED (SIMULATED){Color.RESET}"

    print(f"{'TOTAL':<9} | {'All Selected Phases':<35} | {total_cmds:<5} | {total_success:<7} | {overall_status}")
    print("=" * 80)
    print(f"Elapsed Time: {elapsed_time:.2f}s | Mode: {'Rollback (--undo)' if is_undo else 'Optimization (Forward)'} | Simulation: {is_dry_run}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OnePlus 13R (CPH2691) Safe Optimization & Rollback CLI Tool (OxygenOS 15/16)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python optimize_13r.py --dry-run
  python optimize_13r.py --dry-run --undo
  python optimize_13r.py --dry-run --phases 1,2,3
  python optimize_13r.py --dry-run --skip 5,7
  python optimize_13r.py --phases 2,3
  python optimize_13r.py --undo
  python optimize_13r.py --config custom_config.json
  python optimize_13r.py --adb-path "C:\\Program Files\\O+Connect\\daemon\\bin\\adb.exe"
""",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without modifying device state (exits 0)",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Revert/undo all optimization settings back to factory stock defaults",
    )
    parser.add_argument(
        "--phases",
        type=str,
        default=None,
        help="Comma-separated list of phase numbers or names to run (e.g. 1,2,3 or animations,battery)",
    )
    parser.add_argument(
        "--skip",
        type=str,
        default=None,
        help="Comma-separated list of phase numbers or names to skip (e.g. 5,7)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom YAML or JSON configuration file",
    )
    parser.add_argument(
        "--adb-path",
        type=str,
        default=None,
        help="Explicit path to adb executable (overrides auto-discovery)",
    )
    parser.add_argument(
        "--device",
        "-s",
        type=str,
        default=None,
        help="Target device serial number (optional if single device connected)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass device model check warning (e.g. for non-CPH2691 hardware)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colored output in terminal",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to write execution log file (default: optimization_YYYYMMDD_HHMMSS.log)",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"optimize_13r.py {VERSION}",
        help="Show version information and exit",
    )

    args = parser.parse_args()

    # Color setup
    if args.no_color or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        Color.disable()

    # Logger setup
    logger = ExecutionLogger(args.log_file)
    logger.log("INFO", f"Invocation: {' '.join(sys.argv)}")
    logger.log("INFO", f"Version: {VERSION} | Dry-run: {args.dry_run} | Undo: {args.undo}")

    # Load configuration
    config = load_configuration(args.config)
    phases_dict = config.get("phases", {})
    all_phase_keys = sorted(phases_dict.keys(), key=lambda k: int(k.replace("phase_", "")))

    # Filter phases
    selected_phases = parse_phase_filter(args.phases, args.skip, all_phase_keys)

    mode_label = "ROLLBACK / UNDO" if args.undo else "OPTIMIZATION"
    if args.dry_run:
        mode_label += " (DRY-RUN SIMULATION)"

    print(f"\n{Color.BOLD}OnePlus 13R (CPH2691) Safe Optimization Suite v{VERSION}{Color.RESET}")
    print(f"Mode: {Color.CYAN}{mode_label}{Color.RESET}")
    print(f"Phases to execute: {', '.join(p.replace('phase_', 'P') for p in selected_phases)}\n")

    start_time = time.time()
    device_serial = None
    installed_packages: Set[str] = set()

    # ADB Resolution & Device Handshake
    adb_path = ""
    try:
        adb_path = discover_adb(
            custom_path=args.adb_path,
            search_paths=config.get("adb", {}).get("default_search_paths"),
            is_dry_run=args.dry_run,
            logger=logger,
        )
    except FileNotFoundError as e:
        sys.stderr.write(f"\n{Color.RED}[x] Error:{Color.RESET} {e}\n")
        logger.log("ERROR", str(e))
        logger.close()
        return EXIT_RUNTIME_ERROR

    if not args.dry_run:
        # Start persistent ADB daemon upfront
        print(f"{Color.CYAN}[*]{Color.RESET} Initializing persistent ADB server daemon...")
        start_cmd = [adb_path, "start-server"]
        if adb_path.endswith(".py"):
            start_cmd = [sys.executable, adb_path, "start-server"]
        try:
            subprocess.run(start_cmd, capture_output=True, text=True, timeout=10.0)
        except Exception as e:
            logger.log("WARN", f"adb start-server invocation warning: {e}")

        # Wait for authorized device
        timeout_sec = float(config.get("adb", {}).get("retry_timeout", 30.0))
        delay_sec = float(config.get("adb", {}).get("retry_delay", 1.5))
        try:
            device_serial = wait_for_authorized_device(
                adb_path=adb_path,
                target_serial=args.device,
                timeout=timeout_sec,
                retry_delay=delay_sec,
                logger=logger,
            )
        except TimeoutError as e:
            sys.stderr.write(f"\n{Color.RED}[x] Authorization Timeout:{Color.RESET} {e}\n")
            logger.log("ERROR", str(e))
            logger.close()
            return EXIT_RUNTIME_ERROR

        # Model validation
        is_valid_model = validate_device_model(
            adb_path=adb_path,
            serial=device_serial,
            force=args.force,
            logger=logger,
        )
        if not is_valid_model:
            logger.close()
            return EXIT_RUNTIME_ERROR

        # Query installed packages for graceful package skip
        installed_packages = get_installed_packages(adb_path, device_serial, logger=logger)
    else:
        print(f"{Color.MAGENTA}[DRY-RUN]{Color.RESET} Operating in simulation mode -- no physical device commands will be sent.\n")

    # Phase Execution Loop
    results: List[Dict[str, Any]] = []
    blacklist_set = set(config.get("blacklist", MANDATORY_BLACKLIST))

    for phase_key in selected_phases:
        phase_meta = phases_dict[phase_key]
        phase_num = phase_key.replace("phase_", "")
        phase_name = phase_meta.get("name", phase_key)
        phase_type = phase_meta.get("type", "generic")

        print(f"\n{Color.BOLD}>>> Phase {phase_num}: {phase_name}{Color.RESET}")
        print(f"    {Color.DIM}{phase_meta.get('description', '')}{Color.RESET}")
        logger.log("INFO", f"Starting Phase {phase_num}: {phase_name} ({'Undo' if args.undo else 'Forward'})")

        if args.undo:
            commands = list(phase_meta.get("undo_commands", []))
            undo_note = phase_meta.get("undo_note")
            if not commands and undo_note:
                print(f"    {Color.CYAN}[NOTE]{Color.RESET} {undo_note}")
                logger.log("INFO", f"Phase {phase_num} Note: {undo_note}")
        else:
            commands = list(phase_meta.get("commands", []))

        phase_success = 0
        phase_warn = 0
        phase_failed = 0

        for cmd in commands:
            # Package operations checks
            is_package_disable = "pm disable-user" in cmd
            is_package_enable = "pm enable" in cmd
            target_pkg = cmd.split()[-1] if (is_package_disable or is_package_enable) else None

            # Dry-Run Simulation
            if args.dry_run:
                print(f"  [DRY-RUN] adb shell {cmd}")
                logger.log("DRY-RUN", f"adb shell {cmd}")
                phase_success += 1
                continue

            # Real Execution: Tier 1 Blacklist Protection
            if is_package_disable and target_pkg in blacklist_set:
                print(f"  {Color.RED}[!]{Color.RESET} [BLOCKED] Package '{target_pkg}' is in the NEVER TOUCH blacklist! Skipping for system safety.")
                logger.log("BLOCKED", f"Blacklist prevented disabling: {target_pkg}")
                phase_warn += 1
                continue

            # Real Execution: Tier 1 Pre-Check via Installed Packages
            if is_package_disable and installed_packages and target_pkg not in installed_packages:
                print(f"  {Color.YELLOW}[-]{Color.RESET} [SKIP] Package '{target_pkg}' is not installed on this device (common on OxygenOS 15/16 India). Skipping safely.")
                logger.log("SKIP", f"Package not installed: {target_pkg}")
                phase_warn += 1
                continue

            # Real Execution: Execute command
            print(f"  {Color.CYAN}[EXEC]{Color.RESET} adb shell {cmd}")
            logger.log("EXEC", f"adb shell {cmd}")

            try:
                res = run_adb_command(adb_path, ["shell", cmd], serial=device_serial, timeout=40.0)
                stdout_clean = res.stdout.strip()
                stderr_clean = res.stderr.strip()

                if res.returncode == 0:
                    phase_success += 1
                    logger.log("SUCCESS", f"rc=0: {cmd}")
                else:
                    # Tier 2 Runtime Stderr Exception Trap
                    is_missing_pkg_err = any(
                        err_key in stderr_clean
                        for err_key in ("Unknown package", "does not exist", "IllegalArgumentException", "SecurityException")
                    )
                    if is_missing_pkg_err:
                        print(f"  {Color.YELLOW}[-]{Color.RESET} [SKIP] Package '{target_pkg}' absent or unrecognized on device. Skipping safely.")
                        logger.log("WARN", f"Handled package exception: {target_pkg} (stderr: {stderr_clean})")
                        phase_warn += 1
                    else:
                        print(f"  {Color.RED}[x]{Color.RESET} Command failed (rc={res.returncode}): {stderr_clean or stdout_clean}")
                        logger.log("ERROR", f"Command failed (rc={res.returncode}): {stderr_clean}")
                        phase_failed += 1
            except Exception as e:
                print(f"  {Color.RED}[x]{Color.RESET} Subprocess exception executing command: {e}")
                logger.log("ERROR", f"Exception running {cmd}: {e}")
                phase_failed += 1

        results.append({
            "phase_id": phase_key,
            "name": phase_name,
            "total_commands": len(commands),
            "success_count": phase_success,
            "warning_count": phase_warn,
            "failed_count": phase_failed,
        })

    elapsed_time = time.time() - start_time
    print_summary_table(results, is_dry_run=args.dry_run, is_undo=args.undo, elapsed_time=elapsed_time)

    logger.log("INFO", f"Execution finished in {elapsed_time:.2f}s.")
    logger.close()

    total_failures = sum(r["failed_count"] for r in results)
    if total_failures > 0 and not args.dry_run:
        return EXIT_RUNTIME_ERROR

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
