"""
tests/test_diagnostics_command.py — Verification of RAT doctor diagnostic checks.
"""
from __future__ import annotations

import pytest

from rat.os.diagnostics import collect_system_diagnostics


def test_collect_system_diagnostics_schema():
    report = collect_system_diagnostics()

    assert "timestamp" in report
    assert report["overall_status"] in ("PASS", "WARN", "FAIL")
    assert report["exit_code"] in (0, 1)

    checks = report["checks"]
    assert "environment" in checks
    assert "database" in checks
    assert "configuration" in checks
    assert "models" in checks
    assert "permissions" in checks

    env = checks["environment"]
    assert env["status"] in ("PASS", "WARN", "FAIL")
    assert "python_version" in env["details"]

    db = checks["database"]
    assert db["status"] in ("PASS", "WARN", "FAIL")
    assert "path" in db["details"]


def test_diagnostics_cli_execution():
    from rat.cli import cmd_doctor

    code = cmd_doctor(as_json=True)
    assert code in (0, 1)
