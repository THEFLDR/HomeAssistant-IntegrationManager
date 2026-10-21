# Managed repositories and packages

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

`downloaded → pending_restart → verifying → active`, or `error`. Atomic filesystem
replacement is the installed milestone before pending restart, never activation.
One retained backup and a recovery journal live under
`.storage/integration_manager_files/`. Only the registered domain directory changes.
The next installation replaces the previous retained backup; maintain HA backups too.

Uninstall requires `uninstall <domain>`, moves managed files to backup and removes
registration. HA config entries, devices, entities, automations and user data remain.
Their config entry titles are displayed. Still-running code is reported until restart;
file removal is never proof that the old code has stopped.
