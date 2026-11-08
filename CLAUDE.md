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
- `main` may hold unreleased changes, under `## Unreleased` in the CHANGELOG. Users install the plugin from the
  tag in `.claude-plugin/marketplace.json` (`ref`), and ledgers pin kingsmint to the tag of the plugin's version,
  so skills and package always come from the same tag. A release is one commit on `main`: the version in
  `pyproject.toml`, `.claude-plugin/plugin.json`, `desktop/manifest.json`, the CHANGELOG heading and `uv.lock`, and
  `ref` set to `v<version>`. Then tag that commit `v<version>` and push the tag; the release workflow checks both.
- A commit message says what changed in the first line, and in the body why: the problem, what the user
  reported, what was tested. `src/kingsmint/CHANGELOG.md` gets a line for each change a user notices; a change to `template/` also gets
  a line under `### Ledger`, saying what to change in an existing ledger and why.
- Skills follow the writing rules for agent documents: steps with a clear end condition, reference only
  where a branch needs it.
