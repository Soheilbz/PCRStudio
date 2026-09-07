# pcrstudio-tools

The Python worker. It exists for one reason: `primer3-py` is the complete,
maintained binding to Primer3, and Primer3 is what every published primer
design pipeline uses to generate candidates.

## What is in here

- `pcr_tools` — the design worker. Intake, reaction presets, the Primer3
  search, candidate diversification, the two-layer specificity scan, the
  ranking, and the account of what was checked.
- `pcr_accessibility` — template folding, in a package of its own. See the
  boundary below for why it is not part of `pcr_tools`.

## The licence boundary

`primer3-py` is GPLv2. Code that imports it is a derivative work; code that
runs it as a separate process and reads its output is not. So:

- **This directory is GPL-2.0-or-later.** It is the only place that imports
  `primer3`.
- **The Rust crates and the web interface stay MIT.** They invoke this worker
  as a subprocess and parse its JSON.

Keeping that line intact is why the worker talks over stdin and stdout rather
than being linked in.

There is a second line, for the same reason and in the opposite direction.
ViennaRNA -- which is what can say whether a template is folded shut where a
primer has to bind -- ships under terms that forbid redistribution for a fee
and ask commercial products to contact the authors. Those are conditions the
GPL does not allow to be added to a work it covers, so a single process
importing both Primer3 and ViennaRNA would be a combined work nobody could
distribute cleanly.

Two programs talking over a pipe are not a combined work. So:

- **`pcr_accessibility` imports ViennaRNA and never imports Primer3.**
- **`pcr_tools` imports Primer3 and never imports ViennaRNA**; it runs the
  other package as a subprocess and reads its JSON.

It is optional: `pip install pcrstudio-tools[folding]`. Without it a design
still runs and the result says the folding check did not happen, rather than
leaving the section out and letting its absence read as "nothing to report".

## Running it

```bash
uv sync --project tools --frozen
echo '{"sequences": ["GTAAAACGACGGCCAGT"]}' | uv run --project tools python -m pcr_tools thermo
```

Each command reads one JSON object on stdin and writes one on stdout. Failures
come back as `{"error": {"kind": "...", "detail": "..."}}` with a non-zero exit
code, so the caller never has to parse prose.

## What lives here, and what does not

Here: candidate generation, and the thermodynamics that Primer3 already
computes as part of it.

Not here: the melting temperature shown while someone types. That is answered
in Rust, in-process, because a subprocess per keystroke is the wrong shape.
