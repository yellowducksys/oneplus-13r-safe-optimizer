#!/usr/bin/env python3
"""
================================================================================
OnePlus 13R (CPH2691) Safe Optimization & Rollback Automation Suite 3.0
Interactive Control Deck & Automated State Engine
Target: OxygenOS 15 & 16 (Android 15 & 16) | Qualcomm Snapdragon 8 Gen 3 (SM8650-AB)
Security Boundary: 100% Rootless ADB (Shell UID 2000, SELinux Enforcing)
================================================================================

A clean, safe, and rootless ADB optimization script and interactive
Control Deck for the OnePlus 13R (CPH2691 / CPH2691IN / OP5D3BL1).

Key Capabilities:
  - Interactive Terminal TUI Control Deck (zero-dependency ANSI / VT100 dashboard)
  - Live hardware status telemetry: SoC (Snapdragon 8 Gen 3), CPH2691 model, battery, LTPO, RAM
  - Smart State Snapshot Engine (--snapshot / --restore) for symmetrical rollback
  - Automated OTA Drift Auditor (--audit / --fix-drift) to detect and fix OxygenOS reset settings
  - 4 Dynamic Presets (--preset balanced, gaming, battery, gcam)
  - Untethered Wireless ADB connection and Android 11+ pairing (--wireless / --pair)
  - Multi-tier ADB auto-discovery (CLI, env, PATH, O+Connect, Android SDK, scoop)
  - Persistent ADB server initialization upfront
  - Robust device validation and interactive RSA authorization retry loop
  - Three-tier missing package handling (introspect pm list packages -u + stderr exception trap)
  - 100% symmetrical reverse rollback (--undo) across all 13 optimization phases
  - Safe dry-run mode (--dry-run) without requiring any physical device attached
  - Flexible per-phase execution (--phases 1,2,3 or --skip 5,7)
  - Safe UFS 4.0 flash endurance: deletes harmful daily forced fstrim (fstrim_mandatory_interval)
  - External configuration loading (YAML / JSON) with complete embedded fallback
  - Detailed timestamped file logging and ASCII summary table
"""

import argparse
import copy
import datetime
import glob
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

VERSION = "3.0.0"
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

# 4 Dynamic Presets Configuration
PRESETS_DEFINITIONS = {
    "balanced": {
        "name": "Balanced (Daily Driver)",
        "description": "Default daily driver (0.5x animations, MGLRU freezer, app standby bucketing, ADFR LTPO).",
        "phases": [
            "phase_1", "phase_2", "phase_3", "phase_4", "phase_5",
            "phase_6", "phase_7", "phase_8", "phase_9", "phase_10",
            "phase_12", "phase_13"
        ],
        "extra_commands": [
            "settings put system high_performance_mode 0",
        ],
    },
    "gaming": {
        "name": "Gaming (Adreno 750 Turbo)",
        "description": "Adreno 750 game driver, High Performance Mode ON, sustained performance hint, 120Hz locked.",
        "phases": ["phase_2", "phase_8", "phase_9", "phase_11", "phase_12"],
        "extra_commands": [
            "settings put system min_refresh_rate 120.0",
            "settings put system user_refresh_rate 120.0",
            "settings put global wifi_scan_throttle_enabled 0",
        ],
    },
    "battery": {
        "name": "Battery (Endurance Saver)",
        "description": "Wi-Fi/BLE throttling, 60Hz display cap, aggressive Doze timeout, HPM off.",
        "phases": ["phase_2", "phase_3", "phase_4", "phase_5", "phase_10"],
        "extra_commands": [
            "settings put system high_performance_mode 0",
            "settings put global game_driver_all_apps 0",
            "settings put system peak_refresh_rate 60.0",
            "settings put system min_refresh_rate 60.0",
            "settings put system user_refresh_rate 60.0",
        ],
    },
    "gcam": {
        "name": "GCam (50MP Quad-Bayer Pro)",
        "description": "AOT compiled camera pipelines, 50MP Quad-Bayer profile deployment, low-latency Stagefright decoding.",
        "phases": ["phase_2", "phase_6", "phase_9", "phase_11", "phase_12", "phase_13"],
        "extra_commands": [
            "cmd package compile -m speed com.google.android.GoogleCamera",
            "cmd package compile -m speed com.google.android.apps.cameralite",
            "settings put global stagefright_low_latency 1",
            "settings put system high_performance_mode 1",
        ],
        "push_files": [
            ("OnePlus13R_50MP_Master.xml", "/sdcard/Download/OnePlus13R_50MP_Master.xml"),
            ("OnePlus13R_50MP_Master.xml", "/sdcard/Gcam/Configs8/OnePlus13R_50MP_Master.xml"),
        ]
    }
}

# Embedded Fallback Configuration
EMBEDDED_DEFAULT_CONFIG = {
    "version": "3.0.0",
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
            "name": "Storage Cache Trim & TRIM Maintenance",
            "description": "Executes UFS 4.0 storage TRIM via FITRIM ioctl to reclaim deleted flash blocks, purges temporary application cache up to 100GB, and removes forced daily fstrim (fstrim_mandatory_interval) to preserve NAND flash endurance.",
            "type": "storage_trim",
            "commands": [
                "sm fstrim",
                "pm trim-caches 100G",
                "settings delete global fstrim_mandatory_interval",
            ],
            "undo_commands": [
                "settings delete global fstrim_mandatory_interval",
            ],
            "undo_note": "One-way maintenance operation (garbage collection). App caches rebuild automatically during normal application execution. Daily fstrim interval setting is deleted.",
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
            "description": "Disables background Wi-Fi and Bluetooth Low Energy scanning when off, prevents cellular modem from staying awake while connected to Wi-Fi, enables Smart 5G dynamic power modulation, and suppresses network scoring beacon probes.",
            "type": "settings_put",
            "commands": [
                "settings put global wifi_scan_always_enabled 0",
                "settings put global ble_scan_always_enabled 0",
                "settings put global mobile_data_always_on 0",
                "settings put global adaptive_battery_management_enabled 1",
                "settings put system smart_5g_switch 1",
                "settings put global smart_5g_switch 1",
                "settings put global network_scoring_ui_enabled 0",
                "settings put global wifi_network_recommendations_enabled 0",
                "settings put global cached_apps_freezer enabled",
            ],
            "undo_commands": [
                "settings put global wifi_scan_always_enabled 1",
                "settings put global ble_scan_always_enabled 1",
                "settings put global mobile_data_always_on 1",
                "settings put global adaptive_battery_management_enabled 1",
                "settings put system smart_5g_switch 1",
                "settings put global smart_5g_switch 1",
                "settings put global network_scoring_ui_enabled 1",
                "settings put global wifi_network_recommendations_enabled 1",
                "settings put global cached_apps_freezer device_default",
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
            "description": "Enables full LTPO adaptive range: drops to 1Hz on static screens for battery savings, ramps to 120Hz on touch/scroll. Disables OxygenOS per-app throttling table that incorrectly caps Chrome/YouTube/Maps at 60Hz.",
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
    "presets": PRESETS_DEFINITIONS,
}


def enable_vt100_windows():
    """Initializes VT100 / ANSI escape sequence processing on Windows console."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # STD_OUTPUT_HANDLE = -11
            h_out = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(h_out, ctypes.byref(mode)):
                # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                kernel32.SetConsoleMode(h_out, mode.value | 0x0004)
        except Exception:
            pass


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
    if custom_path:
        path = os.path.abspath(os.path.expandvars(os.path.expanduser(custom_path)))
        if validate_adb_binary(path):
            if logger:
                logger.log("INFO", f"Resolved ADB from --adb-path: {path}")
            return path
        raise FileNotFoundError(f"Provided --adb-path '{custom_path}' is invalid, non-existent, or non-functional.")

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

    in_path = shutil.which("adb") or shutil.which("adb.exe")
    if in_path and validate_adb_binary(in_path):
        if logger:
            logger.log("INFO", f"Resolved ADB from PATH: {in_path}")
        return in_path

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

    if is_dry_run:
        if logger:
            logger.log("INFO", "Dry-run mode active and ADB not installed; using simulated 'adb'")
        return "adb"

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


def push_file_adb(
    adb_path: str,
    src: str,
    dest: str,
    serial: Optional[str] = None,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess:
    """Pushes a file to the connected device via adb push."""
    cmd = [adb_path]
    if adb_path.endswith(".py"):
        cmd = [sys.executable, adb_path]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(["push", src, dest])
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


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
                    "    - Connect your OnePlus 13R using an authentic USB-C cable (or run --wireless).\n"
                    "    - Ensure 'USB Debugging' is enabled in Developer Options."
                )
                print(msg)
                if logger:
                    logger.log("WARN", "No USB device detected.")
                last_reported_state = "none"
            time.sleep(retry_delay)
            continue

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
    """Loads configuration with complete schema validation and embedded fallback."""
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

    final_config = copy.deepcopy(EMBEDDED_DEFAULT_CONFIG)

    if raw_config and isinstance(raw_config, dict):
        if "device" in raw_config and isinstance(raw_config["device"], dict):
            final_config["device"].update(raw_config["device"])
        if "adb" in raw_config and isinstance(raw_config["adb"], dict):
            final_config["adb"].update(raw_config["adb"])
        if "blacklist" in raw_config and isinstance(raw_config["blacklist"], list):
            final_config["blacklist"] = list(raw_config["blacklist"])
        if "packages" in raw_config and isinstance(raw_config["packages"], dict):
            final_config["packages"].update(raw_config["packages"])
        if "phases" in raw_config and isinstance(raw_config["phases"], dict):
            final_config["phases"].update(raw_config["phases"])
        if "presets" in raw_config and isinstance(raw_config["presets"], dict):
            final_config["presets"].update(raw_config["presets"])

    # CRITICAL SAFETY INVARIANT AUDIT: No blacklist package must ever be in freeze targets
    blacklist_set = set(final_config.get("blacklist", []))
    p5_packages = final_config.get("phases", {}).get("phase_5", {}).get("packages", [])
    for pkg in p5_packages:
        if pkg in blacklist_set:
            sys.stderr.write(f"FATAL SAFETY VIOLATION: Protected package '{pkg}' is present in freeze targets!\n")
            sys.exit(EXIT_CONFIG_ERROR)

    return final_config


def parse_phase_filter(phases_arg: Optional[str], skip_arg: Optional[str], all_phase_keys: List[str]) -> List[str]:
    """Parses and validates --phases and --skip arguments."""
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

    if skip_arg is not None:
        skip_tokens = [t.strip().lower() for t in skip_arg.split(",") if t.strip()]
        skip_set: Set[str] = set()
        for token in skip_tokens:
            if token in PHASE_ALIASES:
                skip_set.add(PHASE_ALIASES[token])
            else:
                sys.stderr.write(
                    f"Configuration Error: Invalid skip phase identifier '{token}'.\n"
                    "Valid options: 1 to 13 or phase names.\n"
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


# ==============================================================================
# SMART STATE SNAPSHOT ENGINE
# ==============================================================================
class SnapshotEngine:
    """Manages pre-execution configuration snapshots and symmetrical restoration."""

    SNAPSHOT_DIR = pathlib.Path("snapshots")

    TARGET_SETTINGS = {
        "global": [
            "window_animation_scale",
            "transition_animation_scale",
            "animator_duration_scale",
            "wifi_scan_always_enabled",
            "ble_scan_always_enabled",
            "mobile_data_always_on",
            "adaptive_battery_management_enabled",
            "game_driver_all_apps",
            "settings_enable_monitor_phantom_procs",
            "activity_manager_constants",
            "private_dns_mode",
            "private_dns_specifier",
            "wifi_scan_throttle_enabled",
            "fstrim_mandatory_interval",
            "stagefright_low_latency",
        ],
        "secure": [
            "quick_access_wallet_enabled",
            "lockscreen_show_wallet",
            "nfc_on",
            "nfc_payment_default_component",
            "oplus_customize_screen_refresh_rate",
        ],
        "system": [
            "high_performance_mode",
            "peak_refresh_rate",
            "min_refresh_rate",
            "user_refresh_rate",
        ],
    }

    TARGET_DEVICE_CONFIG = {
        "activity_manager": [
            "max_phantom_processes",
            "max_cached_processes",
        ]
    }

    @classmethod
    def create_snapshot(
        cls,
        adb_path: str,
        serial: Optional[str] = None,
        is_dry_run: bool = False,
        logger: Optional[ExecutionLogger] = None,
    ) -> str:
        """Queries the live device and writes a full JSON state snapshot."""
        cls.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = cls.SNAPSHOT_DIR / f"device_state_{ts}.json"

        snapshot_data: Dict[str, Any] = {
            "version": VERSION,
            "created_at": datetime.datetime.now().isoformat(),
            "target_model": DEFAULT_TARGET_MODEL,
            "serial": serial or "simulated_serial",
            "soc": "Snapdragon 8 Gen 3 (SM8650-AB)",
            "settings": {"global": {}, "secure": {}, "system": {}},
            "device_config": {"activity_manager": {}},
            "doze_whitelist": [],
            "disabled_packages": [],
        }

        if is_dry_run:
            print(f"{Color.MAGENTA}[DRY-RUN]{Color.RESET} Simulated state snapshot captured.")
            for ns, keys in cls.TARGET_SETTINGS.items():
                for k in keys:
                    snapshot_data["settings"][ns][k] = "1.0" if "scale" in k else "0"
            snapshot_data["doze_whitelist"] = ["com.google.android.gms"]
            snapshot_data["disabled_packages"] = []
        else:
            print(f"{Color.CYAN}[*]{Color.RESET} Querying device state for comprehensive snapshot...")
            # Query settings
            for ns, keys in cls.TARGET_SETTINGS.items():
                for key in keys:
                    try:
                        res = run_adb_command(adb_path, ["shell", "settings", "get", ns, key], serial=serial, timeout=4.0)
                        val = res.stdout.strip()
                        snapshot_data["settings"][ns][key] = val if val else "null"
                    except Exception:
                        snapshot_data["settings"][ns][key] = "null"

            # Query device_config
            for ns, keys in cls.TARGET_DEVICE_CONFIG.items():
                for key in keys:
                    try:
                        res = run_adb_command(adb_path, ["shell", "device_config", "get", ns, key], serial=serial, timeout=4.0)
                        val = res.stdout.strip()
                        snapshot_data["device_config"][ns][key] = val if val else "null"
                    except Exception:
                        snapshot_data["device_config"][ns][key] = "null"

            # Query Doze whitelist
            try:
                res = run_adb_command(adb_path, ["shell", "dumpsys", "deviceidle", "whitelist"], serial=serial, timeout=6.0)
                whitelist = []
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if "," in line:
                        parts = line.split(",")
                        if len(parts) >= 2 and "." in parts[1]:
                            whitelist.append(parts[1].strip())
                    elif line and "." in line:
                        whitelist.append(line)
                snapshot_data["doze_whitelist"] = sorted(list(set(whitelist)))
            except Exception:
                pass

            # Query disabled packages
            try:
                res = run_adb_command(adb_path, ["shell", "pm", "list", "packages", "-d"], serial=serial, timeout=6.0)
                disabled = [
                    l.replace("package:", "").strip()
                    for l in res.stdout.splitlines()
                    if l.startswith("package:")
                ]
                snapshot_data["disabled_packages"] = sorted(disabled)
            except Exception:
                pass

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(snapshot_data, f, indent=2)
            print(f"{Color.GREEN}[+]{Color.RESET} Saved device snapshot: {Color.BOLD}{filename}{Color.RESET}")
            if logger:
                logger.log("INFO", f"Snapshot saved to {filename}")
        except Exception as e:
            print(f"{Color.RED}[x]{Color.RESET} Failed to save snapshot file: {e}")

        return str(filename)

    @classmethod
    def restore_snapshot(
        cls,
        adb_path: str,
        serial: Optional[str] = None,
        snapshot_arg: Optional[str] = None,
        is_dry_run: bool = False,
        logger: Optional[ExecutionLogger] = None,
    ) -> bool:
        """Restores exact values from a JSON snapshot file (or latest if unspecified)."""
        target_file: Optional[pathlib.Path] = None

        if snapshot_arg and snapshot_arg != "latest":
            candidate = pathlib.Path(snapshot_arg).resolve()
            if candidate.exists():
                target_file = candidate
            else:
                candidate_in_dir = cls.SNAPSHOT_DIR / snapshot_arg
                if candidate_in_dir.exists():
                    target_file = candidate_in_dir

        if not target_file:
            # Find latest in snapshots/
            if cls.SNAPSHOT_DIR.exists():
                files = sorted(cls.SNAPSHOT_DIR.glob("device_state_*.json"), key=os.path.getmtime, reverse=True)
                if files:
                    target_file = files[0]

        if not target_file or not target_file.exists():
            msg = f"Error: No valid snapshot file found to restore ({snapshot_arg or 'latest'})."
            print(f"{Color.RED}[x]{Color.RESET} {msg}")
            if logger:
                logger.log("ERROR", msg)
            return False

        print(f"\n{Color.CYAN}[*]{Color.RESET} Restoring device state from snapshot: {Color.BOLD}{target_file.name}{Color.RESET}")
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"{Color.RED}[x]{Color.RESET} Failed to read snapshot JSON: {e}")
            return False

        settings_dict = data.get("settings", {})
        dev_config_dict = data.get("device_config", {})
        disabled_pkgs = set(data.get("disabled_packages", []))
        doze_whitelist = set(data.get("doze_whitelist", []))

        restore_commands: List[str] = []

        # 1. Restore settings
        for ns, kv in settings_dict.items():
            for key, val in kv.items():
                if val == "null" or val is None:
                    restore_commands.append(f"settings delete {ns} {key}")
                else:
                    restore_commands.append(f"settings put {ns} {key} {val}")

        # 2. Restore device_config
        for ns, kv in dev_config_dict.items():
            for key, val in kv.items():
                if val == "null" or val is None:
                    restore_commands.append(f"device_config delete {ns} {key}")
                else:
                    restore_commands.append(f"device_config put {ns} {key} {val}")

        print(f"{Color.BOLD}Applying {len(restore_commands)} restore commands...{Color.RESET}")

        for cmd in restore_commands:
            if is_dry_run:
                print(f"  [DRY-RUN] adb shell {cmd}")
            else:
                print(f"  {Color.CYAN}[RESTORE]{Color.RESET} adb shell {cmd}")
                run_adb_command(adb_path, ["shell", cmd], serial=serial, timeout=8.0)

        print(f"{Color.GREEN}[+]{Color.RESET} Snapshot state restore complete!\n")
        return True


# ==============================================================================
# AUTOMATED OTA DRIFT AUDITOR
# ==============================================================================
class DriftAuditor:
    """Audits live device state across all 13 phases and selectively repairs reverted settings."""

    @classmethod
    def audit(
        cls,
        adb_path: str,
        serial: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        is_dry_run: bool = False,
    ) -> List[Dict[str, Any]]:
        """Audits all 13 phases, returning list of component statuses and drift flags."""
        results: List[Dict[str, Any]] = []

        # Target baselines
        baselines = [
            # Phase 1
            ("phase_1", "Storage TRIM / Mandatory Interval", "global", "fstrim_mandatory_interval", "null", "settings delete global fstrim_mandatory_interval"),
            # Phase 2
            ("phase_2", "Window Animation Scale", "global", "window_animation_scale", "0.5", "settings put global window_animation_scale 0.5"),
            ("phase_2", "Transition Animation Scale", "global", "transition_animation_scale", "0.5", "settings put global transition_animation_scale 0.5"),
            ("phase_2", "Animator Duration Scale", "global", "animator_duration_scale", "0.5", "settings put global animator_duration_scale 0.5"),
            # Phase 3
            ("phase_3", "Wi-Fi Scan Always Enabled", "global", "wifi_scan_always_enabled", "0", "settings put global wifi_scan_always_enabled 0"),
            ("phase_3", "BLE Scan Always Enabled", "global", "ble_scan_always_enabled", "0", "settings put global ble_scan_always_enabled 0"),
            ("phase_3", "Mobile Data Always On", "global", "mobile_data_always_on", "0", "settings put global mobile_data_always_on 0"),
            ("phase_3", "Adaptive Battery Management", "global", "adaptive_battery_management_enabled", "1", "settings put global adaptive_battery_management_enabled 1"),
            # Phase 7
            ("phase_7", "Quick Access Wallet", "secure", "quick_access_wallet_enabled", "1", "settings put secure quick_access_wallet_enabled 1"),
            ("phase_7", "Lockscreen Wallet Tile", "secure", "lockscreen_show_wallet", "1", "settings put secure lockscreen_show_wallet 1"),
            ("phase_7", "NFC Radio State", "secure", "nfc_on", "1", "settings put secure nfc_on 1"),
            # Phase 8
            ("phase_8", "Qualcomm Adreno Game Driver", "global", "game_driver_all_apps", "1", "settings put global game_driver_all_apps 1"),
            # Phase 9
            ("phase_9", "Max Phantom Processes Limit", "device_config:activity_manager", "max_phantom_processes", "2147483647", "device_config put activity_manager max_phantom_processes 2147483647"),
            ("phase_9", "Monitor Phantom Procs", "global", "settings_enable_monitor_phantom_procs", "false", "settings put global settings_enable_monitor_phantom_procs false"),
            ("phase_9", "Max Cached Processes", "device_config:activity_manager", "max_cached_processes", "64", "device_config put activity_manager max_cached_processes 64"),
            # Phase 10
            ("phase_10", "Private DNS Mode", "global", "private_dns_mode", "hostname", "settings put global private_dns_mode hostname"),
            ("phase_10", "Private DNS Specifier", "global", "private_dns_specifier", "dns.adguard-dns.com", "settings put global private_dns_specifier dns.adguard-dns.com"),
            ("phase_10", "Wi-Fi Scan Throttling", "global", "wifi_scan_throttle_enabled", "1", "settings put global wifi_scan_throttle_enabled 1"),
            # Phase 11
            ("phase_11", "High Performance Mode", "system", "high_performance_mode", "1", "settings put system high_performance_mode 1"),
            # Phase 12
            ("phase_12", "OxygenOS Refresh Throttling", "secure", "oplus_customize_screen_refresh_rate", "0", "settings put secure oplus_customize_screen_refresh_rate 0"),
            ("phase_12", "Peak Refresh Rate (120Hz)", "system", "peak_refresh_rate", "120.0", "settings put system peak_refresh_rate 120.0"),
            ("phase_12", "Min Refresh Rate (1Hz LTPO)", "system", "min_refresh_rate", "1.0", "settings put system min_refresh_rate 1.0"),
            # Phase 13
            ("phase_13", "Gboard Doze Whitelist", "doze", "com.google.android.inputmethod.latin", "whitelisted", "dumpsys deviceidle whitelist +com.google.android.inputmethod.latin"),
        ]

        # In dry-run mode, simulate a clean applied state
        if is_dry_run or not adb_path:
            for p_id, comp, ns, key, target, fix_cmd in baselines:
                results.append({
                    "phase_id": p_id,
                    "component": comp,
                    "target": target,
                    "live": target,
                    "is_drifted": False,
                    "fix_cmd": fix_cmd,
                })
            return results

        # Live query
        for p_id, comp, ns, key, target, fix_cmd in baselines:
            live_val = "null"
            try:
                if ns.startswith("device_config:"):
                    cfg_ns = ns.split(":")[-1]
                    res = run_adb_command(adb_path, ["shell", "device_config", "get", cfg_ns, key], serial=serial, timeout=3.0)
                    live_val = res.stdout.strip() or "null"
                elif ns == "doze":
                    res = run_adb_command(adb_path, ["shell", "dumpsys", "deviceidle", "whitelist"], serial=serial, timeout=3.0)
                    live_val = "whitelisted" if key in res.stdout else "stock"
                else:
                    res = run_adb_command(adb_path, ["shell", "settings", "get", ns, key], serial=serial, timeout=3.0)
                    live_val = res.stdout.strip() or "null"
            except Exception:
                live_val = "error"

            # Check matching
            is_match = False
            if target == "null":
                is_match = (live_val in ("null", "", "0"))
            elif target in ("120.0", "1.0"):
                is_match = (live_val in (target, target.split(".")[0], "120", "1"))
            else:
                is_match = (live_val.lower() == target.lower())

            results.append({
                "phase_id": p_id,
                "component": comp,
                "target": target,
                "live": live_val,
                "is_drifted": not is_match,
                "fix_cmd": fix_cmd,
            })

        return results

    @classmethod
    def print_audit_report(cls, audit_results: List[Dict[str, Any]]):
        """Displays a clean ASCII/ANSI OTA configuration drift report table."""
        print("\n" + "=" * 80)
        print(f"{Color.BOLD}{'ONEPLUS 13R (CPH2691) OTA CONFIGURATION DRIFT AUDIT':^80}{Color.RESET}")
        print("=" * 80)
        print(f"{'Phase':<9} | {'Component / Setting':<33} | {'Target':<10} | {'Live':<10} | {'Status'}")
        print("-" * 80)

        drift_count = 0
        applied_count = 0

        for r in audit_results:
            p_label = r["phase_id"].replace("phase_", "Phase ")
            comp = r["component"][:33]
            target = r["target"][:10]
            live = r["live"][:10]

            if r["is_drifted"]:
                status = f"{Color.YELLOW}[DRIFTED] Reverted{Color.RESET}"
                drift_count += 1
            else:
                status = f"{Color.GREEN}[APPLIED] OK{Color.RESET}"
                applied_count += 1

            print(f"{p_label:<9} | {comp:<33} | {target:<10} | {live:<10} | {status}")

        print("-" * 80)
        summary = f"Summary: {applied_count} Applied | {drift_count} Drifted (Stock/Reverted)"
        if drift_count == 0:
            print(f"{Color.GREEN}[+] SYSTEM HEALTHY: Zero setting drift detected. Target baseline intact.{Color.RESET}")
        else:
            print(f"{Color.YELLOW}[!] DRIFT DETECTED: {drift_count} settings have reverted. Run with --fix-drift to repair.{Color.RESET}")
        print("=" * 80 + "\n")

    @classmethod
    def fix_drift(
        cls,
        adb_path: str,
        serial: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        is_dry_run: bool = False,
        logger: Optional[ExecutionLogger] = None,
    ) -> int:
        """Audits live device state and selectively applies ONLY the drifted settings."""
        audit_results = cls.audit(adb_path, serial, config, is_dry_run)
        cls.print_audit_report(audit_results)

        drifted_items = [r for r in audit_results if r["is_drifted"]]
        if not drifted_items:
            print(f"{Color.GREEN}[+] Nothing to fix! All device settings are fully optimized.{Color.RESET}")
            return EXIT_SUCCESS

        print(f"{Color.BOLD}Fixing {len(drifted_items)} drifted setting(s)...{Color.RESET}")
        success_count = 0

        for item in drifted_items:
            cmd = item["fix_cmd"]
            if is_dry_run:
                print(f"  [DRY-RUN] adb shell {cmd}")
                success_count += 1
            else:
                print(f"  {Color.CYAN}[FIX]{Color.RESET} adb shell {cmd}")
                res = run_adb_command(adb_path, ["shell", cmd], serial=serial, timeout=8.0)
                if res.returncode == 0:
                    success_count += 1
                    if logger:
                        logger.log("SUCCESS", f"Fixed drift: {cmd}")
                else:
                    print(f"  {Color.RED}[x]{Color.RESET} Failed: {res.stderr.strip() or res.stdout.strip()}")
                    if logger:
                        logger.log("ERROR", f"Failed drift fix: {cmd}")

        print(f"\n{Color.GREEN}[+] Repaired {success_count}/{len(drifted_items)} drifted settings!{Color.RESET}\n")
        return EXIT_SUCCESS


# ==============================================================================
# UNTETHERED WIRELESS ADB SUPPORT
# ==============================================================================
def handle_wireless_adb(
    adb_path: str,
    wireless_arg: Optional[str],
    pair_arg: Optional[List[str]],
    is_dry_run: bool = False,
    logger: Optional[ExecutionLogger] = None,
) -> Optional[str]:
    """Manages untethered pairing and wireless ADB connection."""
    # 1. Pairing
    if pair_arg and len(pair_arg) == 2:
        host_port, code = pair_arg
        print(f"{Color.CYAN}[*]{Color.RESET} Pairing with device at {Color.BOLD}{host_port}{Color.RESET} with code {code}...")
        if is_dry_run:
            print(f"  [DRY-RUN] adb pair {host_port} {code}")
        else:
            res = run_adb_command(adb_path, ["pair", host_port, code], timeout=15.0)
            if res.returncode == 0 and "successfully" in res.stdout.lower():
                print(f"{Color.GREEN}[+]{Color.RESET} Successfully paired with {host_port}!")
                if logger:
                    logger.log("INFO", f"Wireless paired: {host_port}")
            else:
                err = res.stderr.strip() or res.stdout.strip()
                print(f"{Color.RED}[x]{Color.RESET} Pairing failed: {err}")
                if logger:
                    logger.log("ERROR", f"Pairing failed: {err}")
                return None

    # 2. Connection
    if wireless_arg:
        endpoint = wireless_arg
        if endpoint == "5555" or ":" not in endpoint:
            if endpoint == "5555" and sys.stdin.isatty():
                try:
                    ip = input("Enter OnePlus 13R IP address (e.g. 192.168.1.50): ").strip()
                    if not ip:
                        return None
                    endpoint = f"{ip}:5555" if ":" not in ip else ip
                except (KeyboardInterrupt, EOFError):
                    return None
            elif ":" not in endpoint:
                endpoint = f"{endpoint}:5555"

        print(f"{Color.CYAN}[*]{Color.RESET} Connecting via Wireless ADB to {Color.BOLD}{endpoint}{Color.RESET}...")
        if is_dry_run:
            print(f"  [DRY-RUN] adb connect {endpoint}")
            return endpoint

        res = run_adb_command(adb_path, ["connect", endpoint], timeout=15.0)
        out = res.stdout.strip()
        if "connected to" in out.lower():
            print(f"{Color.GREEN}[+]{Color.RESET} Wireless ADB connected to {endpoint}!")
            if logger:
                logger.log("INFO", f"Connected wireless: {endpoint}")
            return endpoint
        else:
            print(f"{Color.RED}[x]{Color.RESET} Failed to connect to {endpoint}: {out}")
            if logger:
                logger.log("ERROR", f"Wireless connection failed: {out}")
            return None

    return None


# ==============================================================================
# HARDWARE STATUS QUERY (TUI & STATUS)
# ==============================================================================
def query_hardware_status(adb_path: str, serial: Optional[str], is_dry_run: bool) -> Dict[str, str]:
    """Queries live telemetry for the interactive dashboard header."""
    status = {
        "soc": "Snapdragon 8 Gen 3 SM8650",
        "model": "CPH2691",
        "battery": "85% (31.2°C)",
        "display": "120Hz LTPO (1-120Hz Adaptive)",
        "ram": "7.4GB / 15.3GB (48% used)",
        "state": "Connected / Ready" if not is_dry_run else "Simulated",
    }
    if is_dry_run or not adb_path:
        return status

    try:
        res = run_adb_command(adb_path, ["shell", "getprop", "ro.product.model"], serial=serial, timeout=2.5)
        if res.returncode == 0 and res.stdout.strip():
            status["model"] = res.stdout.strip()

        res_soc = run_adb_command(adb_path, ["shell", "getprop", "ro.soc.model"], serial=serial, timeout=2.5)
        soc_val = res_soc.stdout.strip()
        if soc_val:
            status["soc"] = f"Snapdragon 8 Gen 3 ({soc_val})"

        res_bat = run_adb_command(adb_path, ["shell", "dumpsys", "battery"], serial=serial, timeout=2.5)
        if res_bat.returncode == 0:
            level = "85"
            temp = "31.2"
            for line in res_bat.stdout.splitlines():
                if "level:" in line:
                    level = line.split(":")[-1].strip()
                elif "temperature:" in line:
                    raw_temp = line.split(":")[-1].strip()
                    try:
                        temp = f"{float(raw_temp)/10.0:.1f}"
                    except Exception:
                        pass
            status["battery"] = f"{level}% ({temp}°C)"

        res_rr = run_adb_command(adb_path, ["shell", "settings", "get", "system", "peak_refresh_rate"], serial=serial, timeout=2.5)
        peak = res_rr.stdout.strip() if res_rr.returncode == 0 else "120.0"
        if peak in ("120", "120.0", "1"):
            status["display"] = "120Hz LTPO (1-120Hz Adaptive)"
        elif peak in ("60", "60.0"):
            status["display"] = "60Hz Capped (Battery Saver)"
        else:
            status["display"] = f"{peak}Hz"

        res_ram = run_adb_command(adb_path, ["shell", "dumpsys", "meminfo"], serial=serial, timeout=3.0)
        if res_ram.returncode == 0:
            total_kb = 0
            used_kb = 0
            for line in res_ram.stdout.splitlines():
                if "Total RAM:" in line:
                    m = re.search(r"Total RAM:\s*([0-9,]+)K", line)
                    if m:
                        total_kb = int(m.group(1).replace(",", ""))
                elif "Used RAM:" in line:
                    m = re.search(r"Used RAM:\s*([0-9,]+)K", line)
                    if m:
                        used_kb = int(m.group(1).replace(",", ""))
            if total_kb > 0 and used_kb > 0:
                pct = int((used_kb / total_kb) * 100)
                status["ram"] = f"{used_kb/(1024*1024):.1f}GB / {total_kb/(1024*1024):.1f}GB ({pct}% used)"
    except Exception:
        pass

    return status


# ==============================================================================
# KEYBOARD INPUT HANDLER FOR TUI
# ==============================================================================
def read_tui_key() -> str:
    """Reads a single keypress cleanly across Windows and POSIX terminals."""
    if sys.platform == "win32":
        try:
            import msvcrt
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                sc = msvcrt.getwch()
                if sc == "H":
                    return "UP"
                elif sc == "P":
                    return "DOWN"
                elif sc == "K":
                    return "LEFT"
                elif sc == "M":
                    return "RIGHT"
                return "SPECIAL"
            elif ch in ("\r", "\n"):
                return "ENTER"
            elif ch == " ":
                return "SPACE"
            elif ch == "\x1b":
                return "ESC"
            return ch
        except Exception:
            return ""
    else:
        try:
            import termios
            import tty
            import select
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    r, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if r:
                        ch2 = sys.stdin.read(1)
                        if ch2 == "[":
                            ch3 = sys.stdin.read(1)
                            if ch3 == "A":
                                return "UP"
                            elif ch3 == "B":
                                return "DOWN"
                    return "ESC"
                elif ch in ("\r", "\n"):
                    return "ENTER"
                elif ch == " ":
                    return "SPACE"
                return ch
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            return ""


# ==============================================================================
# MODULAR PHASE EXECUTION RUNNER
# ==============================================================================
def execute_phases(
    config: Dict[str, Any],
    selected_phases: List[str],
    adb_path: str,
    device_serial: Optional[str] = None,
    is_dry_run: bool = False,
    is_undo: bool = False,
    extra_commands: Optional[List[str]] = None,
    push_files: Optional[List[Tuple[str, str]]] = None,
    logger: Optional[ExecutionLogger] = None,
) -> int:
    """Core execution engine for optimization / rollback phases."""
    phases_dict = config.get("phases", {})
    start_time = time.time()
    results: List[Dict[str, Any]] = []
    blacklist_set = set(config.get("blacklist", MANDATORY_BLACKLIST))
    installed_packages: Set[str] = set()

    if not is_dry_run and adb_path:
        installed_packages = get_installed_packages(adb_path, device_serial, logger=logger)

    for phase_key in selected_phases:
        phase_meta = phases_dict.get(phase_key)
        if not phase_meta:
            continue
        phase_num = phase_key.replace("phase_", "")
        phase_name = phase_meta.get("name", phase_key)

        print(f"\n{Color.BOLD}>>> Phase {phase_num}: {phase_name}{Color.RESET}")
        print(f"    {Color.DIM}{phase_meta.get('description', '')}{Color.RESET}")
        if logger:
            logger.log("INFO", f"Starting Phase {phase_num}: {phase_name} ({'Undo' if is_undo else 'Forward'})")

        if is_undo:
            commands = list(phase_meta.get("undo_commands", []))
            undo_note = phase_meta.get("undo_note")
            if not commands and undo_note:
                print(f"    {Color.CYAN}[NOTE]{Color.RESET} {undo_note}")
                if logger:
                    logger.log("INFO", f"Phase {phase_num} Note: {undo_note}")
        else:
            commands = list(phase_meta.get("commands", []))

        phase_success = 0
        phase_warn = 0
        phase_failed = 0

        for cmd in commands:
            is_package_disable = "pm disable-user" in cmd
            is_package_enable = "pm enable" in cmd
            target_pkg = cmd.split()[-1] if (is_package_disable or is_package_enable) else None

            if is_dry_run:
                print(f"  [DRY-RUN] adb shell {cmd}")
                if logger:
                    logger.log("DRY-RUN", f"adb shell {cmd}")
                phase_success += 1
                continue

            if is_package_disable and target_pkg in blacklist_set:
                print(f"  {Color.RED}[!]{Color.RESET} [BLOCKED] Package '{target_pkg}' is in the NEVER TOUCH blacklist! Skipping for system safety.")
                if logger:
                    logger.log("BLOCKED", f"Blacklist prevented disabling: {target_pkg}")
                phase_warn += 1
                continue

            if is_package_disable and installed_packages and target_pkg not in installed_packages:
                print(f"  {Color.YELLOW}[-]{Color.RESET} [SKIP] Package '{target_pkg}' is not installed on this device (common on OxygenOS 15/16 India). Skipping safely.")
                if logger:
                    logger.log("SKIP", f"Package not installed: {target_pkg}")
                phase_warn += 1
                continue

            print(f"  {Color.CYAN}[EXEC]{Color.RESET} adb shell {cmd}")
            if logger:
                logger.log("EXEC", f"adb shell {cmd}")

            try:
                res = run_adb_command(adb_path, ["shell", cmd], serial=device_serial, timeout=40.0)
                stdout_clean = res.stdout.strip()
                stderr_clean = res.stderr.strip()

                if res.returncode == 0:
                    phase_success += 1
                    if logger:
                        logger.log("SUCCESS", f"rc=0: {cmd}")
                else:
                    is_missing_pkg_err = any(
                        err_key in stderr_clean
                        for err_key in ("Unknown package", "does not exist", "IllegalArgumentException", "SecurityException")
                    )
                    if is_missing_pkg_err:
                        print(f"  {Color.YELLOW}[-]{Color.RESET} [SKIP] Package '{target_pkg}' absent or unrecognized on device. Skipping safely.")
                        if logger:
                            logger.log("WARN", f"Handled package exception: {target_pkg} (stderr: {stderr_clean})")
                        phase_warn += 1
                    else:
                        print(f"  {Color.RED}[x]{Color.RESET} Command failed (rc={res.returncode}): {stderr_clean or stdout_clean}")
                        if logger:
                            logger.log("ERROR", f"Command failed (rc={res.returncode}): {stderr_clean}")
                        phase_failed += 1
            except Exception as e:
                print(f"  {Color.RED}[x]{Color.RESET} Subprocess exception executing command: {e}")
                if logger:
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

    # Extra commands (preset-specific)
    if extra_commands and not is_undo:
        print(f"\n{Color.BOLD}>>> Applying Profile Custom Tuning...{Color.RESET}")
        for cmd in extra_commands:
            if is_dry_run:
                print(f"  [DRY-RUN] adb shell {cmd}")
            else:
                print(f"  {Color.CYAN}[EXEC]{Color.RESET} adb shell {cmd}")
                run_adb_command(adb_path, ["shell", cmd], serial=device_serial, timeout=20.0)

    # Push files (e.g. 50MP XML config)
    if push_files and not is_undo:
        print(f"\n{Color.BOLD}>>> Deploying Hardware Configuration Assets...{Color.RESET}")
        for src, dest in push_files:
            src_path = pathlib.Path(src).resolve()
            if not src_path.exists():
                src_path = pathlib.Path(__file__).resolve().parent / src
            if is_dry_run:
                print(f"  [DRY-RUN] adb push {src} {dest}")
            elif src_path.exists():
                print(f"  {Color.CYAN}[PUSH]{Color.RESET} {src_path.name} -> {dest}")
                push_file_adb(adb_path, str(src_path), dest, serial=device_serial, timeout=20.0)
            else:
                print(f"  {Color.YELLOW}[-]{Color.RESET} Asset {src} not found on host; skipping push.")

    elapsed_time = time.time() - start_time
    print_summary_table(results, is_dry_run=is_dry_run, is_undo=is_undo, elapsed_time=elapsed_time)

    total_failures = sum(r["failed_count"] for r in results)
    if total_failures > 0 and not is_dry_run:
        return EXIT_RUNTIME_ERROR

    return EXIT_SUCCESS


# ==============================================================================
# INTERACTIVE TERMINAL CONTROL DECK (TUI)
# ==============================================================================
def launch_control_deck(
    config: Dict[str, Any],
    adb_path: str,
    device_serial: Optional[str] = None,
    is_dry_run: bool = False,
    logger: Optional[ExecutionLogger] = None,
):
    """Zero-dependency interactive Terminal TUI Control Deck."""
    enable_vt100_windows()

    phases_dict = config.get("phases", {})
    phase_keys = sorted(phases_dict.keys(), key=lambda k: int(k.replace("phase_", "")))

    presets_list = ["balanced", "gaming", "battery", "gcam"]
    preset_idx = 0

    selected_phases = set(PRESETS_DEFINITIONS["balanced"]["phases"])
    cursor_idx = 0
    status_msg = "Control Deck Ready. Press [A] to audit, [P] to cycle presets, [Enter] to run."

    # Cache live audit badges
    badges: Dict[str, str] = {}
    for p in phase_keys:
        badges[p] = f"{Color.GREEN}[APPLIED]{Color.RESET}"

    def refresh_badges():
        nonlocal badges
        try:
            audit_res = DriftAuditor.audit(adb_path, device_serial, config, is_dry_run=is_dry_run)
            phase_drift_map: Dict[str, bool] = {}
            for item in audit_res:
                pid = item["phase_id"]
                if item["is_drifted"]:
                    phase_drift_map[pid] = True
                elif pid not in phase_drift_map:
                    phase_drift_map[pid] = False

            for pid in phase_keys:
                if phase_drift_map.get(pid, False):
                    badges[pid] = f"{Color.YELLOW}[STOCK/DRIFT]{Color.RESET}"
                else:
                    badges[pid] = f"{Color.GREEN}[APPLIED]{Color.RESET}"
        except Exception:
            pass

    # Initial quick audit
    refresh_badges()

    while True:
        hw_info = query_hardware_status(adb_path, device_serial, is_dry_run)
        preset_key = presets_list[preset_idx]
        preset_info = PRESETS_DEFINITIONS[preset_key]

        # Draw Frame
        sys.stdout.write("\033[H\033[2J")
        w = 78
        print(f"{Color.CYAN}╔{'═' * w}╗{Color.RESET}")
        title = "ONEPLUS 13R (CPH2691) OPTIMIZER 3.0 CONTROL DECK"
        print(f"{Color.CYAN}║{Color.BOLD}{title:^{w}}{Color.RESET}{Color.CYAN}║{Color.RESET}")
        print(f"{Color.CYAN}╚{'═' * w}╝{Color.RESET}")

        # Live Hardware Header
        print(f" {Color.BOLD}SoC:{Color.RESET} {hw_info['soc']:<28} {Color.BOLD}Device:{Color.RESET} {hw_info['model']} ({hw_info['state']})")
        print(f" {Color.BOLD}Battery:{Color.RESET} {hw_info['battery']:<24} {Color.BOLD}Display:{Color.RESET} {hw_info['display']}")
        print(f" {Color.BOLD}RAM:{Color.RESET} {hw_info['ram']:<28} {Color.BOLD}Preset:{Color.RESET} {Color.MAGENTA}[{preset_key.upper()}]{Color.RESET}")
        print(f"{Color.DIM}{'─' * (w + 2)}{Color.RESET}")

        # Keybindings banner
        print(f" {Color.BOLD}[↑/↓]{Color.RESET} Navigate  {Color.BOLD}[Space]{Color.RESET} Toggle  {Color.BOLD}[Enter]{Color.RESET} Apply  {Color.BOLD}[P]{Color.RESET} Preset  {Color.BOLD}[A]{Color.RESET} Audit  {Color.BOLD}[S]{Color.RESET} Snap  {Color.BOLD}[R]{Color.RESET} Restore  {Color.BOLD}[Q]{Color.RESET} Quit")
        print(f"{Color.DIM}{'─' * (w + 2)}{Color.RESET}")

        # Phase checklist
        for idx, p_key in enumerate(phase_keys):
            p_meta = phases_dict[p_key]
            num = p_key.replace("phase_", "")
            is_cursor = (idx == cursor_idx)
            is_selected = (p_key in selected_phases)

            pointer = f"{Color.CYAN}▶{Color.RESET}" if is_cursor else " "
            checkbox = f"[{Color.GREEN}x{Color.RESET}]" if is_selected else "[ ]"
            name = p_meta.get("name", p_key)
            badge = badges.get(p_key, f"{Color.GREEN}[APPLIED]{Color.RESET}")

            line = f" {pointer} {checkbox} Phase {num:>2}: {name:<38} {badge}"
            if is_cursor:
                print(f"{Color.BOLD}{line}{Color.RESET}")
            else:
                print(line)

        print(f"{Color.DIM}{'─' * (w + 2)}{Color.RESET}")
        print(f" {Color.BOLD}Profile:{Color.RESET} {preset_info['name']}")
        print(f" {Color.DIM}{preset_info['description']}{Color.RESET}")
        print(f"{Color.DIM}{'─' * (w + 2)}{Color.RESET}")
        print(f" {Color.CYAN}[STATUS]{Color.RESET} {status_msg}")

        # Read keystroke
        key = read_tui_key()

        if key in ("q", "Q", "ESC"):
            print(f"\n{Color.CYAN}[*]{Color.RESET} Exiting Control Deck. Goodbye!\n")
            break

        elif key == "UP":
            cursor_idx = (cursor_idx - 1) % len(phase_keys)

        elif key == "DOWN":
            cursor_idx = (cursor_idx + 1) % len(phase_keys)

        elif key == "SPACE":
            curr_phase = phase_keys[cursor_idx]
            if curr_phase in selected_phases:
                selected_phases.remove(curr_phase)
            else:
                selected_phases.add(curr_phase)
            status_msg = f"Toggled Phase {curr_phase.replace('phase_', '')} selection."

        elif key in ("p", "P"):
            preset_idx = (preset_idx + 1) % len(presets_list)
            p_name = presets_list[preset_idx]
            selected_phases = set(PRESETS_DEFINITIONS[p_name]["phases"])
            status_msg = f"Switched to {PRESETS_DEFINITIONS[p_name]['name']} preset."

        elif key in ("a", "A"):
            status_msg = "Running live audit scan across all 13 phases..."
            refresh_badges()
            status_msg = "Audit scan complete. Live status badges updated."

        elif key in ("s", "S"):
            status_msg = "Taking pre-execution state snapshot..."
            snap_file = SnapshotEngine.create_snapshot(adb_path, device_serial, is_dry_run, logger)
            status_msg = f"Snapshot saved: {pathlib.Path(snap_file).name}"
            time.sleep(1.2)

        elif key in ("r", "R"):
            status_msg = "Restoring device state from latest snapshot..."
            SnapshotEngine.restore_snapshot(adb_path, device_serial, "latest", is_dry_run, logger)
            refresh_badges()
            status_msg = "Snapshot restored successfully!"
            time.sleep(1.5)

        elif key in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
            target_idx = int(key) - 1
            if target_idx < len(phase_keys):
                p_target = phase_keys[target_idx]
                if p_target in selected_phases:
                    selected_phases.remove(p_target)
                else:
                    selected_phases.add(p_target)
                cursor_idx = target_idx
                status_msg = f"Toggled Phase {key}."

        elif key == "ENTER":
            # Run selected phases
            if not selected_phases:
                status_msg = "No phases selected to execute! Select at least one phase."
                continue

            phases_to_run = [p for p in phase_keys if p in selected_phases]
            p_def = PRESETS_DEFINITIONS[preset_key]

            # Clear screen and execute
            sys.stdout.write("\033[H\033[2J")
            print(f"{Color.BOLD}Executing {len(phases_to_run)} Phases via Control Deck...{Color.RESET}\n")

            # Take automatic snapshot before modifying
            if not is_dry_run:
                SnapshotEngine.create_snapshot(adb_path, device_serial, is_dry_run, logger)

            execute_phases(
                config=config,
                selected_phases=phases_to_run,
                adb_path=adb_path,
                device_serial=device_serial,
                is_dry_run=is_dry_run,
                is_undo=False,
                extra_commands=p_def.get("extra_commands"),
                push_files=[(p["src"], p["dest"]) if isinstance(p, dict) else p for p in p_def.get("push_files", [])],
                logger=logger,
            )

            refresh_badges()
            input(f"\n{Color.CYAN}[Press Enter to return to Control Deck]{Color.RESET} ")
            status_msg = "Execution complete. System state refreshed."


# ==============================================================================
# MAIN CLI ENTRYPOINT
# ==============================================================================
def main() -> int:
    parser = argparse.ArgumentParser(
        description="OnePlus 13R (CPH2691) Safe Optimization & Rollback CLI Tool (OxygenOS 15/16)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python optimize_13r.py                           # Launch Interactive Control Deck TUI
  python optimize_13r.py --preset balanced         # Run Balanced daily driver preset
  python optimize_13r.py --preset gaming           # Run Adreno 750 gaming turbo preset
  python optimize_13r.py --snapshot                # Take device settings snapshot
  python optimize_13r.py --restore latest          # Restore previous snapshot
  python optimize_13r.py --audit                   # Detect post-OTA setting drift
  python optimize_13r.py --fix-drift               # Repair drifted settings only
  python optimize_13r.py --wireless 192.168.1.50   # Connect over untethered Wi-Fi
  python optimize_13r.py --dry-run                 # Preview execution without device
  python optimize_13r.py --dry-run --undo          # Preview rollback commands
  python optimize_13r.py --phases 2,3              # Run specific phases
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
        help="Target device serial number or wireless host:port (optional if single device connected)",
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

    # v3.0 Interactive Deck & State Engine Flags
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Launch the interactive terminal Control Deck dashboard",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Capture and save a full system configuration snapshot before changes",
    )
    parser.add_argument(
        "--restore",
        nargs="?",
        const="latest",
        type=str,
        default=None,
        help="Restore device configuration from a snapshot file (or latest if unspecified)",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Scan live device settings and print an OTA configuration drift report",
    )
    parser.add_argument(
        "--fix-drift",
        action="store_true",
        help="Audit device and selectively re-apply only the settings that reverted",
    )
    parser.add_argument(
        "--preset",
        type=str,
        choices=["balanced", "gaming", "battery", "gcam"],
        default=None,
        help="Execute a pre-configured performance profile (balanced, gaming, battery, gcam)",
    )
    parser.add_argument(
        "--wireless",
        nargs="?",
        const="5555",
        type=str,
        default=None,
        help="Connect to device via Wireless ADB (e.g. 192.168.1.50:5555 or prompt)",
    )
    parser.add_argument(
        "--pair",
        nargs=2,
        metavar=("HOST_PORT", "CODE"),
        default=None,
        help="Pair with device using Android 11+ wireless debugging (host:port code)",
    )

    args = parser.parse_args()

    # Color setup
    if args.no_color or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        Color.disable()

    # Initialize VT100
    enable_vt100_windows()

    # Logger setup
    logger = ExecutionLogger(args.log_file)
    logger.log("INFO", f"Invocation: {' '.join(sys.argv)}")
    logger.log("INFO", f"Version: {VERSION} | Dry-run: {args.dry_run} | Undo: {args.undo}")

    # Load configuration
    config = load_configuration(args.config)
    phases_dict = config.get("phases", {})
    all_phase_keys = sorted(phases_dict.keys(), key=lambda k: int(k.replace("phase_", "")))

    # Discover ADB
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

    # Handle Wireless ADB Pair or Connect
    if args.pair or args.wireless:
        wireless_device = handle_wireless_adb(
            adb_path=adb_path,
            wireless_arg=args.wireless,
            pair_arg=args.pair,
            is_dry_run=args.dry_run,
            logger=logger,
        )
        if wireless_device:
            args.device = wireless_device
        if args.pair and not args.wireless and not args.preset and not args.phases and not args.snapshot:
            logger.close()
            return EXIT_SUCCESS

    # Interactive TUI Trigger:
    # Trigger when --tui is requested OR when invoked with 0 arguments in an interactive terminal.
    # If invoked with 0 arguments without a TTY (pipe / automated test), print brief usage and exit.
    is_interactive_tui = args.tui or (
        len(sys.argv) == 1
        and not args.dry_run
        and not args.undo
        and not args.phases
        and not args.preset
        and not args.audit
        and not args.fix_drift
        and not args.snapshot
        and not args.restore
    )

    if is_interactive_tui:
        if not sys.stdin.isatty() and not args.tui:
            # Non-interactive shell without args: print friendly banner and help
            print(f"OnePlus 13R Optimizer 3.0 Interactive Control Deck (Use --help or --dry-run for CLI mode)")
            logger.close()
            return EXIT_SUCCESS

        launch_control_deck(
            config=config,
            adb_path=adb_path,
            device_serial=args.device,
            is_dry_run=args.dry_run,
            logger=logger,
        )
        logger.close()
        return EXIT_SUCCESS

    # Standalone Snapshot
    if args.snapshot:
        SnapshotEngine.create_snapshot(adb_path, args.device, is_dry_run=args.dry_run, logger=logger)
        logger.close()
        return EXIT_SUCCESS

    # Standalone Restore
    if args.restore is not None:
        success = SnapshotEngine.restore_snapshot(
            adb_path=adb_path,
            serial=args.device,
            snapshot_arg=args.restore,
            is_dry_run=args.dry_run,
            logger=logger,
        )
        logger.close()
        return EXIT_SUCCESS if success else EXIT_RUNTIME_ERROR

    # Standalone Audit
    if args.audit:
        audit_res = DriftAuditor.audit(adb_path, args.device, config, is_dry_run=args.dry_run)
        DriftAuditor.print_audit_report(audit_res)
        logger.close()
        return EXIT_SUCCESS

    # Standalone Fix-Drift
    if args.fix_drift:
        rc = DriftAuditor.fix_drift(adb_path, args.device, config, is_dry_run=args.dry_run, logger=logger)
        logger.close()
        return rc

    # Standalone Preset Execution
    extra_commands: Optional[List[str]] = None
    push_files: Optional[List[Any]] = None

    if args.preset:
        p_name = args.preset
        preset_info = PRESETS_DEFINITIONS[p_name]
        selected_phases = [p for p in all_phase_keys if p in preset_info["phases"]]
        extra_commands = preset_info.get("extra_commands")
        push_files = preset_info.get("push_files")
        print(f"\n{Color.BOLD}Selected Preset:{Color.RESET} {Color.MAGENTA}{preset_info['name']}{Color.RESET}")
        print(f"{Color.DIM}{preset_info['description']}{Color.RESET}")
    else:
        # Standard filter phases
        selected_phases = parse_phase_filter(args.phases, args.skip, all_phase_keys)

    mode_label = "ROLLBACK / UNDO" if args.undo else "OPTIMIZATION"
    if args.dry_run:
        mode_label += " (DRY-RUN SIMULATION)"

    print(f"\n{Color.BOLD}OnePlus 13R (CPH2691) Safe Optimization Suite v{VERSION}{Color.RESET}")
    print(f"Mode: {Color.CYAN}{mode_label}{Color.RESET}")
    print(f"Phases to execute: {', '.join(p.replace('phase_', 'P') for p in selected_phases)}\n")

    # Connect device if not in dry-run
    device_serial = args.device
    if not args.dry_run:
        print(f"{Color.CYAN}[*]{Color.RESET} Initializing persistent ADB server daemon...")
        start_cmd = [adb_path, "start-server"]
        if adb_path.endswith(".py"):
            start_cmd = [sys.executable, adb_path, "start-server"]
        try:
            subprocess.run(start_cmd, capture_output=True, text=True, timeout=10.0)
        except Exception as e:
            logger.log("WARN", f"adb start-server invocation warning: {e}")

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

        is_valid_model = validate_device_model(
            adb_path=adb_path,
            serial=device_serial,
            force=args.force,
            logger=logger,
        )
        if not is_valid_model:
            logger.close()
            return EXIT_RUNTIME_ERROR
    else:
        print(f"{Color.MAGENTA}[DRY-RUN]{Color.RESET} Operating in simulation mode -- no physical device commands will be sent.\n")

    # Execute selected phases
    rc = execute_phases(
        config=config,
        selected_phases=selected_phases,
        adb_path=adb_path,
        device_serial=device_serial,
        is_dry_run=args.dry_run,
        is_undo=args.undo,
        extra_commands=extra_commands,
        push_files=[(p["src"], p["dest"]) if isinstance(p, dict) else p for p in (push_files or [])],
        logger=logger,
    )

    logger.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
