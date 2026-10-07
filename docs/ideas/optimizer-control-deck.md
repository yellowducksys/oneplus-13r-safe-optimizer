# OnePlus 13R Optimizer 3.0 — Interactive Control Deck

## Problem Statement
How might we evolve `optimize_13r.py` from a static, blind-execution command runner into an intelligent, interactive Terminal Control Deck (TUI) that snapshots device state, detects post-OTA setting drift, supports on-demand profiles (Gaming/Battery/GCam), and runs untethered over Wireless ADB?

---

## Recommended Direction: Interactive Terminal Control Deck (TUI + State Engine)

Transform the script into a **zero-dependency, bi-directional device dashboard and preset engine**. Instead of blindly pushing commands to the device, the tool first queries current state, snapshots exact user configurations, diffs differences, and presents an interactive, keyboard-driven dashboard.

### Core Architecture Pillars:
1. **Interactive Terminal TUI (ANSI / Curses)**:
   - Live hardware status header: SoC (Snapdragon 8 Gen 3), battery level & temperature, current refresh rate mode, RAM usage, and active preset.
   - Interactive checklist with toggle keys (`Space` to toggle, `Enter` to apply, `Tab` to switch views).
   - Works natively in Windows PowerShell, macOS/Linux, and on-device inside **Termux**.
2. **State & Snapshot Engine (`--snapshot` / `--restore`)**:
   - Dumps existing device settings to a timestamped `snapshots/device_state_<date>.json` before touching anything.
   - True symmetrical rollback: restores the user's *exact prior values*, not generic hardcoded defaults.
3. **Automated OTA Doctor (`--audit` / `--fix-drift`)**:
   - Compares live device settings against the target optimization baseline.
   - Outputs a clean color-coded drift table highlighting which settings OxygenOS OTA updates wiped out.
   - 1-click re-application of only drifted settings.
4. **Dynamic Preset Profiles (`--preset <name>`)**:
   - `balanced`: Default daily driver (0.5x animations, MGLRU freezer, app standby bucketing, ADFR LTPO).
   - `gaming`: Adreno 750 game driver, High Performance Mode ON, sustained performance hint, bypass charging active.
   - `battery`: Wi-Fi/BLE throttling, aggressive Doze timeout, dark theme enforcement.
   - `gcam`: Native AOT camera pipelines, 50MP Quad-Bayer profile deployment, low-latency Stagefright buffer decoding.
5. **Wireless ADB Auto-Discovery (`--wireless [ip:port]`)**:
   - Supports wireless ADB pairing and execution so the phone can be optimized over home Wi-Fi without a physical USB cable.

---

## Key Assumptions to Validate

- [ ] **Windows Console ANSI Support**: Windows PowerShell 5.1/7 supports ANSI virtual terminal sequences without requiring third-party libraries (`rich`, `textual`). *(Test: verify `ENABLE_VIRTUAL_TERMINAL_PROCESSING` via ctypes on Windows)*.
- [ ] **Non-Destructive State Querying**: All 13 phases expose read queries (`settings get`, `dumpsys deviceidle`, `dumpsys package`) with negligible latency (<1.5s total scan time).
- [ ] **Termux Portability**: The same Python script can execute inside Android Termux calling local `adb` or `su/sh` environment.

---

## MVP Scope

### In Scope for v3.0:
* **Interactive TUI Dashboard**: Visual curses/ANSI menu with real-time toggleable phases and execution logs.
* **Smart Device Auditing**: `--audit` command that inspects all 13 phases and prints a live `[APPLIED]` vs `[STOCK / DRIFTED]` matrix.
* **Pre-Execution Snapshot**: Automated JSON snapshot creation before any write action.
* **4 Core Presets**: `--preset balanced|gaming|battery|gcam`.
* **Zero Dependencies**: Pure standard-library Python (`sys`, `os`, `subprocess`, `json`, `ctypes`, `time`, `argparse`).

### Not Doing (and Why):
* **Electron / Native GUI Desktop App**: Unnecessary bloat (200MB+ install size); a responsive TUI is faster, runs directly in the terminal, and works on both Windows PC and on-phone via Termux.
* **Root-Requiring Kernel Voltage Tables**: Still strictly adhering to the rootless boundary to preserve Widevine L1, Google Pay/UPI, and device warranty.
* **Continuous Background Daemon on PC**: The optimizer should remain an on-demand tool, not a resident background service that wastes PC RAM.

---

## Open Questions
1. Should the TUI launch by default when running `python optimize_13r.py` with no arguments, while keeping CLI flags (`--preset`, `--audit`, `--dry-run`) for automated scripts?
2. Do you want the snapshot engine to also backup user installed app APKs or strictly system settings and app states?
