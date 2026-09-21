# Contributing

The public example is the completed corrected-mirror compactness case.

- Keep configurations explicit, including units and signed fields.
- Run tests with `python -m unittest discover -s tests -v`.
- Keep raw simulation outputs under ignored `runs/` and temporary plots under
  ignored `results/local/`.
- Separate changes to the physical model from changes to packaging or display.
- Compare compactness measurements against the included corrected-case snapshots
  after changes to readers or integration.
- State when a change alters a diagnostic definition or a scientific result.
- Update figure recipes and provenance when replacing corrected-case assets.

The CPU checks require no GPU. A simulation change should additionally pass a
short WarpX run using a new output directory. Expensive refinement studies
are separate from routine code checks.

Release preparation still needs the owner's choice of code license.
Do not infer a license for third-party publications from the code.
