# Docker storage policy

PCRStudio builds use a dedicated `docker-container` BuildKit builder named
`pcrstudio`, using the exact BuildKit image digest recorded by the bootstrap
and maintenance scripts. Its garbage collector keeps at most 8 GB of reconstructible
build cache. Production image identities remain exact digest pins; cache
collection cannot change an image digest, TLS verification, provenance, or the
OCI supply-chain gate.

The Linux bootstrap creates/selects this builder before the first expensive
build, prunes it before work starts, and prunes it again even when a build
fails. The same policy is available to maintainers:

```text
python3 scripts/docker-maintenance.py ensure
python3 scripts/docker-maintenance.py report
python3 scripts/docker-maintenance.py prune
```

The builder is selected for PCRStudio through `BUILDX_BUILDER` and is not made
the host-wide default, so another project sharing the Docker daemon keeps its
own builder selection.

The maintenance command deliberately does not run `docker system prune` and
does not remove images belonging to other projects. Only dangling images that
carry PCRStudio's `org.pcrstudio.product=PCRStudio` lifecycle label are
eligible for image cleanup. Old unlabelled images must be reviewed by their
owning project before removal.

CI uses ephemeral runners and runs a final bounded BuildKit prune so a failed
qualification cannot leave a large cache on a reused runner. Cloud hosts
should invoke the repository bootstrap/maintenance path from the same release
checkout rather than using ad-hoc daemon-wide pruning.
