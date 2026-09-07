"""Template folding, kept in a process of its own.

This is a separate program on purpose, and the reason is licensing rather than
architecture. `pcr_tools` imports Primer3, which is GPLv2. ViennaRNA ships
under its own terms, which forbid redistribution for a fee and ask that
commercial products contact the authors -- conditions the GPL does not permit
to be added to a work it covers. Importing both into one process would make a
combined work nobody could distribute cleanly.

Two programs that talk over a pipe are not a combined work. So this one imports
ViennaRNA and never imports Primer3, `pcr_tools` imports Primer3 and never
imports ViennaRNA, and each keeps its own terms.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
