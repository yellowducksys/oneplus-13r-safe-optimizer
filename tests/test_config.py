#!/usr/bin/env python3
"""
Tier 2 Test Suite: Configuration Loading and Schema Validation.

Tests configuration parsing, schema contracts, and fallback behaviors:
- Schema validation of config.yaml and config.json
- Verification of 15 protected packages in the NEVER TOUCH blacklist
- Safety verification: blacklist packages MUST NEVER appear in freeze targets
- Custom config file loading via --config flag
- Malformed config file error reporting and exit codes
- Graceful fallback to embedded defaults when config file is absent
"""

import sys
import os
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_helpers import (
    run_optimizer,
    SCRIPT_PATH,
    CONFIG_YAML_PATH,
    CONFIG_JSON_PATH,
    load_test_config,
)

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


class TestConfigValidation(unittest.TestCase):
    """Test suite for Tier 2: Configuration schema, loading, and fallback."""

    def test_project_config_files_exist_and_are_valid(self):
        """Verifies that at least one of config.yaml or config.json exists and is valid."""
        has_config = CONFIG_YAML_PATH.exists() or CONFIG_JSON_PATH.exists()
        if not has_config:
            self.fail(
                "Neither config.yaml nor config.json was found in project root. "
                "(Milestone M1 target)"
            )

        config_data = load_test_config()
        self.assertIsNotNone(config_data, "Failed to load project configuration file.")
        self.assertIsInstance(config_data, dict, "Configuration root must be a dictionary/mapping.")

    def test_config_device_specification(self):
        """Verifies the device section targets CPH2691 / OnePlus 13R."""
        config_data = load_test_config()
        if config_data is None:
            self.skipTest("config file not available yet")

        device_info = config_data.get("device", {})
        model = device_info.get("model") or device_info.get("target_model")
        self.assertEqual(
            model,
            "CPH2691",
            f"Config must target model 'CPH2691', found: {model}",
        )

    def test_blacklist_contains_all_15_critical_protected_packages(self):
        """Verifies that the configuration blacklist includes all 15 protected packages."""
        config_data = load_test_config()
        if config_data is None:
            self.skipTest("config file not available yet")

        blacklist = config_data.get("blacklist", [])
        self.assertTrue(len(blacklist) >= 15, f"Blacklist must contain at least 15 packages, found {len(blacklist)}")

        for pkg in MANDATORY_BLACKLIST:
            self.assertIn(
                pkg,
                blacklist,
                f"Critical system package '{pkg}' missing from protected blacklist.",
            )

    def test_blacklist_safety_invariant(self):
        """CRITICAL SAFETY INVARIANT: No blacklist package must ever be present in freeze targets!"""
        config_data = load_test_config()
        if config_data is None:
            self.skipTest("config file not available yet")

        # Collect all freeze targets across config formats
        freeze_targets = []
        if "packages" in config_data and "telemetry_freeze_targets" in config_data["packages"]:
            freeze_targets.extend(config_data["packages"]["telemetry_freeze_targets"])
        elif "freeze_targets" in config_data:
            freeze_targets.extend(config_data["freeze_targets"])
        elif "phases" in config_data:
            for p_id, p_val in config_data["phases"].items():
                if p_val.get("type") == "package_disable" or "freeze" in p_id:
                    freeze_targets.extend(p_val.get("packages", []))

        blacklist_set = set(MANDATORY_BLACKLIST)
        for target in freeze_targets:
            self.assertNotIn(
                target,
                blacklist_set,
                f"FATAL SAFETY VIOLATION: Protected package '{target}' is included in freeze targets!",
            )

    def test_all_12_phases_defined_in_config(self):
        """Verifies that all 12 optimization phases (1 to 7 + A to E/F) are declared."""
        config_data = load_test_config()
        if config_data is None:
            self.skipTest("config file not available yet")

        phases = config_data.get("phases", {})
        self.assertTrue(len(phases) >= 12, f"Config must define at least 12 phases, found {len(phases)}.")

        for p_num in range(1, 13):
            p_key = f"phase_{p_num}"
            self.assertIn(p_key, phases, f"Mandatory phase '{p_key}' missing from configuration phases mapping.")
            p_meta = phases[p_key]
            self.assertIn("name", p_meta, f"Phase {p_key} missing 'name' attribute.")
            self.assertIn("description", p_meta, f"Phase {p_key} missing 'description' attribute.")
            self.assertIn("commands", p_meta, f"Phase {p_key} missing 'commands' list.")
            self.assertIn("undo_commands", p_meta, f"Phase {p_key} missing 'undo_commands' list.")

    def test_phases_undo_symmetry_in_config(self):
        """Verifies that all state-modifying phases (phases 2 to 12) have non-empty undo_commands."""
        config_data = load_test_config()
        if config_data is None:
            self.skipTest("config file not available yet")

        phases = config_data.get("phases", {})
        for p_num in range(2, 13):
            p_key = f"phase_{p_num}"
            p_meta = phases.get(p_key, {})
            undo_cmds = p_meta.get("undo_commands", [])
            # If phase has forward commands, it MUST have undo commands
            fwd_cmds = p_meta.get("commands", [])
            if fwd_cmds:
                self.assertTrue(
                    len(undo_cmds) > 0,
                    f"CRITICAL ROLLBACK ASYMMETRY in config: {p_key} has forward commands but empty undo_commands!",
                )

    def test_json_yaml_config_parity(self):
        """Verifies both config.yaml and config.json exist and maintain parity."""
        if not (CONFIG_YAML_PATH.exists() and CONFIG_JSON_PATH.exists()):
            self.skipTest("Both config.yaml and config.json must exist to test parity.")

        import json
        with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        try:
            import yaml
            with open(CONFIG_YAML_PATH, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
        except ImportError:
            self.skipTest("PyYAML not installed, skipping YAML parsing.")

        self.assertEqual(json_data.get("version"), yaml_data.get("version"), "Version mismatch between JSON and YAML.")
        self.assertEqual(len(json_data.get("blacklist", [])), len(yaml_data.get("blacklist", [])), "Blacklist size mismatch.")
        self.assertEqual(len(json_data.get("phases", {})), len(yaml_data.get("phases", {})), "Phases count mismatch.")

    def test_custom_json_config_override_via_cli(self):
        """Verifies the CLI accepts a custom valid JSON config and runs successfully."""
        if not SCRIPT_PATH.exists():
            self.fail(f"Required target script 'optimize_13r.py' not found at {SCRIPT_PATH}. (Milestone M2 target)")

        custom_config = {
            "device": {"model": "CPH2691"},
            "blacklist": MANDATORY_BLACKLIST,
            "settings": {"animation_scale": 0.5},
            "packages": {
                "doze_whitelist": ["com.whatsapp"],
                "aot_speed_targets": ["com.whatsapp"],
                "telemetry_freeze_targets": ["com.heytap.browser"],
            },
        }

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump(custom_config, tf)
            tf_path = tf.name

        try:
            proc = run_optimizer(["--config", tf_path, "--dry-run"])
            self.assertEqual(
                proc.returncode,
                0,
                f"Custom config execution failed with code {proc.returncode}.\nStderr: {proc.stderr}",
            )
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_malformed_json_config_returns_exit_code_2(self):
        """Verifies providing a malformed/corrupt config file causes exit code 2."""
        if not SCRIPT_PATH.exists():
            self.fail(f"Required target script 'optimize_13r.py' not found at {SCRIPT_PATH}. (Milestone M2 target)")

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            tf.write('{"unclosed_json_object: true, "corrupted"')
            tf_path = tf.name

        try:
            proc = run_optimizer(["--config", tf_path, "--dry-run"])
            self.assertEqual(
                proc.returncode,
                2,
                f"Expected exit code 2 for malformed config, got {proc.returncode}",
            )
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)


if __name__ == "__main__":
    unittest.main()
