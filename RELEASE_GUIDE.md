# Release Guide

## Release gates

Before releasing `0.3.x`:

1. Confirm `src/commercexl/_version.py` and the README status table contain the intended version.
2. Run the targeted payment, module, contract and configuration tests.
3. Build both wheel and sdist and run `twine check` against them.
4. Inspect the wheel: it must contain `commercexl`, `py.typed`, README, license metadata and no test
   package, local secrets or generated migration files.
5. For `0.3.0`, verify the breaking migration guide and the absence of the 0.2 payment API in docs.
6. Open a PR into `master` and wait for CI. Do not publish from an unmerged feature branch.

Suggested local commands:

```bash
python -m pytest tests/test_runtime.py tests/test_module.py tests/test_payment_contracts.py tests/test_config.py -q
python -m build
python -m twine check dist/*
```

## Version bump helper

```bash
uv run python scripts/release.py patch --dry-run
uv run python scripts/release.py patch
```

PowerShell wrapper:

```powershell
./scripts/release.ps1 patch
```

The helper requires a clean worktree, changes `src/commercexl/_version.py`, creates the release
commit and tag, and optionally pushes them with `--push`. For the breaking `0.3.0` release, set and
review the version in the feature branch before the PR; do not run a second automatic minor bump.

## GitHub release flow

1. Merge the reviewed release PR into `master`.
2. Create and push the exact tag matching package metadata, for example `v0.3.0`.
3. The tag starts CI. Publishing stops if the strict `vX.Y.Z` tag does not match
   `commercexl.__version__`.
4. After the package build and PyPI Trusted Publishing succeed, the workflow creates the matching
   GitHub release. Existing PyPI artifacts are treated as an error rather than silently skipped.
5. Verify that the GitHub workflow and release succeeded and that
   [PyPI](https://pypi.org/project/commercexl/) exposes the expected wheel and sdist.
6. Install the published version in a clean environment and verify `commercexl.__version__`.

The GitHub `pypi` environment must have a Trusted Publisher for this repository and workflow.
Publishing uses an OIDC token; a long-lived PyPI API token must not be added as a fallback.

## @orcestr/commerce-ui release flow

The first `@orcestr/commerce-ui` release must be published manually from `frontend` with
`npm publish --workspace @orcestr/commerce-ui --access public`. Then configure its npm Trusted
Publisher with organization `Artasov`, repository `commercexl`, workflow `ci.yml`, and environment
`npm`. Later releases use an exact `commerce-ui-vX.Y.Z` tag; CI verifies the package version and
publishes with provenance.

## 0.3 compatibility note

Provider add-ons should depend on `commercexl>=0.3.1,<0.4`. Version 0.3.1 is the minimum safe
baseline for finalized-only providers because it permits a provisional `confirmed` payment to
expire before final settlement. During coordinated local development they may use an editable
checkout, but the committed lockfile must resolve a reproducible published artifact.
