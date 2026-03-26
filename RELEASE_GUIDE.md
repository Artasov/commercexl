# Release Guide

## Local checks

```bash
python -m pytest -q
python -m build
python -m twine check dist/*
```

## Release flow

1. Bump `src/commercexl/_version.py`.
2. Commit and push code.
3. Create and push a release tag like `v0.1.0`.
4. GitHub Actions will:
   - run tests
   - build the package
   - publish to PyPI

## PyPI publishing

The workflow is configured for trusted publishing with `pypi` environment.
Configure that environment in GitHub before the first release.
