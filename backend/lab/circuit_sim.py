"""Small, typed adapter around the native ngspice transient solver.

Only a fixed RC step topology is accepted. A browser never submits SPICE text,
file paths, device models or commands.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, ConfigDict, model_validator


class EngineUnavailable(RuntimeError):
    """The native simulation engine is missing or misconfigured."""


class RcProject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = Field(default=1, ge=1, le=1)
    name: str = Field(default="RC · réponse à un échelon", min_length=1, max_length=80)
    resistance_ohms: float = Field(default=1_000, ge=100, le=100_000)
    capacitance_farads: float = Field(default=1e-6, ge=1e-9, le=1e-3)

    @model_validator(mode="after")
    def bounded_time_constant(self):
        value = self.resistance_ohms * self.capacitance_farads
        if not math.isfinite(value) or value > 0.05:
            raise ValueError("Constante de temps hors limite : R × C doit être ≤ 50 ms.")
        return self

    @property
    def tau(self) -> float:
        return self.resistance_ohms * self.capacitance_farads


def _binary() -> str:
    configured = os.environ.get("RESONANT_NGSPICE_BIN")
    result = configured or shutil.which("ngspice")
    if not result:
        raise EngineUnavailable("Moteur ngspice indisponible sur ce serveur.")
    path = Path(result).expanduser().resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise EngineUnavailable("Le chemin du moteur ngspice configuré est invalide.")
    return str(path)


@lru_cache(maxsize=4)
def _version(binary: str) -> str:
    try:
        result = subprocess.run([binary, "--version"], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", timeout=2,
                                check=False, env={"PATH": os.environ.get("PATH", "")})
        match = re.search(r"ngspice[- ](\d+(?:\.\d+)*)", result.stdout, re.IGNORECASE)
        return match.group(1) if match else "inconnue"
    except (OSError, subprocess.TimeoutExpired):
        return "inconnue"


def _make_netlist(project: RcProject, trace_path: str) -> str:
    r = project.resistance_ohms
    c = project.capacitance_farads
    tau = project.tau
    duration = 5 * tau
    max_step = min(tau / 50, duration / 500)
    rise_time = min(1e-9, tau / 1_000)
    # All names, topology and commands are fixed here. Only bounded numeric
    # values validated by RcProject are interpolated.
    return f"""Resonant Lab RC step response
V1 vin 0 PULSE(0 5 0 {rise_time:.12g} {rise_time:.12g} 1 2)
R1 vin vout {r:.12g}
C1 vout 0 {c:.12g} IC=0
.control
set wr_singlescale
set wr_vecnames
tran {max_step:.12g} {duration:.12g} uic
wrdata {trace_path} v(vin) v(vout)
quit
.endc
.end
"""


def _read_trace(path: Path) -> tuple[list[float], list[float], list[float]]:
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise RuntimeError("ngspice n’a pas produit une trace valide ou trop volumineuse.")
    times: list[float] = []
    vin: list[float] = []
    vout: list[float] = []
    with path.open("r", encoding="ascii") as stream:
        header = stream.readline().strip().lower().split()
        if header != ["time", "v(vin)", "v(vout)"]:
            raise RuntimeError("Format de trace ngspice inattendu.")
        for line in stream:
            fields = line.split()
            if len(fields) != 3:
                continue
            try:
                t, source, output = map(float, fields)
            except ValueError:
                continue
            if not all(math.isfinite(v) for v in (t, source, output)):
                raise RuntimeError("La simulation a produit une valeur non finie.")
            times.append(t)
            vin.append(source)
            vout.append(output)
            if len(times) > 20_000:
                raise RuntimeError("La simulation dépasse la limite de points autorisée.")
    if len(times) < 2:
        raise RuntimeError("La simulation n’a pas produit assez de points.")
    return times, vin, vout


def _sample(times: list[float], *signals: list[float], limit: int = 513):
    if len(times) <= limit:
        return times, signals
    indices = [round(i * (len(times) - 1) / (limit - 1)) for i in range(limit)]
    return ([times[i] for i in indices], tuple([signal[i] for i in indices] for signal in signals))


def simulate_rc(project: RcProject) -> dict:
    """Run a bounded transient simulation and return a decimated oscilloscope trace."""
    tau = project.tau
    binary = _binary()
    with tempfile.TemporaryDirectory(prefix="resonant-circuit-") as temp:
        root = Path(temp)
        netlist = root / "circuit.cir"
        trace = root / "trace.dat"
        netlist.write_text(_make_netlist(project, str(trace)), encoding="ascii")
        try:
            result = subprocess.run(
                [binary, "-b", str(netlist)],
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
                env={"PATH": os.environ.get("PATH", ""), "HOME": str(root), "TMPDIR": str(root), "LC_ALL": "C"},
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("La simulation ngspice a dépassé sa limite locale de 5 s.") from exc
        except OSError as exc:
            raise EngineUnavailable("Impossible de démarrer le moteur ngspice configuré.") from exc
        if result.returncode != 0:
            raise RuntimeError("ngspice n’a pas pu résoudre ce circuit.")
        times, vin, vout = _read_trace(trace)
    sample_times, (sample_vin, sample_vout) = _sample(times, vin, vout)
    threshold = 5 * (1 - math.exp(-1))
    measured_tau = None
    for index in range(1, len(times)):
        if vout[index - 1] < threshold <= vout[index]:
            dt = times[index] - times[index - 1]
            fraction = (threshold - vout[index - 1]) / max(vout[index] - vout[index - 1], 1e-30)
            measured_tau = times[index - 1] + fraction * dt
            break
    return {
        "engine": "ngspice",
        "engine_version": _version(binary),
        "analysis": "transient",
        "sample_rate_hz": None,
        "project": project.model_dump(),
        "expected_tau_seconds": tau,
        "measured_tau_seconds": measured_tau,
        "cutoff_hz": 1 / (2 * math.pi * tau),
        "time_seconds": sample_times,
        "signals": {"vin": sample_vin, "vout": sample_vout},
        "raw_points": len(times),
        "display_points": len(sample_times),
    }
