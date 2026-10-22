# Installation and configuration

Use stable **HA Core 2026.10.2**, which requires **Python >=3.14.2**. Development and
CI use **Python 3.14.8**. HA OS manages Python itself; do not replace it inside HA OS.
Read [security](Security.md) for the temporary Sandbox-only upstream advisories.

## First Sandbox installation

1. After owner-approved merge, run `Release - Publish` on the default branch with
   `version: 0.1.0`. It automatically obtains full CI for the exact release commit
   if needed, including a new squash SHA; existing full evidence is reused. A
   failure, timeout or branch advance prevents publication. No separate CI dispatch
   is required.
2. The immutable RC contains `integration.zip` and `integration.json`. Check the package SHA-256
   against both metadata and the GitHub asset digest before extraction.
3. Copy `custom_components/integration_manager` from the package to HA's
   `custom_components` directory, keep an HA backup, and restart HA.
4. In **Settings → Devices & services → Add integration**, choose **Integration Manager**.
   Select **sandbox**; enter the App ID, Client ID, Installation ID, RSA private PEM
   key and registry `THEFLDR/HomeAssistant-IntegrationManager`. Identifiers are
   installation-specific configuration, never embedded authentication defaults.
5. The PEM key is stored atomically with `0600` permissions under
   `.storage/integration_manager_keys/`. Config entries contain only its path.
   Protect backups: permissions do not encrypt keys at rest.
6. Open **Integration Manager** in the sidebar. After RC discovery, choose **Verify
   and adopt existing files** for the manager. Every file must match the release.
   An arbitrary existing integration is never silently adopted or overwritten.
7. Startup checks, registry write, active version and self-checks must complete before
   manager health becomes healthy. Review all panel errors.

Before 1.0.0, Production setup and pre-1.0.0 Production package installation are
blocked. Testing a real 0.x promotion to Stable does not authorize Production use.
Production begins with a reviewed, explicitly installed Stable 1.0.0.

## Options and key rotation

Use **Settings → Devices & services → Integration Manager → Configure** for App ID,
Client ID, Installation ID and PEM rotation. A blank key retains the existing one.
New credentials authenticate before replacement. Saving reloads the connection;
that reload never activates downloaded code. Environment and registry remain fixed
to protect stored ownership and installation identities.

## Development tasks

Use the task's existing checkout and `.venv`. Cloud tasks are already isolated;
do not create a Git worktree unless the user asks. The test workflow needs no
continuously running server. A live HA development run must start its services
explicitly and does not replace the owner's Sandbox acceptance.
