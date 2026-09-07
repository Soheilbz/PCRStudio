# Generation-1 toolchain policy

Pinned production identities: Primer3 core 2.6.1 / primer3-py 2.3.0, MFEprimer 4.5.1,
NCBI BLAST+ 2.17.0, MAFFT 7.526, PrimerPooler 1.89, PrimalScheme3 3.3.0. ViennaRNA 2.7.2 and
pydna 5.5.16 remain optional specialized validators/simulators. Primer-BLAST and licensing-blocked
or remote-only tools are references rather than silent backend dependencies.

Tool role is engine-scoped. A tool identity is global; `PRIMARY`, `VALIDATOR`, `OPTIONAL`, etc. is
resolved for the engine/operation. Every external run records engine, module, operation, configured
version, executable hash, command, duration, exit status and stdout/stderr digests.

Coordinates inside PCRStudio are zero-based half-open `[start,end)`. Oligo sequences are always
reported 5′→3′ and strand is separate metadata. Adapters must convert upstream coordinate systems at
the boundary and must not leak mixed conventions downstream.
