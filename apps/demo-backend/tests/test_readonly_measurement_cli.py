"""Exercise the measurement-only opt-in guard without connecting to CAD."""
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize('option', ['-AllowMissingReferencesForMeasurement', '-CaptureSingleModule'])
def test_measurement_opt_in_cannot_be_used_for_cad_acceptance(tmp_path, option):
    executable = shutil.which("powershell.exe")
    if not executable:
        pytest.skip("Windows PowerShell unavailable")
    root = Path(__file__).resolve().parents[3]
    report = tmp_path / "must-not-exist.json"
    result = subprocess.run(
        [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(root / "scripts/verify_p000_support_demo_state.ps1"),
         "-AssemblyPath", str(tmp_path / "absent.SLDASM"),
         "-ReportPath", str(report), option],
        capture_output=True, timeout=20,
    )
    assert result.returncode != 0
    assert b"only available for measurement" in result.stderr
    assert not report.exists()
