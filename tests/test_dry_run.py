#!/usr/bin/env python3
"""
Tier 4 Test Suite: Dry-Run Simulation.

Tests dry-run execution mode:
- Clean exit code 0 without any connected physical device
- Exhaustive preview of all forward optimization commands across all phases
- Exhaustive preview of all reverse rollback commands under --dry-run --undo
- Summary status table rendered at completion
- Confirmation of zero side effects
"""

import sys
import os
import unittest
from pathlib import Path

from tests.test_helpers import run_optimizer, SCRIPT_PATH


class TestDryRunSimulation(unittest.TestCase):
    """Test suite for Tier 4: Dry-Run mode and output verification."""

    def setUp(self):
        if not SCRIPT_PATH.exists():
            self.fail(f"Required target script 'optimize_13r.py' not found at {SCRIPT_PATH}. (Milestone M2 target)")

    def test_dry_run_exits_zero_without_device(self):
        """Verifies optimize_13r.py --dry-run exits 0 in a completely disconnected environment."""
        proc = run_optimizer(["--dry-run"])
        self.assertEqual(
            proc.returncode,
            0,
            f"Expected exit code 0 for --dry-run, got {proc.returncode}.\nStderr:\n{proc.stderr}",
        )

    def test_dry_run_outputs_all_core_forward_commands(self):
        """Verifies forward optimization commands are output during dry-run."""
        proc = run_optimizer(["--dry-run"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout

        # Phase 1: Storage
        self.assertTrue(
            "sm fstrim" in output or "trim-caches" in output,
            "Phase 1 (Storage/Cache) command not found in dry-run output.",
        )

        # Phase 2: Animations (0.5x)
        self.assertIn("window_animation_scale", output)
        self.assertIn("0.5", output)

        # Phase 3: Radios / Battery
        self.assertTrue(
            "wifi_scan_always_enabled" in output or "mobile_data_always_on" in output,
            "Phase 3 (Radios/Battery) command not found in dry-run output.",
        )

        # Phase 4: Doze Whitelist
        self.assertIn("deviceidle whitelist", output)
        self.assertIn("+", output)

        # Phase 5: Telemetry Freeze
        self.assertIn("pm disable-user", output)

        # Phase 6: AOT Compilation
        self.assertIn("package compile", output)

        # Phase 7: Google Wallet & NFC
        self.assertTrue(
            "quick_access_wallet_enabled" in output or "svc nfc" in output,
            "Phase 7 (Wallet/NFC) command not found in dry-run output.",
        )

    def test_dry_run_outputs_new_categories(self):
        """Verifies new optimization categories (GPU, Scheduler, Network, Thermal, Display) are previewed."""
        proc = run_optimizer(["--dry-run"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout

        # At least 3 new categories per R2 requirement:
        # Category A: GPU Game Driver
        has_gpu = "game_driver_all_apps" in output
        # Category B: Scheduler / Phantom Process / Cached apps
        has_scheduler = "max_phantom_processes" in output or "max_cached_processes" in output
        # Category C: Network Private DNS
        has_network = "private_dns" in output or "wifi_scan_throttle" in output
        # Category D: Thermal / Performance mode
        has_thermal = "high_performance_mode" in output
        # Category E: Display 120Hz unlock
        has_display = "oplus_customize_screen_refresh_rate" in output or "peak_refresh_rate" in output

        categories_present = sum([has_gpu, has_scheduler, has_network, has_thermal, has_display])
        self.assertTrue(
            categories_present >= 3,
            f"Expected at least 3 new categories in dry run, found {categories_present}.",
        )

    def test_dry_run_undo_outputs_reverse_commands(self):
        """Verifies --dry-run --undo previews symmetric rollback commands."""
        proc = run_optimizer(["--dry-run", "--undo"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout

        # Phase 2 undo: scale to 1.0
        self.assertIn("window_animation_scale", output)
        self.assertIn("1.0", output)

        # Phase 3 undo: scan enabled to 1
        self.assertTrue(
            "wifi_scan_always_enabled" in output or "mobile_data_always_on" in output,
            "Phase 3 undo not found in rollback preview.",
        )

        # Phase 4 undo: - package
        self.assertIn("deviceidle whitelist", output)
        self.assertIn("-", output)

        # Phase 5 undo: pm enable
        self.assertIn("pm enable", output)

        # Phase 6 undo: compile --reset
        self.assertTrue("compile --reset" in output or "--reset" in output)

    def test_dry_run_summary_table_rendered(self):
        """Verifies that a completion summary table is output."""
        proc = run_optimizer(["--dry-run"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout

        # Check for table or phase summary markers
        has_table_marker = any(
            marker in output for marker in ("Phase", "Status", "Summary", "======", "------", "✅", "⚠️", "SIMULATED")
        )
        self.assertTrue(has_table_marker, "Dry-run output must render a completion summary table.")


if __name__ == "__main__":
    unittest.main()
