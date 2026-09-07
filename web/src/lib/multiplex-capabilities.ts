import capabilityContract from "./multiplex-capabilities.generated.json";

type CapabilityRecord = {
  engine: string;
  kind: string;
  pooling: string;
  primary_selection: string;
  software_target_bound: number | null;
  status: string;
};

const capabilities = capabilityContract.modules as Record<string, CapabilityRecord>;

/**
 * The catalogue's generic modifier is intentionally narrower than the full
 * multiplex contract. Some assays have a dedicated panel editor or a pooled
 * workflow rather than the shared endpoint-PCR builder. Keeping that
 * distinction here prevents the module page from offering a route the API
 * cannot execute, while still making every reviewed multiplex capability
 * visible to somebody choosing an assay.
 */
const genericBuilderModules = new Set(["standard-pcr", "colony-pcr", "species-specific-pcr"]);

export type MultiplexCapability = CapabilityRecord & {
  moduleId: string;
  genericBuilder: boolean;
  title: string;
  description: string;
  boundLabel: string | null;
};

export function multiplexCapabilityFor(moduleId: string): MultiplexCapability | null {
  const record = capabilities[moduleId];
  if (!record) return null;

  const genericBuilder = genericBuilderModules.has(moduleId);
  const boundLabel = record.software_target_bound
    ? `Planning bound: up to ${record.software_target_bound} targets`
    : null;

  if (genericBuilder) {
    return {
      ...record,
      moduleId,
      genericBuilder,
      title: "Multiplex design",
      description:
        "Design several targets for one reaction. The complete set is checked for oligo interactions, product specificity and shared reaction context rather than ranking each pair in isolation.",
      boundLabel,
    };
  }

  const copy: Record<string, { title: string; description: string }> = {
    "qpcr-probe": {
      title: "Multiplex panel planning",
      description:
        "Add peer assays in the main design form. Reporters, channels and the primer–probe interaction matrix are checked together; measured efficiency and LoD still come from assay validation.",
    },
    "digital-pcr": {
      title: "Digital multiplex planning",
      description:
        "Choose a platform and channel or amplitude architecture in the design form. PCRStudio records the optical plan, while thresholds, rain and cluster calls remain evidence from the digital-PCR run.",
    },
    lamp: {
      title: "Specialised multiplex planning",
      description:
        "The design form supports an evidence-bound modified-primer or probe topology. It does not invent LAMP multiplex chemistry or claim target-specific signal without the named method and empirical evidence.",
    },
    rpa: {
      title: "RPA multiplex planning",
      description:
        "The design form can record a low-plex candidate panel and its evidence. Final RPA selection remains an empirical screen because conventional PCR Tm does not predict RPA performance.",
    },
    "tiled-scheme": {
      title: "Pooled amplicon design",
      description:
        "This workflow already distributes overlapping amplicons across pools. Review coverage, pool interactions, variant risk and the exact upstream scheme workflow before ordering a panel.",
    },
  };
  const selected = copy[moduleId] ?? {
    title: "Multiplex capability",
    description:
      "This assay has a reviewed multiplex capability with assay-specific rules. Configure it in the design form and review the evidence boundary before ordering.",
  };

  return { ...record, moduleId, genericBuilder, ...selected, boundLabel };
}
