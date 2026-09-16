#!/usr/bin/env python3
"""
Mock ADB Simulator and Test Harness for OnePlus 13R (CPH2691) Optimizer.

This module provides a realistic ADB server and shell emulator that accurately
simulates Android 16 / OxygenOS 16 behavior on a OnePlus 13R (CPH2691 / CPH2691IN),
including device authorization state machines, package existence checks,
verbatim Java exception throwing for missing packages, and settings management.

Can be run as a standalone CLI executable or imported into test suites.
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional

# Default state file location
DEFAULT_STATE_FILE = Path(__file__).resolve().parent / ".mock_adb_state.json"
DEFAULT_LOG_FILE = Path(__file__).resolve().parent / ".mock_adb_log.json"

# Stock packages verified on CPH2691IN
DEFAULT_INSTALLED_PACKAGES = [
    # Safe telemetry / OEM targets (present on device)
    "com.oplus.postmanservice",
    "com.oplus.onetrace",
    "com.oplus.stdsp",
    "com.oplus.qualityprotect",
    "com.facebook.system",
    "com.facebook.appmanager",
    "com.facebook.services",
    "com.heytap.browser",
    "com.heytap.htms",
    "com.oneplus.membership",
    # System apps for AOT
    "com.oplus.camera",
    "com.oneplus.gallery",
    "com.android.chrome",
    "com.google.android.youtube",
    "com.google.android.apps.maps",
    # User / messaging apps for Doze & AOT
    "com.whatsapp",
    "org.telegram.messenger",
    "com.instagram.android",
    "com.twitter.android",
    "com.spotify.music",
    "com.google.android.gm",
    "com.google.android.apps.messaging",
    "com.discord",
    "com.Slack",
    "org.thoughtcrime.securesms",
    # Critical protected blacklist packages
    "com.oplus.athena",
    "com.oplus.safecenter",
    "com.oplus.battery",
    "com.oplus.securityguard",
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

# Absent packages on CPH2691IN (trigger Java exceptions if pm disable-user is called directly)
DEFAULT_ABSENT_PACKAGES = [
    "com.oplus.crashbox",
    "com.heytap.pictorial",
    "net.oneplus.forums",
    "com.oplus.statistics.rom",
    "com.oplus.logkit",
    "com.heytap.cloud",
]

class MockADBState:
    """Manages persistent or ephemeral state of the mock ADB device."""

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or DEFAULT_STATE_FILE
        self.load()

    def default_state(self) -> Dict[str, Any]:
        return {
            "server_running": False,
            "device_serial": "CPH2691_OP5D3BL1_MOCK",
            "device_state": "device",  # device, authorizing, unauthorized, offline, none
            "auth_step_count": 0,
            "auth_required_steps": 0,   # if > 0, status transitions after N checks
            "model": "CPH2691",
            "product_name": "CPH2691IN",
            "device_code": "OP5D3BL1",
            "android_version": "16",
            "build_id": "CPH2691_16.0.10.500(EX01)",
            "installed_packages": list(DEFAULT_INSTALLED_PACKAGES),
            "disabled_packages": [],
            "doze_whitelist": ["com.google.android.gms"],
            "settings": {
                "global": {
                    "window_animation_scale": "1.0",
                    "transition_animation_scale": "1.0",
                    "animator_duration_scale": "1.0",
                    "wifi_scan_always_enabled": "1",
                    "ble_scan_always_enabled": "1",
                    "mobile_data_always_on": "1",
                    "adaptive_battery_management_enabled": "1",
                    "game_driver_all_apps": "0",
                    "wifi_scan_throttle_enabled": "0",
                },
                "secure": {
                    "quick_access_wallet_enabled": "0",
                    "lockscreen_show_wallet": "0",
                    "nfc_on": "0",
                    "oplus_customize_screen_refresh_rate": "1",
                },
                "system": {
                    "high_performance_mode": "0",
                    "peak_refresh_rate": "120.0",
                    "min_refresh_rate": "60.0",
                },
            },
            "device_config": {
                "activity_manager": {
                    "max_phantom_processes": "32",
                }
            },
            "compiled_packages": {},
            "history": [],
        }

    def load(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                    return
            except Exception:
                pass
        self.data = self.default_state()
        self.save()

    def save(self):
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            pass

    def log_call(self, args: List[str], rc: int, stdout: str, stderr: str):
        record = {
            "timestamp": time.time(),
            "args": args,
            "returncode": rc,
            "stdout": stdout,
            "stderr": stderr,
        }
        self.data.setdefault("history", []).append(record)
        self.save()
        # Also write to separate append-only log file if available
        try:
            log_entries = []
            if DEFAULT_LOG_FILE.exists():
                with open(DEFAULT_LOG_FILE, "r", encoding="utf-8") as f:
                    log_entries = json.load(f)
            log_entries.append(record)
            with open(DEFAULT_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(log_entries, f, indent=2)
        except Exception:
            pass

    def reset(self):
        self.data = self.default_state()
        self.save()
        if DEFAULT_LOG_FILE.exists():
            try:
                DEFAULT_LOG_FILE.unlink()
            except Exception:
                pass


def handle_adb_command(args: List[str], state: MockADBState) -> int:
    """Processes an ADB command invocation and produces stdout/stderr/returncode."""
    if not args:
        print("Android Debug Bridge version 1.0.41")
        print("Version 36.0.1")
        return 0

    subcmd = args[0]

    if subcmd in ("version", "--version"):
        print("Android Debug Bridge version 1.0.41")
        print("Version 36.0.1")
        print(f"Installed as {Path(__file__).resolve()}")
        return 0

    if subcmd == "start-server":
        state.data["server_running"] = True
        state.save()
        print("* daemon not running; starting now at tcp:5037")
        print("* daemon started successfully")
        return 0

    if subcmd == "kill-server":
        state.data["server_running"] = False
        state.save()
        return 0

    # Device listing
    if subcmd == "devices":
        long_format = "-l" in args
        # Check environment override
        env_state = os.environ.get("MOCK_ADB_DEVICE_STATE")
        if env_state:
            curr_state = env_state
        else:
            curr_state = state.data.get("device_state", "device")

        # Handle progressive authorization transition
        req_steps = state.data.get("auth_required_steps", 0)
        curr_step = state.data.get("auth_step_count", 0)
        if req_steps > 0:
            if curr_step < req_steps:
                curr_state = "authorizing"
                state.data["auth_step_count"] = curr_step + 1
                state.save()
            else:
                curr_state = "device"
                state.data["device_state"] = "device"
                state.save()

        print("List of devices attached")
        if curr_state == "none":
            return 0

        serial = state.data.get("device_serial", "CPH2691_OP5D3BL1_MOCK")
        if long_format:
            model = state.data.get("model", "CPH2691")
            product = state.data.get("product_name", "CPH2691IN")
            device_code = state.data.get("device_code", "OP5D3BL1")
            print(f"{serial}               {curr_state} product:{product} model:{model} device:{device_code} transport_id:1")
        else:
            print(f"{serial}	{curr_state}")
        return 0

    # Handle serial option: adb -s <serial> ...
    cmd_args = list(args)
    if cmd_args[0] == "-s":
        if len(cmd_args) >= 3:
            cmd_args = cmd_args[2:]
        else:
            sys.stderr.write("error: option requires an argument -- s\n")
            return 1

    if not cmd_args:
        return 0

    # Shell subcommands
    if cmd_args[0] == "shell":
        shell_tokens = cmd_args[1:]
        if not shell_tokens:
            return 0
        # If passed as a single compound string: adb shell "cmd1; cmd2"
        if len(shell_tokens) == 1 and (";" in shell_tokens[0] or " " in shell_tokens[0]):
            subcommands = [sc.strip() for sc in shell_tokens[0].split(";") if sc.strip()]
            final_rc = 0
            for sc in subcommands:
                rc = execute_single_shell_command(sc.split(), state)
                if rc != 0:
                    final_rc = rc
            return final_rc
        return execute_single_shell_command(shell_tokens, state)

    sys.stderr.write(f"unknown command {cmd_args[0]}\n")
    return 1


def execute_single_shell_command(tokens: List[str], state: MockADBState) -> int:
    """Executes a single Android shell command under Mock ADB."""
    if not tokens:
        return 0

    # Clean leading path wrappers: /system/bin/cmd -> cmd, /system/bin/device_config -> device_config
    cmd_name = tokens[0].split("/")[-1]

    # 1. getprop
    if cmd_name == "getprop":
        prop = tokens[1] if len(tokens) > 1 else ""
        if prop == "ro.product.model":
            model = os.environ.get("MOCK_DEVICE_MODEL", state.data.get("model", "CPH2691"))
            print(model)
            return 0
        elif prop == "ro.product.name":
            print(state.data.get("product_name", "CPH2691IN"))
            return 0
        elif prop == "ro.product.device":
            print(state.data.get("device_code", "OP5D3BL1"))
            return 0
        elif prop == "ro.build.version.release":
            print(state.data.get("android_version", "16"))
            return 0
        elif prop == "ro.build.display.id":
            print(state.data.get("build_id", "CPH2691_16.0.10.500(EX01)"))
            return 0
        print("")
        return 0

    # 2. sm fstrim
    if cmd_name == "sm":
        if len(tokens) > 1 and tokens[1] == "fstrim":
            print("Trimmed 4503599627370496 bytes on /data")
            return 0
        return 0

    # 3. pm (Package Manager)
    if cmd_name == "pm":
        action = tokens[1] if len(tokens) > 1 else ""

        if action == "trim-caches":
            print("Trimmed caches")
            return 0

        if action == "list" and len(tokens) > 2 and tokens[2] == "packages":
            # List packages
            installed = state.data.get("installed_packages", [])
            for pkg in sorted(installed):
                print(f"package:{pkg}")
            return 0

        if action == "disable-user":
            # Syntax: pm disable-user --user 0 <package>
            pkg = tokens[-1]
            installed = state.data.get("installed_packages", [])
            if pkg not in installed or pkg in DEFAULT_ABSENT_PACKAGES:
                # Verbatim Android Java stack trace on missing package
                sys.stderr.write(
                    f"Exception occurred while executing 'disable-user':\n"
                    f"java.lang.IllegalArgumentException: Unknown package: {pkg}\n"
                    f"\tat com.android.server.pm.PackageManagerService.setEnabledSettings(PackageManagerService.java:4283)\n"
                    f"\tat com.android.server.pm.PackageManagerShellCommand.runSetEnabledSetting(PackageManagerShellCommand.java:2455)\n"
                )
                return 1
            if pkg not in state.data.get("disabled_packages", []):
                state.data.setdefault("disabled_packages", []).append(pkg)
                state.save()
            print(f"Package {pkg} new state: disabled-user")
            return 0

        if action == "enable":
            # Syntax: pm enable --user 0 <package> or pm enable <package>
            pkg = tokens[-1]
            installed = state.data.get("installed_packages", [])
            if pkg not in installed or pkg in DEFAULT_ABSENT_PACKAGES:
                sys.stderr.write(
                    f"Exception occurred while executing 'enable':\n"
                    f"java.lang.IllegalArgumentException: Unknown package: {pkg}\n"
                )
                return 1
            if pkg in state.data.get("disabled_packages", []):
                state.data["disabled_packages"].remove(pkg)
                state.save()
            print(f"Package {pkg} new state: enabled")
            return 0

        return 0

    # 4. settings
    if cmd_name == "settings":
        op = tokens[1] if len(tokens) > 1 else ""
        ns = tokens[2] if len(tokens) > 2 else "global"
        key = tokens[3] if len(tokens) > 3 else ""

        ns_dict = state.data.setdefault("settings", {}).setdefault(ns, {})

        if op == "put":
            val = tokens[4] if len(tokens) > 4 else ""
            ns_dict[key] = val
            state.save()
            return 0

        if op == "get":
            val = ns_dict.get(key, "null")
            print(val)
            return 0

        if op == "delete":
            if key in ns_dict:
                del ns_dict[key]
                state.save()
            return 0

        return 0

    # 5. dumpsys
    if cmd_name == "dumpsys":
        service = tokens[1] if len(tokens) > 1 else ""
        if service == "deviceidle":
            # whitelist queries/modifications
            if len(tokens) > 3 and tokens[2] == "whitelist":
                target = tokens[3]
                whitelist = state.data.setdefault("doze_whitelist", [])
                if target.startswith("+"):
                    pkg = target[1:]
                    if pkg not in whitelist:
                        whitelist.append(pkg)
                    state.save()
                    print(f"Added: {pkg}")
                    return 0
                elif target.startswith("-"):
                    pkg = target[1:]
                    if pkg in whitelist:
                        whitelist.remove(pkg)
                    state.save()
                    print(f"Removed: {pkg}")
                    return 0
            elif len(tokens) > 2 and tokens[2] == "whitelist":
                for pkg in state.data.get("doze_whitelist", []):
                    print(f"system-on-data,{pkg},10000")
                return 0
        return 0

    # 6. cmd
    if cmd_name == "cmd":
        if len(tokens) > 1 and tokens[1] == "package":
            if len(tokens) > 2 and tokens[2] == "compile":
                # Compilation: -m speed <pkg>, -m speed-profile -a, --reset <pkg>, --reset -a
                sub = tokens[3] if len(tokens) > 3 else ""
                compiled = state.data.setdefault("compiled_packages", {})
                if sub == "-m":
                    mode = tokens[4] if len(tokens) > 4 else "speed"
                    pkg = tokens[5] if len(tokens) > 5 else "-a"
                    compiled[pkg] = mode
                    state.save()
                    print("Success")
                    return 0
                elif sub == "--reset":
                    pkg = tokens[4] if len(tokens) > 4 else "-a"
                    if pkg == "-a":
                        compiled.clear()
                    elif pkg in compiled:
                        del compiled[pkg]
                    state.save()
                    print("Success")
                    return 0
        return 0

    # 7. svc
    if cmd_name == "svc":
        sub = tokens[1] if len(tokens) > 1 else ""
        act = tokens[2] if len(tokens) > 2 else ""
        if sub == "nfc":
            state.data["settings"]["secure"]["nfc_on"] = "1" if act == "enable" else "0"
            state.save()
            return 0
        return 0

    # 8. device_config
    if cmd_name == "device_config":
        op = tokens[1] if len(tokens) > 1 else ""
        ns = tokens[2] if len(tokens) > 2 else ""
        key = tokens[3] if len(tokens) > 3 else ""
        cfg_ns = state.data.setdefault("device_config", {}).setdefault(ns, {})

        if op == "put":
            val = tokens[4] if len(tokens) > 4 else ""
            cfg_ns[key] = val
            state.save()
            return 0
        elif op == "delete":
            if key in cfg_ns:
                del cfg_ns[key]
                state.save()
            return 0
        elif op == "set_sync_disabled_for_tests":
            return 0
        return 0

    # 9. am start
    if cmd_name == "am":
        if len(tokens) > 1 and tokens[1] == "start":
            print(f"Starting: Intent {{ act=android.intent.action.MAIN {' '.join(tokens[2:])} }}")
            return 0
        return 0

    return 0


class MockADBController:
    """Programmatic control interface for test suites to configure mock state."""

    def __init__(self, state_file: Optional[Path] = None):
        self.state = MockADBState(state_file)

    def reset(self):
        self.state.reset()

    def set_device_state(self, status: str):
        """Set state: 'device', 'authorizing', 'unauthorized', 'offline', 'none'."""
        self.state.data["device_state"] = status
        self.state.save()

    def configure_auth_transition(self, authorizing_steps: int):
        """Require N checks in 'authorizing' before transitioning to 'device'."""
        self.state.data["device_state"] = "authorizing"
        self.state.data["auth_step_count"] = 0
        self.state.data["auth_required_steps"] = authorizing_steps
        self.state.save()

    def set_model(self, model: str):
        self.state.data["model"] = model
        self.state.save()

    def get_setting(self, namespace: str, key: str) -> Optional[str]:
        self.state.load()
        return self.state.data.get("settings", {}).get(namespace, {}).get(key)

    def is_package_disabled(self, pkg: str) -> bool:
        self.state.load()
        return pkg in self.state.data.get("disabled_packages", [])

    def is_package_whitelisted(self, pkg: str) -> bool:
        self.state.load()
        return pkg in self.state.data.get("doze_whitelist", [])

    def is_server_running(self) -> bool:
        self.state.load()
        return bool(self.state.data.get("server_running", False))

    def get_command_history(self) -> List[Dict[str, Any]]:
        self.state.load()
        return list(self.state.data.get("history", []))


def main():
    state = MockADBState()
    args = sys.argv[1:]

    # Capture stdout and stderr for history logging
    from io import StringIO
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    out_buf = StringIO()
    err_buf = StringIO()

    class TeeStream:
        def __init__(self, original, buffer):
            self.orig = original
            self.buf = buffer
        def write(self, s):
            self.orig.write(s)
            self.buf.write(s)
        def flush(self):
            self.orig.flush()
            self.buf.flush()

    sys.stdout = TeeStream(old_stdout, out_buf)
    sys.stderr = TeeStream(old_stderr, err_buf)

    rc = 0
    try:
        rc = handle_adb_command(args, state)
    except Exception as e:
        sys.stderr.write(f"Mock ADB Internal Error: {e}\n")
        rc = 1
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        state.log_call(args, rc, out_buf.getvalue(), err_buf.getvalue())

    sys.exit(rc)


if __name__ == "__main__":
    main()
