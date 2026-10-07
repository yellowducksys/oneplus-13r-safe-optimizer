#!/usr/bin/env python3
"""
Tier 8 Test Suite: OnePlus 13R Optimizer 3.0 Control Deck & State Engine.

Tests v3.0 core capabilities:
- New CLI argument flags (--tui, --snapshot, --restore, --audit, --fix-drift, --preset, --wireless, --pair)
- State snapshot generation and JSON schema integrity
- Symmetrical state restore from snapshot file and 'latest' keyword
- Automated OTA configuration drift detection and report table formatting
- Selective drift fixing (--fix-drift)
- All 4 dynamic presets (balanced, gaming, battery, gcam)
- Untethered Wireless ADB pairing and connection
- Safe flash endurance: fstrim_mandatory_interval 86400 removed and actively deleted
- Hardware metadata: Qualcomm Snapdragon 8 Gen 3 (SM8650-AB) and Adreno 750
"""

import json
import os
import pathlib
import re
import unittest

from tests.test_helpers import (
    run_optimizer,
    SCRIPT_PATH,
    PROJECT_ROOT,
    load_test_config,
)


class TestV3Features(unittest.TestCase):
    """Test suite for Tier 8: Optimizer 3.0 Control Deck & State Engine."""

    def setUp(self):
        if not SCRIPT_PATH.exists():
            self.fail(f"Required target script 'optimize_13r.py' not found at {SCRIPT_PATH}.")

    def test_v3_cli_arguments_documented_in_help(self):
        """Verifies --help documents all v3.0 flags."""
        proc = run_optimizer(["--help"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout

        v3_flags = [
            "--tui",
            "--snapshot",
            "--restore",
            "--audit",
            "--fix-drift",
            "--preset",
            "--wireless",
            "--pair",
        ]
        for flag in v3_flags:
            self.assertIn(
                flag,
                output,
                f"v3.0 flag '{flag}' must be documented in --help output.",
            )

    def test_v3_snapshot_creation_and_file_format(self):
        """Verifies --snapshot --dry-run captures and creates a valid JSON snapshot file."""
        proc = run_optimizer(["--snapshot", "--dry-run"])
        self.assertEqual(proc.returncode, 0, f"Snapshot creation failed: {proc.stderr}")
        self.assertIn("Saved device snapshot", proc.stdout)

        # Verify snapshots directory has at least one valid snapshot
        snapshot_dir = PROJECT_ROOT / "snapshots"
        self.assertTrue(snapshot_dir.exists(), "snapshots/ directory was not created.")
        snapshots = list(snapshot_dir.glob("device_state_*.json"))
        self.assertTrue(len(snapshots) > 0, "No device_state_*.json file found in snapshots/.")

        latest_snap = sorted(snapshots, key=os.path.getmtime, reverse=True)[0]
        with open(latest_snap, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("version", data)
        self.assertIn("settings", data)
        self.assertIn("doze_whitelist", data)
        self.assertIn("disabled_packages", data)
        self.assertEqual(data.get("target_model"), "CPH2691")
        self.assertIn("Snapdragon 8 Gen 3", data.get("soc", ""))

    def test_v3_snapshot_restore_latest(self):
        """Verifies --restore latest --dry-run reads latest snapshot and outputs restore commands."""
        # Ensure a snapshot exists
        run_optimizer(["--snapshot", "--dry-run"])

        proc = run_optimizer(["--restore", "latest", "--dry-run"])
        self.assertEqual(proc.returncode, 0, f"Restore failed: {proc.stderr}")
        output = proc.stdout
        self.assertIn("Restoring device state from snapshot", output)
        self.assertIn("[DRY-RUN] adb shell settings put", output)

    def test_v3_drift_audit_report(self):
        """Verifies --audit --dry-run renders clean drift audit report table."""
        proc = run_optimizer(["--audit", "--dry-run"])
        self.assertEqual(proc.returncode, 0, f"Audit failed: {proc.stderr}")
        output = proc.stdout
        self.assertIn("ONEPLUS 13R (CPH2691) OTA CONFIGURATION DRIFT AUDIT", output)
        self.assertIn("Phase 1", output)
        self.assertIn("Phase 12", output)
        self.assertIn("[APPLIED] OK", output)
        self.assertIn("SYSTEM HEALTHY", output)

    def test_v3_fix_drift_dry_run(self):
        """Verifies --fix-drift --dry-run exits 0 and reports status cleanly."""
        proc = run_optimizer(["--fix-drift", "--dry-run"])
        self.assertEqual(proc.returncode, 0, f"Fix drift failed: {proc.stderr}")
        self.assertTrue(
            "Nothing to fix" in proc.stdout or "Repaired" in proc.stdout or "Fixing" in proc.stdout,
            "Expected clean fix-drift status message in output.",
        )

    def test_v3_preset_balanced(self):
        """Verifies --preset balanced executes daily driver phases and disables HPM."""
        proc = run_optimizer(["--preset", "balanced", "--dry-run"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout
        self.assertIn("Balanced", output)
        self.assertIn("Window Animation Scales", output)
        self.assertIn("Display True 120Hz Refresh Rate", output)
        self.assertIn("high_performance_mode 0", output)

    def test_v3_preset_gaming(self):
        """Verifies --preset gaming opts into Adreno 750 game driver, HPM 1, and 120Hz lock."""
        proc = run_optimizer(["--preset", "gaming", "--dry-run"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout
        self.assertIn("Gaming", output)
        self.assertIn("game_driver_all_apps 1", output)
        self.assertIn("high_performance_mode 1", output)
        self.assertIn("min_refresh_rate 120.0", output)

    def test_v3_preset_battery(self):
        """Verifies --preset battery caps refresh rate to 60Hz and turns off game driver and HPM."""
        proc = run_optimizer(["--preset", "battery", "--dry-run"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout
        self.assertIn("Battery", output)
        self.assertIn("game_driver_all_apps 0", output)
        self.assertIn("peak_refresh_rate 60.0", output)
        self.assertIn("high_performance_mode 0", output)

    def test_v3_preset_gcam(self):
        """Verifies --preset gcam compiles camera pipelines and deploys 50MP Quad-Bayer profile."""
        proc = run_optimizer(["--preset", "gcam", "--dry-run"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout
        self.assertIn("GCam", output)
        self.assertIn("package compile -m speed com.oplus.camera", output)
        self.assertIn("OnePlus13R_50MP_Master.xml", output)
        self.assertIn("stagefright_low_latency 1", output)

    def test_v3_wireless_adb_commands(self):
        """Verifies --wireless and --pair CLI commands simulate without physical device."""
        proc_pair = run_optimizer(["--pair", "192.168.1.50:37123", "123456", "--dry-run"])
        self.assertEqual(proc_pair.returncode, 0)
        self.assertIn("adb pair 192.168.1.50:37123 123456", proc_pair.stdout)

        proc_wireless = run_optimizer(["--wireless", "192.168.1.50:5555", "--dry-run", "--phases", "2"])
        self.assertEqual(proc_wireless.returncode, 0)
        self.assertIn("adb connect 192.168.1.50:5555", proc_wireless.stdout)

    def test_fstrim_mandatory_interval_removed_and_deleted(self):
        """
        Verifies daily forced fstrim (fstrim_mandatory_interval 86400) is NEVER set
        and is actively deleted in both forward and undo execution modes.
        """
        proc_fwd = run_optimizer(["--dry-run", "--phases", "1"])
        self.assertEqual(proc_fwd.returncode, 0)
        self.assertNotIn("fstrim_mandatory_interval 86400", proc_fwd.stdout)
        self.assertNotIn("settings put global fstrim_mandatory_interval", proc_fwd.stdout)
        self.assertIn("settings delete global fstrim_mandatory_interval", proc_fwd.stdout)

        proc_undo = run_optimizer(["--dry-run", "--undo", "--phases", "1"])
        self.assertEqual(proc_undo.returncode, 0)
        self.assertIn("settings delete global fstrim_mandatory_interval", proc_undo.stdout)

    def test_hardware_target_snapdragon_8_gen_3(self):
        """Verifies configuration and script target Qualcomm Snapdragon 8 Gen 3 and Adreno 750."""
        config = load_test_config()
        self.assertIsNotNone(config)
        device = config.get("device", {})
        self.assertIn("Snapdragon 8 Gen 3", device.get("platform", ""))
        self.assertEqual(device.get("gpu"), "Adreno 750")
        self.assertEqual(device.get("model"), "CPH2691")


if __name__ == "__main__":
    unittest.main()
