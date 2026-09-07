// Generated from contracts/modules.toml and contracts/engines.toml; do not hand-edit.
export const ENGINE_IDS = ["flanking-pair", "pair-and-probe", "nested", "loop-set", "discriminating-pair", "single-primer", "outward-pair", "consensus-pair", "tiling-scheme", "junction-primers", "mutagenic-pair"] as const;

export type EngineId = (typeof ENGINE_IDS)[number];

export const MODULE_BINDINGS = {
  "arms-pcr": {
    "command": "discriminate",
    "engine": "discriminating-pair",
    "resourceWeight": 2
  },
  "colony-pcr": {
    "command": "run",
    "engine": "flanking-pair",
    "resourceWeight": 2
  },
  "digital-pcr": {
    "command": "run",
    "engine": "flanking-pair",
    "resourceWeight": 2
  },
  "gibson-assembly": {
    "command": "junction",
    "engine": "junction-primers",
    "resourceWeight": 2
  },
  "inverse-pcr": {
    "command": "inverse",
    "engine": "outward-pair",
    "resourceWeight": 2
  },
  "kasp": {
    "command": "discriminate",
    "engine": "discriminating-pair",
    "resourceWeight": 2
  },
  "lamp": {
    "command": "loop_set",
    "engine": "loop-set",
    "resourceWeight": 4
  },
  "long-range-pcr": {
    "command": "run",
    "engine": "flanking-pair",
    "resourceWeight": 2
  },
  "nested-pcr": {
    "command": "nested",
    "engine": "nested",
    "resourceWeight": 3
  },
  "qpcr-probe": {
    "command": "probe",
    "engine": "pair-and-probe",
    "resourceWeight": 3
  },
  "qpcr-sybr": {
    "command": "run",
    "engine": "flanking-pair",
    "resourceWeight": 2
  },
  "race": {
    "command": "single",
    "engine": "single-primer",
    "resourceWeight": 1
  },
  "restriction-cloning": {
    "command": "run",
    "engine": "flanking-pair",
    "resourceWeight": 2
  },
  "rpa": {
    "command": "run",
    "engine": "flanking-pair",
    "resourceWeight": 2
  },
  "sequencing-primer": {
    "command": "single",
    "engine": "single-primer",
    "resourceWeight": 1
  },
  "site-directed-mutagenesis": {
    "command": "mutagenic",
    "engine": "mutagenic-pair",
    "resourceWeight": 2
  },
  "species-specific-pcr": {
    "command": "run",
    "engine": "flanking-pair",
    "resourceWeight": 2
  },
  "standard-pcr": {
    "command": "run",
    "engine": "flanking-pair",
    "resourceWeight": 2
  },
  "tetra-primer-arms": {
    "command": "discriminate",
    "engine": "discriminating-pair",
    "resourceWeight": 2
  },
  "tiled-scheme": {
    "command": "tiling",
    "engine": "tiling-scheme",
    "resourceWeight": 4
  },
  "universal-primers": {
    "command": "universal",
    "engine": "consensus-pair",
    "resourceWeight": 4
  }
} as const;

export type ModuleId = keyof typeof MODULE_BINDINGS;
export type EngineFor<M extends ModuleId> = (typeof MODULE_BINDINGS)[M]["engine"];
