# Troubleshooting and recovery

| Observation | Action |
| --- | --- |
| GitHub HTTP 401 | Verify App/installation identity and rotate the PEM if necessary. Tokens refresh automatically. Never paste keys into logs/issues. |
| Variables HTTP 403/404 | Owner checks Variables read/write, installation repository selection, and the exact endpoint in the error. Do not add Contents write. |
| Dispatch HTTP 403/404 | Owner checks Actions write and that `promote.yml` exists on the managed default branch. Workflow files only activate after merge. |
| Package digest/path/domain failure | Do not install; inspect immutable assets and publish a new PATCH version. Never rewrite expected hashes or disable checks. |
| Existing unmanaged files | Use explicit verified adoption only if every file matches the authenticated release. Otherwise preserve/remove them manually with an HA backup first. |
| Pending restart after update | Restart the whole HA process. A config-entry reload is insufficient. Old running code is shown until activation. |
| Verifying / unknown health | Configure the integration normally, resolve HA setup/dependency errors, and supply a fresh version-bound health report. Missing checks never mean healthy. |
| Another instance owns registry | Stop the old instance/clone. Resolve identity ownership deliberately before replacement. Do not run simultaneous writers. |
| Promotion blocked by Production unknown | Confirm absence explicitly only for a real initial non-installation; otherwise restore fresh Production reporting. |
| Promotion timed out | Inspect audited workflow runs and GitHub release metadata. A timeout is not success; retry only after determining the outcome. |

## Recovery

An existing entry starts its local panel and cached state even while GitHub is
unavailable; the outage is shown as an error and blocks remote operations. Initial
configuration and credential rotation still require successful authentication.

The installer retains one previous domain directory in
`.storage/integration_manager_files/<domain>.backup`. **Restore retained backup**
requires `restore <domain>`, then a full HA restart and activation verification.
Journal recovery restores a moved old directory when an interrupted replacement
left no target. A hash disagreement stays an error; it is never inferred healthy.
The previous backup survives a failed replacement. Its release identity changes
only when the new target commits; a persisted pending transaction reconciles both
identities after a crash. Restore checks the retained files against that identity.

If the manager itself cannot start, stop HA and use the owner's HA terminal/backup
tools to preserve the failed `custom_components/integration_manager` directory and
restore its retained backup to that exact path. Restart HA, inspect the loaded
version, and restore/reconcile the matching private HA Store from an HA backup if
needed. Do not edit version/hash fields merely to clear an error. Preserve the App
key and config entries securely. Full HA restore is the final 0.x Sandbox recovery
path. Do not delete entities, automations or unrelated integrations.

The automated suite exercises atomic replacement, backup restore and an interrupted
move. Power-loss durability, full HA OS self-update recovery, mobile UI and a real
immutable GitHub promotion still need controlled Sandbox acceptance before claiming
live readiness. Production recovery must pass the pre-1.0.0 security gate.
