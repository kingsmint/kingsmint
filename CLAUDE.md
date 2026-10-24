# kingsmint

The engine of a kingsmint ledger: the `kingsmint` Python package (`src/kingsmint/`: the importer, the parsers in
`banks/<country>/<bank>.py`, ECB rates), the Claude Code plugin (`skills/`, `.claude-plugin/`), and `template/`, which
`/kingsmint:setup` copies into a new ledger repository. Users' ledgers depend on this package and run it in
their own directory (`ROOT = Path.cwd()`).

- This repository is public. Personal data (IBANs, names, amounts, real statements) never goes into
  code, tests, examples, or commit messages; tests use synthetic values.
- `uv run --group dev pytest` must pass. A parser change is verified by importing real statements in a
  ledger that uses this checkout, where every statement must reconcile, and the output must be unchanged
  for the statements that worked before.
- Skills follow the writing rules for agent documents: steps with a clear end condition, reference only
  where a branch needs it.
