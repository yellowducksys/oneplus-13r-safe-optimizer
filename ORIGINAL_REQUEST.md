# Original User Request

## 2026-09-16T01:46:51+05:30

Improve an existing OnePlus 13R (CPH2691) Safe Optimization Guide — a markdown document containing 7 phases of ADB-based Android optimization commands and an embedded Python automation script. The guide was recently executed on a real device and works, but needs a comprehensive overhaul: correctness audit, additional safe optimizations across several new categories, a much more robust Python script, and publication-quality documentation. The result should be a small, well-organized project (README + script + config) that the owner can confidently use and share.

Working directory: C:/Users/Harsh/.gemini/antigravity/scratch/oneplus_13r_optimizer
Integrity mode: benchmark

Reference material: The existing guide is at `C:/Users/Harsh/Downloads/ONEPLUS_13R_SAFE_OPTIMIZATION_GUIDE.md`

## Real-World Observations from Live Execution

These issues were discovered when running the guide on an actual OnePlus 13R (CPH2691, OxygenOS):

1. **ADB not on PATH** — The guide assumes `adb` is in PATH, but the only ADB binary on the test system was bundled inside `C:\Program Files\O+Connect\daemon\bin\adb.exe`. The script should auto-discover ADB or accept a custom path.
2. **3 packages not found** — `com.oplus.crashbox`, `com.heytap.pictorial`, and `net.oneplus.forums` don't exist on OxygenOS 15/16 India variant (CPH2691IN). The script silently threw Java exceptions. It should handle "Unknown package" gracefully.
3. **ADB server restart on every call** — Each `subprocess.run(["adb", "shell", ...])` spawns a new ADB daemon handshake. The script should start the server once upfront and reuse it.
4. **Device showed `unauthorized` then `authorizing`** — The guide's pre-flight section doesn't cover the multi-step auth handshake or retry logic.
5. **PowerShell `&&` incompatibility** — Mentioned in the guide but the manual commands still use patterns that trip up PS 5.1 users.
6. **The `--undo` rollback is incomplete** — It only reverts animation scales and re-enables frozen packages. It does NOT undo Phase 3 (battery/radio settings), Phase 4 (Doze whitelist), or Phase 7 (NFC/Wallet settings).

## Requirements

### R1. Correctness Audit & Safety Review

Review every ADB command in the existing guide for correctness, safety, and device compatibility. Fix the 6 real-world issues listed above. Ensure the "NEVER TOUCH" blacklist is complete and accurate for OxygenOS 15/16. Verify that every `pm disable-user` target is genuinely safe to freeze and won't break core OS functionality, banking apps, or OTA updates.

### R2. New Optimization Categories

Research and add safe, rootless ADB optimizations across these categories. Every new tweak must be individually reversible and must NOT require root or bootloader unlock:

- **GPU rendering** (e.g., force GPU rendering, disable HW overlays only if safe)
- **Scheduler / process tuning** (e.g., background process limits)
- **Network** (private DNS configuration, IPv6 preferences, TCP buffer tuning)
- **Thermal management** (e.g., thermal throttling profiles if accessible without root)
- **Display** (refresh rate forcing, peak brightness settings if accessible)
- **App-specific** (expand Doze whitelist and AOT compilation to common apps: Instagram, Telegram, Spotify, Twitter/X, etc.)

### R3. Robust Python Automation Script

Rewrite `optimize_13r.py` as a production-quality CLI tool with:

- **ADB auto-discovery**: Search common install paths (Android SDK, O+Connect, scoop, PATH) and accept `--adb-path` override
- **Device validation**: Check for `device` status (not `unauthorized`/`offline`), confirm model, retry with backoff on `authorizing`
- **Per-phase selection**: `--phases 1,2,3` or `--skip 5,7` to run/skip specific phases
- **Dry-run mode**: `--dry-run` prints all commands without executing
- **Graceful error handling**: Catch "Unknown package" and other package-not-found errors, log them as warnings, continue execution
- **Complete `--undo`**: Reverse ALL phases, not just animations and frozen packages
- **Logging**: Write a timestamped log file of every command and its result
- **Progress output**: Clear phase headers, success/warning/error indicators, summary table at the end
- **Config file support**: Load app lists (Doze whitelist, AOT targets, freeze targets) from a YAML/JSON config so users can customize without editing the script

### R4. Publication-Quality Documentation

Produce a well-structured project with:

- `README.md` — The main guide with all phases, safety info, and troubleshooting
- `optimize_13r.py` — The standalone automation script
- `config.yaml` (or `.json`) — Customizable app lists and settings
- Troubleshooting section covering: ADB not found, device unauthorized, package not found, PowerShell compatibility, O+Connect port conflicts
- Clear "What This Does / What This Doesn't Do" section for transparency

## Acceptance Criteria

### Correctness & Safety
- [ ] Every ADB command in the final guide is syntactically valid and targets documented Android settings/APIs
- [ ] All 6 real-world issues from the observations section are addressed
- [ ] The `--undo` command reverses every single setting changed by the optimization (not just a subset)
- [ ] The blacklist ("NEVER TOUCH") section includes rationale for each entry and is verified against OxygenOS 15/16 package lists
- [ ] No command requires root, bootloader unlock, or custom recovery

### Script Quality
- [ ] `optimize_13r.py` runs successfully with `python optimize_13r.py --dry-run` without a connected device (prints commands, exits 0)
- [ ] `python optimize_13r.py --help` displays usage with all flags documented
- [ ] Unknown/missing packages produce a warning log line, not an unhandled exception or script abort
- [ ] The script produces a summary table at completion showing each phase's status (✅/⚠️/❌)
- [ ] Config file (`config.yaml` or `config.json`) is valid and loadable; the script uses it for all app lists

### Documentation Quality
- [ ] README.md renders correctly as GitHub-flavored Markdown (no broken tables, links, or formatting)
- [ ] Every new optimization includes: what it does, why it helps, how to undo it, and any caveats
- [ ] Troubleshooting section covers all 6 real-world issues observed during live execution

### New Optimizations
- [ ] At least 3 new optimization categories are added beyond the original 7 phases
- [ ] Each new tweak cites its ADB setting key and expected behavior
- [ ] All new tweaks are included in both the manual guide and the automated script
