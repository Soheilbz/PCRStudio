import type { ReactNode } from "react";

/** Small definition-list fact used across result views. */
export function ResultFact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-foreground">{value}</dd>
    </div>
  );
}

type ProvenanceLike = {
  primer3_py: string;
  tool_versions?: { libprimer3?: string | null } | null;
  model: { name: string };
  worker: string;
  python: string;
  platform: string;
  note?: string | null;
  scientific_authorities?: Array<{
    authority_id: string;
    authority_revision: string;
    canonical_source: string;
    canonical_sha256: string;
  }> | null;
  method_fidelity?: Array<{
    method_id: string;
    display_name: string;
    grade: string;
    decision_impact: string;
    scientific_strict_eligible: boolean;
    claim_boundary: string;
    use_role?: string;
  }> | null;
  method_fidelity_references?: Array<{ method_id: string }> | null;
  method_fidelity_registry?: { registry_id: string; canonical_sha256: string } | null;
};

/** One wording contract for the common scientific runtime provenance sentence. */
export function RuntimeProvenance({
  provenance,
  children,
}: {
  provenance?: ProvenanceLike | null;
  children?: ReactNode;
}) {
  if (!provenance) return null;
  return (
    <p className="text-xs leading-relaxed text-muted-foreground">
      Computed by primer3-py {provenance.primer3_py} (libprimer3{" "}
      {provenance.tool_versions?.libprimer3 ?? "not reported"}) under {provenance.model.name},
      worker {provenance.worker}, on Python {provenance.python} ({provenance.platform}).{" "}
      {provenance.note}
      {provenance.scientific_authorities?.length ? (
        <>
          {" "}
          Scientific authority set:{" "}
          {provenance.scientific_authorities
            .map(
              (row) =>
                `${row.authority_id}@${row.authority_revision}#${row.canonical_sha256.slice(0, 12)}`,
            )
            .join(", ")}
          .
        </>
      ) : null}
      {provenance.method_fidelity?.length ? (
        <>
          {" "}
          Active method fidelity:{" "}
          {provenance.method_fidelity
            .map(
              (row) =>
                `${row.method_id}=${row.grade} [${row.use_role}]${row.scientific_strict_eligible ? "" : " (not Scientific-Strict primary)"}`,
            )
            .join(", ")}
          .{" "}
          {provenance.method_fidelity_references?.length
            ? `Related external/reference authorities: ${provenance.method_fidelity_references.map((row) => row.method_id).join(", ")}. `
            : ""}
          Registry{" "}
          {provenance.method_fidelity_registry?.canonical_sha256?.slice(0, 12) ?? "unreported"}.
        </>
      ) : null}
      {children ? <> {children}</> : null}
    </p>
  );
}
