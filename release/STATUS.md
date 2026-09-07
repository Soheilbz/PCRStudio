# PCRStudio CURRENT public-source status

**Disposition:** Linux-native, unified-engine, architecture-hardened public source. Source/static qualification is required to be green before packaging; native Rust/Web/Docker/scientific execution remains an explicit target-host/CI gate and is never inferred from source inspection.

All 21 public design modules remain computationally `experimental` unless separate bench evidence supports promotion. The active engine registry contains exactly 11 engines and every engine is represented through the same profile, authority, capability, transport-parity and differential-contract framework.

Production uses PostgreSQL-backed durable jobs, a dedicated `pcr-runner`, one-shot `pcr-migrate`, Linux process-group cleanup, immutable scientific tooling in the runner/API image, file-backed secrets, strict scientific readiness and one-command host bootstrap.
