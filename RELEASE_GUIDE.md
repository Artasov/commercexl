# Release Guide

## Local checks

```bash
python -m pytest -q
python -m build
python -m twine check dist/*
```

## Version bump helper

Базовая команда:

```bash
uv run python scripts/release.py patch
```

Или через PowerShell-обёртку:

```powershell
./scripts/release.ps1 patch
```

Доступные варианты:

```bash
uv run python scripts/release.py patch
uv run python scripts/release.py minor
uv run python scripts/release.py major
```

Полезные флаги:

```bash
uv run python scripts/release.py patch --dry-run
uv run python scripts/release.py patch --push
```

Что делает скрипт:

1. Проверяет, что git worktree чистый.
2. Поднимает версию в `src/commercexl/_version.py`.
3. Создаёт commit `chore: release vX.Y.Z`.
4. Создаёт tag `vX.Y.Z`.
5. При `--push` пушит commit и tag.

## Release flow

1. Прогони локальные проверки.
2. Подними версию через `scripts/release.py`.
3. Если запуск был без `--push`, отдельно выполни:

```bash
git push
git push origin vX.Y.Z
```

4. GitHub Actions:
   - прогонит тесты
   - соберёт пакет
   - опубликует его в PyPI

## PyPI publishing

The workflow is configured for trusted publishing with `pypi` environment.
Configure that environment in GitHub before the first release.
