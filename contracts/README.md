# Scientific execution seam — version 1

This directory is a platform integration contract, not a scientific engine. No primer method, patient model, engine catalogue or scientific dependency is inherited from the prototype.

`execution-request.schema.json` defines the neutral versioned request. A capability publishes its own input/output JSON Schemas and finite resource bounds. Only local schema references are supported at this boundary; publishing a schema must not trigger arbitrary network retrieval. The platform validates and freezes the actual input and immutable artifact references before admission.

Requests contain run/attempt identifiers and job-scoped input, never browser cookies, user identities, billing details or unrestricted database credentials. Authentication and artifact URLs are transport concerns and must be scoped to the current active job attempt. The platform owns permission, reservation, cancellation, retries and settlement; the executor owns scientific validation/computation/provenance.

`snapshot.py` demonstrates immutable canonical JSON input and a digest covering capability identity, file versions and resource bounds. Nested mutable caller objects cannot alter an admitted snapshot. This is not the job admission/ledger implementation.

Tests use two deliberately different synthetic capability schemas and an isolated echo mock labelled simulation. The API runtime never imports this mock, and no UI presents it as a scientific result. Future execution acceptance must also verify current-attempt fencing, output schemas, finalized file existence and atomic success/settlement in PostgreSQL.
