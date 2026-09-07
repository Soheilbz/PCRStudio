"""Shared Loop Set/LAMP error types.

Kept in a dependency-light module so profile selection and the main search
engine can report the same public error class without an import cycle.
"""
from __future__ import annotations


class LoopSetError(ValueError):
    """A loop-mediated design that could not be asked for."""
