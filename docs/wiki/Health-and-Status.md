# Health and central status

The central registry is `IM_STATUS_SANDBOX` and `IM_STATUS_PRODUCTION` in the manager
repository. They are nonsecret JSON documents. Never store tokens, PEM keys,
certificate data or private network addresses in them.

```json
{
  "schema_version": 1,
  "environment": "sandbox",
  "instance_id": "<random instance identity>",
  "updated_at": "2026-10-21T12:00:00+00:00",
  "integrations": {
    "example_integration": {
      "repository": "owner/repository",
      "installed_version": "0.1.0",
      "running_version": "0.1.0",
      "state": "active",
      "health": "healthy",
      "health_at": "2026-10-21T12:00:00+00:00",
      "health_release_id": 123,
      "restart_pending": false,
      "updated_at": "2026-10-21T12:00:00+00:00",
      "release": {
        "repository": "owner/repository",
        "release_id": 123,
        "tag": "v0.1.0",
        "version": "0.1.0",
        "commit": "<40 hexadecimal characters>",
        "asset_id": 456,
        "sha256": "<64 hexadecimal characters>"
      }
    }
  }
}
```

Status is written after relevant state changes and hourly as a heartbeat, separately
from daily release discovery. A whole-document write cannot race a newer local
operation because all operations are serialized. Another live writer/HA clone is not
supported: Variables do not provide atomic conditional updates. Each environment
owns its document. Sandbox may create/refresh an explicitly authorized initial
Production absence record only while no Production instance owns that document.
Once Production owns its registry, confirm a new registered integration's absence
on Production itself. That action checks installed files and loaded code first;
a subsequent unexpected local installation invalidates the absence confirmation.
An explicitly requested uninstall completes its absence transition only after both
files and loaded code are gone. Unexpected unmanaged files revoke that authorization;
removing them does not silently restore confirmation. Production administrators can
reconfirm verified absence in the panel's **Removed integrations** section, without
registering or reinstalling the integration. Registered unmanaged integrations also
return to an unconfirmed `not_installed` state after their files/code are removed.

For promotion, registry documents, Production integration records and health are
fresh for **two hours**, with at most 60 seconds future-clock tolerance. An unrelated
integration's heartbeat cannot freshen an old bootstrap record. Missing, inconsistent
or stale state is unknown and blocks normal promotion. `not_installed` requires
explicit owner confirmation, no running version and no restart still pending.

## Managed integration health contract

After actual HA activation, a managed integration calls the native service
`integration_manager.report_health` from trusted integration code (or an HA admin):

```yaml
action: integration_manager.report_health
data:
  domain: example_integration
  health: healthy
  reported_version: "0.1.0"
  release_id: 123
  sha256: "<64 lowercase hexadecimal characters>"
```

Report `healthy` or `unhealthy` after actual integration-specific checks, on changes
and at least hourly. Read the active manager entity's release attributes to obtain
identity, and only report for the version actually running. The manager verifies
loaded manifest version, completed restart, installed file fingerprints and matching
release ID/hash. Health for an old version is rejected. No report, expired report,
failed mapping or unconfigured integration means `unknown`, never healthy. Reports
do not survive a process restart as fresh evidence. HA-internal callers are trusted;
this contract is not a sandbox for hostile integration code.

## Manager self-health

The manager checks usable native storage and interfaces, GitHub App authentication,
registry read/write and required permissions, release discovery errors, loaded versus
installed identity, and local file consistency. Its own bootstrap state is unknown
until exact release adoption establishes provenance. Pending restart cannot be
healthy. The health claim is the defined non-destructive contract, not proof that a
future filesystem mutation or remote workflow will succeed. No health check installs,
uninstalls, restarts HA or promotes a release as a probe.

`checking` is a separate operation indicator. A routine release check does not blank
previous valid health; expiry, real failures and activation changes do. Arbitrary
managed integrations supply their own meaningful health checks; the manager never
fabricates device, Cloudflare or cloud-service health.
