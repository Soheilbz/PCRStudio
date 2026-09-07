"""PCRStudio's isolated scientific worker package.

The public convenience names are loaded lazily. Foundation/contract tooling can
therefore inspect generated manifests, IPC envelopes, fingerprints and storage
contracts without importing GPL Primer3 thermodynamics as a side effect. The
first access to a scientific design/thermodynamic symbol still imports the same
implementation as before.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "CandidatePair",
    "Constraints",
    "DesignResult",
    "OligoReport",
    "SequenceError",
    "analyse",
    "design",
    "melting_temperature",
    "pair_dimer",
]

_DESIGN = {"CandidatePair", "Constraints", "DesignResult", "design"}
_THERMO = {"OligoReport", "SequenceError", "analyse", "melting_temperature", "pair_dimer"}


def __getattr__(name: str) -> Any:
    if name in _DESIGN:
        value = getattr(import_module(".design", __name__), name)
    elif name in _THERMO:
        value = getattr(import_module(".thermo", __name__), name)
    else:
        raise AttributeError(name)
    globals()[name] = value
    return value
