"""
tests.test_cli_smoke — End-to-end smoke tests for CLI entry points.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_smoke_cli_doctor_json():
    """Verify `python main.py doctor --json` executes and returns valid JSON telemetry."""
    cmd = [sys.executable, "main.py", "doctor", "--json"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, f"doctor --json failed: {proc.stderr}"
    data = json.loads(proc.stdout)
    assert "overall_status" in data
    assert "checks" in data
    assert "environment" in data["checks"]
    assert "database" in data["checks"]


def test_smoke_cli_help():
    """Verify `python main.py --help` outputs usage cleanly."""
    cmd = [sys.executable, "main.py", "--help"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0
    assert "usage:" in proc.stdout.lower() or "options:" in proc.stdout.lower()


def test_smoke_cli_init_shell():
    """Verify `python main.py init-shell` outputs valid shell functions."""
    cmd = [sys.executable, "main.py", "init-shell"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0
    assert "rat()" in proc.stdout


def test_smoke_cli_quick_math():
    """Verify `python main.py 15+25` resolves via AST calculate without starting GUI."""
    cmd = [sys.executable, "main.py", "15+25"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0
    assert "40" in proc.stdout


def test_smoke_cli_room_lookup():
    """Verify `python main.py B203` resolves room location without starting GUI."""
    cmd = [sys.executable, "main.py", "B203"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0
    assert "B203" in proc.stdout
