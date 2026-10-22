# Release channels and promotion

Every release starts as an immutable RC: `vMAJOR.MINOR.PATCH`, `prerelease=true`.
Stable is that same release with `prerelease=false`; there is no different package
or version number. Sandbox offers only RCs, Production only Stable >=1.0.0. An RC
already installed on Sandbox remains installed after promotion without reinstallation.

## Publish

`Release - Publish` is a manual default-branch workflow. It requires the exact current
commit to have a successful full `CI / Validation`, verifies the exact CI workflow
and completed Quality/Tests/Security steps, builds once, creates a draft, uploads
both assets, validates their GitHub digests and publishes the RC. It then verifies
immutability, tag commit and package hash. Existing tags are never reused; a broken
version requires a new PATCH version. A failed draft upload stays a draft for owner
inspection, never a falsely successful release.

CI has no push-on-main trigger. Publishing first reuses successful **full** validation
for its exact commit. If CI for that SHA is already running, it waits. Otherwise it
automatically dispatches the same `CI - Validation` workflow once on the default
branch, passing `expected_sha`, and waits up to 20 minutes. This covers the new SHA
created by a squash merge. A PR-head check or docs-only green check cannot authorize
publication. Manual/dispatch CI always runs all five areas; docs-only PRs retain their
lightweight green path. No second full run occurs when exact full evidence exists.

The CI checkout must match `expected_sha`; a branch advance before or during the
wait aborts publication. Publishing rechecks exact current-branch identity and full
CI evidence before creating a draft. Failed/cancelled CI or a timeout creates no
release; inspect the CI run before retrying. `Release - Publish` needs Actions write
to dispatch CI; dispatched validation itself has only Contents read, no App secret.
GitHub explicitly permits `workflow_dispatch` events using `GITHUB_TOKEN` to start
another workflow. All workflow files must already be on the default branch.

## Normal promotion from Sandbox

The target repository must first have its own installed workflow bundle and
configured registry credentials; see [managed setup](Managed-Repositories.md#workflow-installation).
HA checks that its `promote.yml` is active before dispatch; missing/disabled workflows
produce an actionable error. This check cannot prove secrets are correctly configured.

The owner selects **Promote to Stable** for the installed RC in HA. The backend
refreshes activation/registry health and reads fresh status and release metadata.
Preflight verifies local files and requires a successful status publication under
the operation lock. Any verification or registry failure prevents dispatch; cached
healthy status cannot substitute for a failed preflight.
The workflow independently revalidates:

- Exact repository, release ID, tag, commit, asset ID, version and SHA-256.
- Immutable published package and matching manifest, metadata and GitHub digest.
- Sandbox installed and running version, completed restart, active state, healthy
  observation for that exact release, and current registry/health timestamps.
- Below **1.0.0**, Production status is neither required nor read: these releases
  are Sandbox-only. Missing Production status needs no confirmation.
- From **1.0.0**, Production version is older, or a fresh, explicit owner-confirmed
  `not_installed` record exists. Missing, stale or inconsistent Production state blocks.

For promotion of **1.0.0 or later**, before the first Production installation, use
**Confirm initial Production absence**
and type the requested domain-specific confirmation. This never overwrites an active
Production instance record. Bootstrap confirmation expires with status freshness;
the owner may explicitly reconfirm absence before another promotion. No Production
installation is needed to test the 0.x promotion workflow.

The only release mutation is PATCH of `prerelease=false` and `make_latest=true`.
GitHub explicitly allows changing prerelease/latest flags on immutable releases;
its locked assets and tag are untouched. Both workflows serialize on release ID.
Repetition validates the same release and does not rebuild or publish a second one.
The script re-downloads and verifies the final identity/hash after promotion.

HA correlates the request with `promote-<request-id>`, displays the audited workflow
URL and verifies the final release independently. A failed run or unconfirmed result
is reported as failure/unknown outcome, never assumed successful. Inspect the audit
run and check release metadata after a timeout before requesting another attempt.
The dispatched release identity is persisted with the request. Installing another
version while a workflow runs does not change which release its result verifies.

## Emergency owner override

`Release - Override` is separate, `workflow_dispatch` only, and absent from HA's
action list. Only **THEFLDR**, as both actor and triggering actor, may authorize it.
Explicit version, domain, release ID, SHA-256 and the exact confirmation
`THEFLDR authorizes promotion of v<version>` are required. Authorization is checked
before mutation and again in the shared promotion implementation.

It bypasses Sandbox install/activation/health eligibility only. Production version
safety, canonical version, immutable release, manifest/domain and all identity/digest
checks still apply. From 1.0.0 it still needs fresh Production status or an explicit
initial absence record, readable through the scoped registry token. The same Sandbox-only
Production exemption applies below 1.0.0; immutable identity and integrity checks
are always mandatory. Audit output identifies override, actors, run ID, release
identity and final result.

The owner approved this platform limitation: GitHub does not reliably distinguish
`workflow_dispatch` initiated through UI, CLI or API. Therefore owner identity and
explicit authorization are enforced; UI-only provenance cannot be guaranteed.

Source: [GitHub immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases),
verified 21 October 2026. The supported documentation contract is not a substitute
for an owner-controlled live release test after merge.
