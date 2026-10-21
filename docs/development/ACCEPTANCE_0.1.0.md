# Version 0.1.0 acceptance evidence

The entire functional scope is implemented together on `codex/0.1.0`. The original
assignment file is unchanged. The owner's supplied functional concept governs
metadata-only RC/Stable channels and explicit initial Production absence; its staged
roadmap was superseded by the single-assignment request.

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
| Central status | Read/write contract, size bound, ownership, serialization and explicit absent bootstrap; failure to invalidate registry prevents filesystem mutation |
| Promotion eligibility and execution | Strict local verification/status preflight, no dispatch on failure, shared Actions checks, dispatched identity preserved through later installation, no rebuild and idempotent metadata PATCH |
| Production channel | Stable-only >=1.0.0 filtering; 0.x Production setup blocked; stale/unknown/equal-version Production blocks promotion |
| Emergency override | Owner + triggering actor + explicit confirmation, manual dispatch, shared immutable/integrity/version checks; Production safety preserved |
| Uninstall and self-update | Managed domain removal/retained backup, active uninstall completion after restart, explicit reconfirmation after unmanaged files, manager adoption and installed/running self-update transitions |
| Dashboard and authorization | Real native panel registration, HTTP delivery of module/logo, real admin/non-admin WebSocket requests, pushed status subscription |
| CI and security | One validation job, all five validation areas, docs-only successful path, pinned actions, hashed locks, Bandit and dependency audit |

Ruff lint/format, Node syntax, deterministic package/branding/translation/ruleset
contracts, actionlint 1.7.12 and the dependency audit are also run locally.
Actionlint's downloaded binary was verified against its official release checksum.
The complete locked pip installation was exercised. 23 owner-approved upstream
advisories remain explicitly reported and expire on **4 November 2026**; see
[Security](../wiki/Security.md). No verification or assertions were disabled to pass.

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
- The owner configures the documented minimal App permissions, installation access,
  Actions identity variables and private-key secret. No such settings are modified
  by this assignment. Workflows requiring the default branch cannot run from this
  unmerged development branch.
- Browser/mobile behavior, custom-integration global Settings banners and full HA OS
  crash/power-loss recovery are not established by Python fixture/HTTP tests.
- Wiki-ready English Markdown is included in the PR; no draft technical documentation
  is published to an independent Wiki before implementation review.
- Import `docs/github/main-ruleset.json` manually only after reconciling the existing
  provisional ruleset and confirming the exact `CI / Validation` check name.

These are remaining live acceptance steps, not claims of completed external tests.
The implementation PR must remain open and unmerged for owner review.
