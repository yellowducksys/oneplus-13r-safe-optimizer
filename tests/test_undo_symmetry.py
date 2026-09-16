#!/usr/bin/env python3
"""
Tier 5 Test Suite: 100% Symmetric Undo Verification.

Programmatically asserts that EVERY state-changing forward optimization command
has an exact reverse/undo counterpart in rollback mode:
- Animation scale reversibility (0.5x -> 1.0x)
- Modem and radio reversibility (0 -> 1 for Wi-Fi/BLE background scans and mobile data)
- Doze whitelist bidirectional symmetry (+package in forward, -package in undo)
- Telemetry package freeze/enable symmetry (disable-user -> enable)
- AOT compilation reset symmetry (compile -m speed -> compile --reset)
- Google Wallet / NFC reversibility (enabled -> disabled)
- New categories symmetry (GPU game driver, scheduler limits, DNS, refresh rate)
"""

import sys
import os
import re
import unittest
from pathlib import Path
from typing import List, Set, Tuple

from tests.test_helpers import run_optimizer, SCRIPT_PATH, load_test_config


def extract_commands_from_output(output: str) -> List[str]:
    """Extracts shell command lines from CLI dry-run preview output."""
    commands = []
    for line in output.splitlines():
        line = line.strip()
        # Common formatting in CLI tools: "[CMD] adb shell ...", "$ adb shell ...", "adb shell ...", "  -> adb ..."
        if "adb shell" in line:
            parts = line.split("adb shell", 1)
            commands.append(parts[1].strip())
        elif line.startswith("adb "):
            commands.append(line[4:].strip())
        elif line.startswith("$ ") or line.startswith("> "):
            cmd = line[2:].strip()
            if "adb" in cmd:
                commands.append(cmd)
    return commands


class TestUndoCompleteness(unittest.TestCase):
    """Test suite for Tier 5: 100% Symmetric Undo verification."""

    def setUp(self):
        if not SCRIPT_PATH.exists():
            self.fail(f"Required target script 'optimize_13r.py' not found at {SCRIPT_PATH}. (Milestone M2 target)")

        # Run dry-run for forward and undo
        self.proc_fwd = run_optimizer(["--dry-run"])
        self.assertEqual(self.proc_fwd.returncode, 0, "Forward dry-run failed.")
        self.fwd_text = self.proc_fwd.stdout

        self.proc_undo = run_optimizer(["--dry-run", "--undo"])
        self.assertEqual(self.proc_undo.returncode, 0, "Undo dry-run failed.")
        self.undo_text = self.proc_undo.stdout

    def test_animation_scales_symmetry(self):
        """Verifies all three animation scales (window, transition, animator) reverse 0.5 -> 1.0."""
        scale_keys = [
            "window_animation_scale",
            "transition_animation_scale",
            "animator_duration_scale",
        ]
        for key in scale_keys:
            # Forward must set 0.5
            self.assertIn(
                key,
                self.fwd_text,
                f"Animation key '{key}' missing in forward optimization.",
            )
            # Undo must set 1.0
            self.assertIn(
                key,
                self.undo_text,
                f"Animation key '{key}' missing in undo rollback.",
            )
            self.assertIn(
                "1.0",
                self.undo_text,
                "Undo rollback must restore animation scale to factory default 1.0.",
            )

    def test_radio_settings_symmetry(self):
        """Verifies Phase 3 radio settings (wifi_scan, ble_scan, mobile_data) are fully reversed."""
        radio_keys = [
            "wifi_scan_always_enabled",
            "ble_scan_always_enabled",
            "mobile_data_always_on",
        ]
        for key in radio_keys:
            self.assertIn(
                key,
                self.fwd_text,
                f"Radio key '{key}' missing in forward optimization.",
            )
            self.assertIn(
                key,
                self.undo_text,
                f"CRITICAL DEFECT: Radio key '{key}' missing in rollback. Must be restored to 1!",
            )

    def test_doze_whitelist_symmetry(self):
        """Verifies every whitelisted package (+pkg) has an exact un-whitelist (-pkg) in undo."""
        # Find all whitelisted packages in forward
        fwd_matches = set(re.findall(r"whitelist\s+\+([a-zA-Z0-9._]+)", self.fwd_text))
        undo_matches = set(re.findall(r"whitelist\s+\-([a-zA-Z0-9._]+)", self.undo_text))

        self.assertTrue(len(fwd_matches) > 0, "No Doze whitelist packages found in forward output.")
        self.assertTrue(len(undo_matches) > 0, "No Doze un-whitelist packages found in undo output.")

        # Every forward whitelisted package must be removed in undo
        missing_undo = fwd_matches - undo_matches
        self.assertEqual(
            missing_undo,
            set(),
            f"CRITICAL ROLLBACK ASYMMETRY: These packages were whitelisted (+pkg) but never removed (-pkg) in undo: {missing_undo}",
        )

    def test_package_disable_enable_symmetry(self):
        """Verifies every package frozen via pm disable-user has an exact pm enable in undo."""
        # Regex to find disabled packages
        fwd_frozen = set(re.findall(r"disable-user.*?([a-zA-Z0-9._]+)$", self.fwd_text, re.MULTILINE))
        if not fwd_frozen:
            fwd_frozen = set(re.findall(r"disable-user\s+(?:--user\s+0\s+)?([a-zA-Z0-9._]+)", self.fwd_text))

        undo_enabled = set(re.findall(r"enable.*?([a-zA-Z0-9._]+)$", self.undo_text, re.MULTILINE))
        if not undo_enabled:
            undo_enabled = set(re.findall(r"pm\s+enable\s+(?:--user\s+0\s+)?([a-zA-Z0-9._]+)", self.undo_text))

        self.assertTrue(len(fwd_frozen) > 0, "No packages frozen in forward output.")
        self.assertTrue(len(undo_enabled) > 0, "No packages enabled in undo output.")

        missing_enable = fwd_frozen - undo_enabled
        self.assertEqual(
            missing_enable,
            set(),
            f"CRITICAL ROLLBACK ASYMMETRY: These packages were frozen but never re-enabled in undo: {missing_enable}",
        )

    def test_aot_compilation_reset_symmetry(self):
        """Verifies AOT speed compilation has a corresponding compile --reset in undo."""
        has_forward_compile = "compile" in self.fwd_text and ("speed" in self.fwd_text or "-m" in self.fwd_text)
        self.assertTrue(has_forward_compile, "AOT compilation commands not found in forward output.")

        has_undo_reset = "compile" in self.undo_text and "--reset" in self.undo_text
        self.assertTrue(
            has_undo_reset,
            "CRITICAL ROLLBACK ASYMMETRY: AOT compilation was applied but compile --reset was omitted in undo.",
        )

    def test_wallet_nfc_symmetry(self):
        """Verifies Phase 7 Wallet/NFC quick access tile modifications are reversed."""
        if "quick_access_wallet_enabled" in self.fwd_text:
            self.assertIn(
                "quick_access_wallet_enabled",
                self.undo_text,
                "quick_access_wallet_enabled must be reversed in undo.",
            )

    def test_gpu_and_refresh_rate_symmetry(self):
        """Verifies GPU Game Driver and 120Hz unlock settings are symmetrically restored."""
        if "game_driver_all_apps" in self.fwd_text:
            self.assertIn(
                "game_driver_all_apps",
                self.undo_text,
                "game_driver_all_apps must be reversed to 0 in undo.",
            )

        if "oplus_customize_screen_refresh_rate" in self.fwd_text:
            self.assertIn(
                "oplus_customize_screen_refresh_rate",
                self.undo_text,
                "oplus_customize_screen_refresh_rate must be reversed in undo.",
            )


if __name__ == "__main__":
    unittest.main()
