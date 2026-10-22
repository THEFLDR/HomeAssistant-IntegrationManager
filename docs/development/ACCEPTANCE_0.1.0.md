# Version 0.1.0 acceptance evidence

The entire functional scope is implemented together on `codex/0.1.0`. The owner
maintains the assignment file; the latest review-budget update is incorporated.
The owner's supplied functional concept governs
metadata-only RC/Stable channels; its staged roadmap was superseded by the
single-assignment request. The 22 October owner review explicitly removes Production
confirmation for Sandbox-only 0.x promotion; Production protection begins at 1.0.0.

## Automated evidence

The focused suite runs under real HA Core **2026.10.2** and Python **3.14.8**.
GitHub transport and remote state are mocked; local HA framework setup is real.
The PR records the final test count and check result.

| Acceptance requirement | Evidence |
| --- | --- |
| Config flow, private key, options and App JWT | Native flow initialization, private key permissions, rotation, JWT claims and single-flight token refresh |
| Registration/approval and RC selection | Repository/domain approval, package contract, multiple eligible versions, newest/default and explicit selection |
| Install, update, integrity, failure/recovery | Hash/path/link/special-file rejection, domain isolation, atomic replace, retained backup identity through failed replacement, interrupted move and post-swap state reconciliation |
| Native update entity | Real platform/entity initialization, installed/running attributes, real panel WebSocket install with native progress state, and non-admin rejection |
| Restart and health | Full-process boot gate, loaded version, exact identity, stale/old/unknown report rejection, health preserved through checks |
| Central status | Read/write contract, size bound, ownership and explicit absent bootstrap; verified atomic local commits, cancellation/unload serialization, and no filesystem mutation after persistence/registry failure |
| Promotion eligibility and execution | Strict local verification/status preflight, no dispatch on failure, shared Actions checks, dispatched identity preserved through later installation, no rebuild and idempotent metadata PATCH |
| Production channel | Stable-only >=1.0.0 filtering; 0.x Production setup blocked; missing Production permitted below 1.0.0; stale/unknown/equal-version Production blocks promotion from 1.0.0 |
| Emergency override | Owner + triggering actor + explicit confirmation, manual dispatch, shared immutable/integrity/version checks; Production safety preserved |
| Uninstall and self-update | Managed domain removal/retained backup, active uninstall completion after restart, explicit reconfirmation after unmanaged files, manager adoption and installed/running self-update transitions |
| Dashboard and authorization | Real native panel registration, HTTP delivery of module/logo, real admin/non-admin WebSocket requests, pushed status subscription |
| Exact release-commit CI | Squash/new SHA dispatches full CI once; exact full evidence reused, existing run awaited, docs-only evidence rejected, branch advance/failure/timeout block release mutation |
| Multi-repository workflows | Generated foreign-repository bundle packages independently without HA, mocked publish then promotion use its vendored code; missing/disabled promote workflow blocks HA dispatch; missing inputs/lock and existing files stop preparation |
| CI and security | One validation job, all five validation areas, docs-only successful path, pinned actions, hashed locks, Bandit and dependency audit |

Ruff lint/format, Node syntax, deterministic package/branding/translation/ruleset
contracts, actionlint 1.7.12 and the dependency audit are also run locally.
Actionlint's downloaded binary was verified against its official release checksum.
The complete locked pip installation was exercised. 25 owner-approved upstream
advisories remain explicitly reported and expire on **4 November 2026**; see
[Security](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Security).
No verification or assertions were disabled to pass.

## Live boundaries and owner actions

- GitHub repository metadata, native Git access and current main/branch tips were
  checked. The current provisional ruleset is active and was not changed.
- Reading the immutable-release setting returned **403 Resource not accessible by
  integration** for `GET /repos/THEFLDR/HomeAssistant-IntegrationManager/immutable-releases`.
  That administrative read needs Administration read; no broader permission was
  requested. The owner's stated enabled setting is a prerequisite. Every published
  release is independently required to return `immutable: true` before acceptance.
- The owner's HA App private key and two HA OS instances are not available to this
  test process. Actual App installation access, live download/install/restart,
  real integration-specific health, actual immutable promotion and self-update
  recovery must be exercised on Sandbox after owner review/merge and RC publication.
- On each managed repository, review and merge the generated workflow bundle and
  its real project CI commands/tests. Confirm its own RC publish and promotion,
  central registry App access, enabled Actions and immutable release behavior.
  The helper changes local files only; no foreign repository has been configured
  or live-released by this assignment.
- After merge, exercise a squash-SHA publish: automatic dispatch of exact full CI,
  successful publication, failure rejection and reuse of existing full evidence.
  This cross-workflow path cannot execute from this unmerged default-branch-only PR.
- The owner configures the documented minimal App permissions, installation access,
  Actions identity variables and private-key secret. No such settings are modified
  by this assignment. Workflows requiring the default branch cannot run from this
  unmerged development branch.
- Browser/mobile behavior, custom-integration global Settings banners and full HA OS
  crash/power-loss recovery are not established by Python fixture/HTTP tests.
- English technical documentation is published in the
  [native GitHub Wiki](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki).
  The [migration report](WIKI_MIGRATION_REPORT.md) records publication and readback
  verification; development and repository-specific engineering records remain here.
- Import `docs/github/main-ruleset.json` manually only after reconciling the existing
  provisional ruleset and confirming the exact `CI / Validation` check name.

These are remaining live acceptance steps, not claims of completed external tests.
The implementation PR must remain open and unmerged for owner review.

All 15 actionable findings from the three completed Copilot reviews are addressed.
The owner-approved review-budget policy prohibits further requests for 0.1.0.
Final Codex self-review and CI cover the latest changes; independent ChatGPT/owner
review remains. Copilot availability is not a required branch check.
