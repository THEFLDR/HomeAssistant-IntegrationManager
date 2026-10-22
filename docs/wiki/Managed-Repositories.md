# Managed repositories and packages

GitHub owner/repository identifiers are normalized to lowercase at configuration,
registration and release boundaries, including restored HA state. Promotion treats
only repository spelling as case-insensitive; release IDs, tags, commits, asset IDs
and hashes must still match exactly.

Each approved repository maps to one integration domain. Register `owner/repository`,
the HA domain and explicit code approval in the panel. A published immutable release
must implement the package contract. Existing files require explicit exact-match
adoption, including the manager's first manual bootstrap installation.

## Assets and identity

The canonical tag is `vMAJOR.MINOR.PATCH`. Channel is only GitHub's `prerelease`
boolean; there are no `-rc` suffixes. Attach `integration.zip` and `integration.json`
to the draft before publishing. The JSON contract is:

```json
{
  "schema_version": 1,
  "domain": "example_integration",
  "version": "0.1.0",
  "sha256": "<64 lowercase hexadecimal characters for integration.zip>",
  "size": 12345
}
```

ZIP contents are exclusively `custom_components/<domain>/...`, including
`manifest.json` and `__init__.py`. Manifest domain/version match registration,
tag and metadata. Dependencies use exact PyPI pins and are installed by HA during
normal integration initialization; no executable package installer is accepted.

GitHub's asset digest must agree with metadata and downloaded bytes. Authenticated
immutable metadata binds release ID, tag, commit, asset ID and SHA-256. Generated
source archives are not packages. Limits: 32 MiB compressed, 64 MiB expanded,
2,000 entries. Traversal, absolute paths, links, special files, duplicate paths,
encrypted entries and other domains are rejected. TLS verification stays enabled.

Packaging sorts files, fixes ZIP timestamps/permissions and excludes bytecode.
The approved image is unchanged in `brand/icon.png`, supported by HA custom
integrations since 2026.3, and the panel. The original root asset is retained.

## Lifecycle

`downloaded → installed → pending_restart → verifying → active`, or `error`. Atomic filesystem
replacement is the installed milestone before pending restart, never activation.
One retained backup and a recovery journal live under
`.storage/integration_manager_files/`. Only the registered domain directory changes.
The next installation replaces the previous retained backup; maintain HA backups too.

Uninstall requires `uninstall <domain>`, moves managed files to backup and removes
registration. HA config entries, devices, entities, automations and user data remain.
Their config entry titles are displayed. Still-running code is reported until restart;
file removal is never proof that the old code has stopped.

## Workflow installation

Workflows in the manager repository do not exist in other repositories automatically.
Before registering/releasing another integration, prepare its checkout on a development
branch with `custom_components/<domain>/manifest.json`, real unit/HA compatibility tests
and its own **hashed `requirements-dev.lock`**. Include compatible Python 3.14.8 tools
and `pip-audit` in that lock. Do not copy the manager's dependency exception policy.

In the Integration Manager checkout, create a reviewed JSON file of that project's
CI commands, for example (adapt paths and tests to the actual project):

```json
{
  "quality": "ruff check . && ruff format --check .",
  "tests": "pytest tests/unit tests/homeassistant",
  "package": "python -m compileall -q custom_components/example_integration",
  "security": "bandit -r custom_components scripts && pip-audit -r requirements-dev.lock --require-hashes --no-deps --disable-pip"
}
```

Then run using this checkout's development environment (PyYAML is already locked):

```sh
.venv/bin/python -m scripts.prepare_managed_repository /path/to/other-repository \
  --domain example_integration --commands /path/to/reviewed-ci-commands.json
```

The helper creates the four named workflows, `scripts/release.py`, the five shared
release modules under `scripts/im_release/` and `requirements-release.lock`. It
sets the publish source to the requested domain and preserves exact-commit CI,
lightweight docs-only PRs, immutable packaging, metadata-only promotion and owner-only
override. Package validation and auditing the release helper's hashed dependencies
are appended to the supplied commands. Project tests must actually include HA setup;
step labels cannot establish test quality. No placeholder tests are generated.

Existing destination files stop preparation before any writes. For an existing CI
or release setup, generate into a temporary copy and reconcile changes in a reviewed
PR, preserving the stable workflow path, job/step names, dispatch `expected_sha` input
and all validation categories. Vendor updates explicitly through subsequent PRs;
there is no mutable remote-code download. Run the generated full CI and review all
files before merging to that repository's default branch.

The owner then verifies Actions is enabled, immutable releases are enabled, and the
App installation includes **both** the target repository and central registry.
Configure the documented App identity variables/key secret in each target repository;
its promotion reader needs Variables read on the central registry. HA needs Contents
read and Actions write on the target, Variables write on the registry. Installation
permissions are not per-repository grants, so selected repositories must all be trusted.
Only owner configuration is allowed; the helper never changes remote settings.

Run that repository's `Release - Publish` to produce its first RC before registering
it in HA. HA registration validates the release package; it does not install remote
workflow code. Promotion checks the target's active `promote.yml`, then dispatches
there with the fixed central registry and exact version/identity. Missing secrets,
insufficient grants and unsupported workflow inputs remain concrete workflow/API errors.
Verify a live publish → Sandbox install/restart/health → promotion for each repository.
