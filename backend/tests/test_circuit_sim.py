import math
import re
import shutil
import subprocess

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from lab.app import app
from lab import circuit_sim
from lab.circuit_sim import EngineUnavailable, RcProject, simulate_rc


def test_rc_project_rejects_excessive_time_constant():
    with pytest.raises(ValidationError):
        RcProject(resistance_ohms=100_000, capacitance_farads=1e-6)


@pytest.mark.skipif(shutil.which("ngspice") is None, reason="ngspice natif absent")
def test_ngspice_rc_transient_matches_analytic_time_constant():
    result = simulate_rc(RcProject(resistance_ohms=1_000, capacitance_farads=1e-6))
    assert result["engine"] == "ngspice"
    assert result["expected_tau_seconds"] == pytest.approx(1e-3)
    assert result["measured_tau_seconds"] == pytest.approx(1e-3, rel=0.01)
    assert result["cutoff_hz"] == pytest.approx(159.154943, rel=1e-6)
    assert result["raw_points"] >= 100
    assert result["display_points"] <= 513
    assert len(result["signals"]["vout"]) == result["display_points"]
    assert all(math.isfinite(value) for value in result["signals"]["vout"])


@pytest.mark.skipif(shutil.which("ngspice") is None, reason="ngspice natif absent")
def test_ngspice_voltage_divider_reference_is_2_5_volts(tmp_path):
    netlist = tmp_path / "divider.cir"
    netlist.write_text("""Divider reference
V1 vin 0 DC 5
R1 vin vout 1k
R2 vout 0 1k
.control
op
print v(vout)
quit
.endc
.end
""", encoding="ascii")
    result = subprocess.run([shutil.which("ngspice"), "-b", str(netlist)], cwd=tmp_path,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, timeout=5, check=True)
    match = re.search(r"v\(vout\)\s*=\s*([+-]?[0-9.eE+-]+)", result.stdout)
    assert match, result.stdout
    assert float(match.group(1)) == pytest.approx(2.5, abs=1e-9)


def test_circuit_simulation_api_returns_real_scope_trace():
    client = TestClient(app)
    response = client.post("/api/circuit/simulate", json={
        "schema_version": 1,
        "name": "RC test",
        "resistance_ohms": 1_000,
        "capacitance_farads": 1e-6,
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["analysis"] == "transient"
    assert data["measured_tau_seconds"] == pytest.approx(1e-3, rel=0.01)
    assert data["engine_version"] != "inconnue"


def test_circuit_simulation_rejects_unknown_netlist_fields():
    client = TestClient(app)
    response = client.post("/api/circuit/simulate", json={"netlist": "shell command"})
    assert response.status_code == 422


def test_circuit_simulation_reports_missing_engine_without_trace(monkeypatch):
    def unavailable():
        raise EngineUnavailable("Moteur ngspice indisponible sur ce serveur.")
    monkeypatch.setattr(circuit_sim, "_binary", unavailable)
    response = TestClient(app).post("/api/circuit/simulate", json={"schema_version": 1})
    assert response.status_code == 503
    assert "ngspice indisponible" in response.json()["detail"]


@pytest.mark.skipif(shutil.which("ngspice") is None, reason="ngspice natif absent")
def test_small_time_constant_stays_within_point_budget():
    result = simulate_rc(RcProject(resistance_ohms=100, capacitance_farads=1e-9))
    assert result["expected_tau_seconds"] == pytest.approx(1e-7)
    assert result["measured_tau_seconds"] == pytest.approx(1e-7, rel=0.03)
    assert result["raw_points"] < 20_000
