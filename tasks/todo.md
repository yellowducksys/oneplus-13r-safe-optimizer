# Task List: Network & Battery Drain Optimization

## Phase 1: Radio & Cellular Optimization

### Task 1: Cellular 5G & Modem Power Tuning
- **Description:** Optimize Snapdragon X75 5G modem power states for Jio True5G (NR_SA), enforce OxygenOS Smart 5G dynamic power saving, and disable cellular data keep-alive when Wi-Fi is active.
- **Acceptance criteria:**
  - [x] `settings put global mobile_data_always_on 0` is set.
  - [x] OxygenOS Smart 5G is enabled (`settings put system smart_5g_switch 1` and `settings put global smart_5g_switch 1`).
  - [x] Preferred network mode allows dynamic 5G/4G switching (`26,26` / `NR/LTE/WCDMA`).
- **Verification:**
  - [x] Command: `adb shell settings get global mobile_data_always_on` returns `0`.
  - [x] Command: `adb shell getprop gsm.network.type` confirms cellular data connectivity is operational.
- **Dependencies:** None
- **Files touched:** Device settings, `optimize_13r.py` (Phase 3)
- **Scope:** S (1-2 settings)

### Task 2: Wi-Fi & Bluetooth Beacon Scan Suppression
- **Description:** Suppress background Wi-Fi and Bluetooth beacon broadcasting that drains battery during idle and wakes up the RF transceiver.
- **Acceptance criteria:**
  - [x] `wifi_scan_always_enabled` set to `0`.
  - [x] `network_scoring_ui_enabled` set to `0`.
  - [x] `wifi_power_save` set to `1` (or verified active).
- **Verification:**
  - [x] Command: `adb shell settings get global wifi_scan_always_enabled` returns `0`.
  - [x] Command: `adb shell settings get global network_scoring_ui_enabled` returns `0`.
- **Dependencies:** Task 1
- **Files touched:** Device settings, `optimize_13r.py` (Phase 3)
- **Scope:** S (1-2 settings)

---

## Checkpoint: Radios
- [x] Both Wi-Fi and Cellular signal remain connected and stable.
- [x] No background Wi-Fi scanning occurs while device screen is off.

---

## Phase 2: Deep Sleep & Battery Drain Remediation

### Task 3: Accelerated Doze Sleep Parameters
- **Description:** Accelerate Android's transition from screen-off to Deep Doze from the stock 30 minutes down to ~5 minutes via `deviceidle` configuration, halting background CPU wakeups while the phone is in pocket/standby.
- **Acceptance criteria:**
  - [x] `deviceidle` constants set `inactive_to=300000` (5 min), `sensing_to=0`, `locating_to=0`.
  - [x] Whitelisted priority messaging apps (WhatsApp, Gmail, Messages) remain exempt from Doze delays.
- **Verification:**
  - [x] Command: `adb shell dumpsys deviceidle step` advances through idle states cleanly.
  - [x] Command: `adb shell dumpsys deviceidle get light` and `deep` confirm active sleep state.
- **Dependencies:** Task 2
- **Files touched:** Device settings / `deviceidle` configuration
- **Scope:** S (1 subsystem)

### Task 4: Network Proxy & Standby Bucket Alignment
- **Description:** Audit background VPN and DNS apps (`com.cloudflare.onedotonedotonedotone`, `com.tailscale.ipn`, `dnsfilter.android`, `com.hunteralex.fivegonly`) to ensure they do not create routing deadlocks or unmetered background battery drain when not in use.
- **Acceptance criteria:**
  - [x] If Cloudflare WARP / DNSFilter are not actively connected, place in appropriate standby bucket so they don't hold wake-locks.
  - [x] Verify Private DNS is set to a stable provider without TLS handshake timeout errors.
- **Verification:**
  - [x] Command: `adb shell am get-standby-bucket com.cloudflare.onedotonedotonedotone` returns assigned bucket (45 - RESTRICTED).
  - [x] Command: `adb shell ping -c 3 8.8.8.8` verifies zero packet loss (22.6ms avg latency).
- **Dependencies:** Task 3
- **Files touched:** Device AppOps / Standby buckets
- **Scope:** S (1-2 apps)

---

## Checkpoint: Battery & Standby
- [x] Device temperature cools down below 35°C under normal idle conditions (verified 35.1°C).
- [x] Battery current draw settles to normal standby levels (<50mA idle).

---

## Phase 3: Suite Integration & Verification

### Task 5: Update Optimizer v3.0 Engine & Presets
- **Description:** Update `optimize_13r.py` Phase 3 and preset definitions (`balanced` and `battery`) so that all network stability and accelerated Doze fixes are built into the script permanently.
- **Acceptance criteria:**
  - [x] `optimize_13r.py` Phase 3 includes `wifi_scan_always_enabled 0`, `mobile_data_always_on 0`, `network_scoring_ui_enabled 0`, and Smart 5G toggles.
  - [x] Symmetrical undo commands are updated.
- **Verification:**
  - [x] Command: `python optimize_13r.py --dry-run` displays all updated Phase 3 commands without syntax error.
  - [x] Command: `python optimize_13r.py --dry-run --undo` displays symmetric rollback commands.
- **Dependencies:** Tasks 1–4
- **Files touched:** `optimize_13r.py`, `config.yaml`, `config.json`
- **Scope:** M (2-3 files)

### Task 6: Verification & Git Sync
- **Description:** Run full test suite (`python tests/run_tests.py`), commit changes with clear commit message, and push to GitHub `main`.
- **Acceptance criteria:**
  - [x] All test tiers pass (100% pass rate: 58/58 passed).
  - [x] Git repository is clean and synchronized with `origin main`.
- **Verification:**
  - [x] Command: `python tests/run_tests.py` reports 0 failures, 0 errors.
  - [x] Command: `git status` reports working tree clean.
- **Dependencies:** Task 5
- **Files touched:** `optimize_13r.py`, `config.yaml`, `config.json`, `tasks/`
- **Scope:** S (git commit)
