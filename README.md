# PCRStudio

PCRStudio is an evidence-first workspace for designing and checking PCR
primers. It helps researchers explore primer candidates, review their
properties, and keep each result tied to the method and evidence that produced
it.

## What it offers

- Primer design and checking across 21 computational design systems.
- Clear module pages with the inputs, outputs, method status, and known limits.
- Support for single-assay, multiplex, qPCR, and related PCR workflows where
  the required method and evidence are available.
- Projects and saved design runs for keeping work organised.
- A refusal when the requested chemistry or method cannot be represented
  honestly, instead of silently substituting a different calculation.

## Read results carefully

Every public module is currently marked **experimental**. This means that its
implementation is computationally testable; it does not mean that the output
has been validated at the bench. Results should be reviewed by a qualified
researcher and validated experimentally before ordering oligos or relying on
them in laboratory work.

PCRStudio does not claim to reproduce private vendor algorithms. Named tools
and methods are identified separately from compatible approximations and
external-authority-only workflows. For example, MGB-aware melting temperature
remains bound to matching external authority rather than being replaced with
an ordinary-DNA estimate.

## Method fidelity

PCRStudio labels whether a result follows a named method exactly, follows a
public rule set, is a compatible approximation, or requires outside authority.
This helps you understand what a result means and when additional review is
needed.

## Try it locally

On a supported Linux system with Docker available:

```bash
./bootstrap.sh --local
```

The launcher prepares the local application, starts the required services, and
prints the address to open in a browser. It can be run again safely when the
local stack is already healthy.

## Current status

PCRStudio is an actively qualified source candidate. The computational
implementation, web interface, data contracts, and local production-shaped
workflow are covered by automated checks. Scientific and wet-lab validation
remain separate gates; passing software tests does not promote a module to
bench-validated status.

## Learn more

- [Release status and limitations](release/STATUS.md)
- [Security policy](SECURITY.md)
- [Contributor guide](CONTRIBUTING.md)
- [Development setup](docs/DEVELOPMENT.md)
- [Operations and deployment](docs/OPERATIONS.md)
- [Current release evidence](release/INDEX.md)

## License and responsible use

See [LICENSE](LICENSE) and [NOTICE](NOTICE) for the terms that apply to this
repository. Treat sequence data and generated results according to the
privacy, institutional, and regulatory requirements of your work.
