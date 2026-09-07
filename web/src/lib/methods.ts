/**
 * What the numbers are computed with, and where those methods come from.
 *
 * A primer design tool asks people to trust figures they cannot check by eye —
 * a melting temperature is the output of a model, not a measurement, and two
 * respectable models disagree on the same oligo by more than a protocol has
 * room for. Naming the model is the difference between a number somebody can
 * verify and a number they have to take on faith.
 *
 * Every reference here was checked against PubMed rather than written from
 * memory, which is the only defensible way to put a DOI on a page whose whole
 * purpose is that the reader can go and look.
 */

export interface Method {
  /** What it does here, in the words of somebody at a bench. */
  what: string;
  /** The software, where a piece of software is doing it. */
  software?: { name: string; url: string };
  /** The published method behind it. */
  paper: {
    authors: string;
    year: number;
    title: string;
    journal: string;
    where: string;
    doi: string;
  };
}

export const METHODS: Method[] = [
  {
    what: "Every melting temperature on every screen, and the salt correction applied to it. Fixed rather than configurable: a result that does not say which model produced it is not a result anyone can check.",
    paper: {
      authors: "SantaLucia J",
      year: 1998,
      title:
        "A unified view of polymer, dumbbell, and oligonucleotide DNA nearest-neighbor thermodynamics",
      journal: "Proceedings of the National Academy of Sciences",
      where: "95(4):1460–1465",
      doi: "10.1073/pnas.95.4.1460",
    },
  },
  {
    what: "Finding the candidate primers, and measuring hairpins, self-dimers and cross-dimers between them.",
    software: { name: "Primer3", url: "https://primer3.org" },
    paper: {
      authors: "Untergasser A, Cutcutache I, Koressaar T, Ye J, Faircloth BC, Remm M, Rozen SG",
      year: 2012,
      title: "Primer3 — new capabilities and interfaces",
      journal: "Nucleic Acids Research",
      where: "40(15):e115",
      doi: "10.1093/nar/gks596",
    },
  },
  {
    what: "Whether the template is actually open where a primer has to bind — a site folded into a stable hairpin is a site a primer has to compete with.",
    software: { name: "ViennaRNA", url: "https://www.tbi.univie.ac.at/RNA/" },
    paper: {
      authors:
        "Lorenz R, Bernhart SH, Höner zu Siederdissen C, Tafer H, Flamm C, Stadler PF, Hofacker IL",
      year: 2011,
      title: "ViennaRNA Package 2.0",
      journal: "Algorithms for Molecular Biology",
      where: "6:26",
      doi: "10.1186/1748-7188-6-26",
    },
  },
];
