# Development and compatibility

Verified against public PyPI metadata and official repository documentation on
**21 October 2026**, before implementing CI:

| Component | Selected stable compatible version |
| --- | --- |
| Home Assistant Core | 2026.10.2, requires Python >=3.14.2 |
| Python | 3.14.8 |
| HA custom-integration pytest fixtures | 0.13.373, pins Core 2026.10.2 and pytest 9.0.3 |
| HA frontend | 20260930.4, exact requirement of Core's frontend manifest |
| PyJWT / cryptography | Core's compatible pins 2.15.1 / 50.0.1; no additional runtime package |
| Ruff / Bandit / pip-audit | 0.17.1 / 1.9.4 / 2.10.1 |
| actions/checkout | v7, pinned commit |
| actions/setup-python | v7, pinned commit |
| actions/create-github-app-token | v3 researched; not used because it lacks a declared Variables permission input |

Newer cryptography or pytest releases are not substituted over exact Core/fixture
requirements. `requirements-dev.lock` pins all transitive packages with hashes.
Install once and reuse the environment across all checks:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/ruff check .
.venv/bin/ruff format --check .
node --check custom_components/integration_manager/frontend/panel.js
.venv/bin/pytest --cov=custom_components.integration_manager --cov=scripts --cov-report=term-missing
.venv/bin/python scripts/check_repository.py
.venv/bin/bandit -q -r custom_components scripts -c pyproject.toml
.venv/bin/python scripts/audit_dependencies.py
```

In the managed cloud workspace, point writable caches at `/workspace/.cache` if the
home directory is read-only (`XDG_CACHE_HOME=/workspace/.cache`). Do not replace HOME.
Use the existing isolated checkout; no Git worktree is needed.

## CI contract

Exactly one workflow **`CI - Validation`**, `.github/workflows/ci.yml`, has exactly
one job/check named **`CI / Validation`**. Quality steps cover Ruff lint/format and
JavaScript syntax. Tests cover focused unit/integration tests, real HA Core
initialization, WebSocket authorization and native entity setup, plus deterministic
release package/integrity checks. Security covers Bandit and every locked dependency,
with only the explicitly approved expiring upstream exceptions.

Pull requests trigger CI, superseded runs cancel, dependencies install once and use
pip cache. Both validation paths select the supported Python version. Docs-only PRs
keep the required check present/green with lightweight JSON, branding, translation
and ruleset contract checks, skipping dependency installation and full tests. PR title
edits also trigger validation. No push-on-main duplicate or release-time automatic full rerun exists.
Manual CI is available to establish evidence for an exact new release commit SHA.
All PR titles must be `PR - <branch-name>`.

The three distinct release workflows use shared promotion code. No release is
published, promoted, merged or deployed by running local tests. GitHub calls are
mocked in automated tests; live App permissions and HA OS behavior require the
acceptance procedure. Wiki pages are ready-to-publish repository Markdown.

Sources: [Core metadata](https://pypi.org/pypi/homeassistant/2026.10.2/json),
[fixture metadata](https://pypi.org/pypi/pytest-homeassistant-custom-component/0.13.373/json),
[Core pyproject](https://github.com/home-assistant/core/blob/2026.10.2/pyproject.toml),
[local custom branding](https://developers.home-assistant.io/docs/core/integration/brand_images/),
[checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python),
[App tokens](https://github.com/actions/create-github-app-token).
