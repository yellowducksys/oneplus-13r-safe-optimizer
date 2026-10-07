# Implementation Plan: OnePlus 13R Network & Battery Drain Optimization

## Overview
Diagnostic telemetry on the connected OnePlus 13R (`CPH2691IN`, Snapdragon 8 Gen 3, Jio True5G) revealed that network instability and battery drain stem from three interconnected factors:
1. **Aggressive 5G Standalone (NR_SA) Modem Transmission**: The device is connected to Jio True5G (`NR_SA`) with a moderate signal strength (-88 dBm ssRsrp). In fluctuating signal environments, the Snapdragon X75 modem cranks transmit power (`TX Power`) to maximum and repeatedly searches channels if forced into 5G-only mode, burning battery and causing data stalls.
2. **Background Radio Polling**: `wifi_scan_always_enabled` is active (`1`) along with `network_scoring_ui_enabled` (`1`), causing the Wi-Fi and location subsystems to continuously broadcast channel scanning beacons even when connected to cellular or asleep.
3. **VPN & DNS Routing Layer Overlap**: Multiple network proxies (`1.1.1.1 Cloudflare WARP`, `DNSFilter`, `Tailscale`) and `private_dns_mode` switches introduce routing table contention and packet retry loops.

This plan resolves both network reliability and battery drain through systematic radio tuning, Doze sleep acceleration, Smart 5G policy enforcement, and network stack cleanup without requiring root or breaking 5G speeds.

---

## Architecture Decisions

### 1. Enable OxygenOS Smart 5G Dynamic Modulation
- **Decision:** Activate OxygenOS native Smart 5G (`oplus.radio.smart5g_switch 1` and `smart_5g_sa_cfg`).
- **Rationale:** Rather than locking the modem to power-hungry NR_SA permanently or dropping to 4G manually, Smart 5G keeps 5G active during high-bandwidth demands (streaming, downloads, gaming) and throttles the modem to low-power idle/LTE states when the screen is off or transferring background telemetry, saving up to ~25% battery on cellular data.

### 2. Disable Background Wi-Fi & BLE Location Scanning
- **Decision:** Set `wifi_scan_always_enabled 0`, `ble_scan_always_enabled 0`, and `network_scoring_ui_enabled 0`.
- **Rationale:** Stops the Wi-Fi and Bluetooth chips from waking the SoC every 15–30 seconds to report nearby access points to Google Location Services while keeping standard Wi-Fi and Bluetooth connectivity 100% operational.

### 3. Accelerated Deep Doze Timing Parameters
- **Decision:** Tune `deviceidle` constants so the device transitions into deep sleep within 5 minutes of screen-off instead of waiting the stock 30 minutes.
- **Rationale:** On a 6,000 mAh battery, idle standby drain is dominated by the initial 30 minutes post-screen-off where background apps continue churning. Accelerating light-doze and deep-doze saves an estimated ~3–5% battery per day.

### 4. Clean DNS & Network Stack Alignment
- **Decision:** Eliminate DNS retry latency by aligning Private DNS to either a low-latency provider or native ISP DNS, and disabling carrier network scoring probes.

---

## Task List

### Phase 1: Radio & Cellular Optimization (Tasks 1–2)
- [ ] **Task 1: Cellular 5G & Modem Power Tuning**: Enable OxygenOS Smart 5G, disable mobile data keep-alive on Wi-Fi, and configure VoNR fallback.
- [ ] **Task 2: Wi-Fi & Bluetooth Beacon Scan Suppression**: Disable `wifi_scan_always_enabled`, `network_scoring_ui_enabled`, and tune Wi-Fi sleep policy.

### Checkpoint: Radios
- [ ] Verify signal strength reporting and Wi-Fi stability without packet drops.
- [ ] Confirm `wifi_scan_always_enabled` is `0`.

### Phase 2: Deep Sleep & Battery Drain Remediation (Tasks 3–4)
- [ ] **Task 3: Accelerated Doze Sleep Parameters**: Configure `deviceidle` constants for rapid idle sleep and verify active wakelock suppression.
- [ ] **Task 4: Network Proxy & Standby Bucket Alignment**: Set standby buckets for background network tools (`com.cloudflare.onedotonedotonedotone`, `com.tailscale.ipn`, `com.hunteralex.fivegonly`) to prevent unmetered background drain.

### Checkpoint: Battery & Standby
- [ ] Verify device enters light doze and deep doze cleanly via `dumpsys deviceidle`.
- [ ] Inspect battery temperature and current draw (`dumpsys battery`).

### Phase 3: Suite Integration & Verification (Tasks 5–6)
- [ ] **Task 5: Update Optimizer v3.0 Engine & Presets**: Integrate the network and battery fixes into Phase 3 of `optimize_13r.py` and the `battery` / `balanced` presets.
- [ ] **Task 6: Verification & Git Sync**: Run test suite (`python tests/run_tests.py`), commit improvements, and push to GitHub.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|:---|:---:|:---|
| Smart 5G switches to LTE during high-speed downloads | Low | Smart 5G checks packet flow; when >4MB/s is requested, it instantly ramps to full 5G NR carrier aggregation. |
| Aggressive Doze delays push notifications | Medium | High-priority messaging apps (WhatsApp, Gmail, Messages, Slack) are already on the system Doze whitelist. |
| Private DNS connectivity failure on public Wi-Fi | Low | Private DNS is set to `opportunistic` or clean fallback mode, preventing captive portal lockout. |

---

## Open Questions
- Do you use the "5G Only" app (`com.hunteralex.fivegonly`) to force 5G in areas with weak signals, or do you prefer the phone to seamlessly fall back to 4G LTE when 5G signal dips below usable thresholds?
