#!/usr/bin/env python3
"""
Test Helpers and Utilities for OnePlus 13R Optimizer Test Suite.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"
SCRIPT_PATH = PROJECT_ROOT / "optimize_13r.py"
CONFIG_YAML_PATH = PROJECT_ROOT / "config.yaml"
CONFIG_JSON_PATH = PROJECT_ROOT / "config.json"

MOCK_ADB_PY = TESTS_DIR / "mock_adb.py"
MOCK_ADB_CMD = TESTS_DIR / "mock_adb.cmd"
MOCK_ADB_BAT = TESTS_DIR / "mock_adb.bat"


def get_mock_adb_executable() -> str:
    """Returns path to the mock ADB executable on current platform."""
    if sys.platform == "win32":
        if MOCK_ADB_CMD.exists():
            return str(MOCK_ADB_CMD)
        return str(MOCK_ADB_BAT)
    return str(MOCK_ADB_PY)


def run_optimizer(
    args: List[str],
    use_mock_adb: bool = False,
    mock_env: Optional[Dict[str, str]] = None,
    timeout: float = 15.0,
    cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    """
    Executes the optimize_13r.py CLI script with specified arguments.
    Raises FileNotFoundError if optimize_13r.py does not exist.
    """
    if not SCRIPT_PATH.exists():
        raise FileNotFoundError(
            f"Target script 'optimize_13r.py' not found at {SCRIPT_PATH}. "
            "The implementation milestone (M2) has not yet created the script."
        )

    cmd = [sys.executable, str(SCRIPT_PATH)]

    # If mock ADB requested, prepend or supply --adb-path if not already in args
    has_adb_flag = any(a.startswith("--adb-path") for a in args)
    if use_mock_adb and not has_adb_flag:
        cmd.extend(["--adb-path", get_mock_adb_executable()])

    cmd.extend(args)

    env = dict(os.environ)
    if mock_env:
        env.update(mock_env)

    # Disable python buffer for immediate capture
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.run(
        cmd,
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return proc


def load_test_config() -> Optional[Dict[str, Any]]:
    """Loads config.json or config.yaml from project root if available."""
    if CONFIG_JSON_PATH.exists():
        try:
            with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    if CONFIG_YAML_PATH.exists():
        try:
            import yaml
            with open(CONFIG_YAML_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception:
            pass

    return None
