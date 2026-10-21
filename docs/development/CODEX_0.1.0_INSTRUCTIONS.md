# Integration Manager — Codex Implementation Assignment v0.1.0

## Scope and authority
Implement the complete functioning Home Assistant custom integration **Integration Manager**, version **0.1.0**, in `THEFLDR/HomeAssistant-IntegrationManager`, branch `codex/0.1.0`. This is one end-to-end assignment, not staged artificial releases. The owner's functional description is the primary requirements source; request it if unavailable, and flag any unresolved conflict rather than guessing. Prefer minimal, maintainable, native Home Assistant implementations. All code, docs, comments and PR descriptions in English. Do not merge the implementation PR.

**Owner-only GitHub security configuration:** Never create, update, delete, import or weaken branch rulesets, branch protection, GitHub App permissions, or repository security settings. At the end, supply an importable proposed branch ruleset JSON file under `docs/github/`, for the owner to import manually. The existing provisional ruleset remains unchanged.

**PR naming:** Every PR title must be exactly `PR - <branch-name>`; the implementation PR is **`PR - codex/0.1.0`**. Use `codex/{version}` for subsequent development branches. Request Copilot review, address substantive findings, and leave the PR open for owner review.

## Branding and repository
The approved image `approved-icon.png` has already been merged into `main` from `thefldr/0.0.0` via PR #1. Integrate it into the Home Assistant integration's supported icon/branding mechanism, validating current HA conventions and retaining the original asset. Recheck current `main` and PR state before submission. Never write directly to `main`.

## Environments, versions and installation
There are exactly two HA OS environments: **Sandbox** (isolated Hetzner VM behind Cloudflare mTLS) and **Production** (local HA Yellow). Both have outbound HTTPS to GitHub; do not require inbound webhooks or direct HA-to-HA communication. Select environment in the HA configuration flow. Sandbox consumes GitHub prereleases / RCs; Production consumes Stable only. Versions use SemVer, starting at 0.1.0. All pre-1.0.0 releases are Sandbox-only for installation; lack of Production installation must not block RC→Stable promotion testing. Production rollout begins at 1.0.0 only after security review.

Every managed custom integration corresponds to a GitHub repository. Implement repository registration/approval, release discovery, installation, updates, uninstall, error recovery, accurate installed/running versions, and native HA update entities where appropriate. The manager must also be self-updatable. Respect HA reload/restart requirements: downloaded files do not imply activation, and health/success must not be declared before restart and verification when required.

Use integrity-verifiable version-specific release artifacts. RC→Stable must preserve exact package bytes, identity and hash; no rebuild on promotion. **GitHub immutable releases are enabled**: verify GitHub's actual constraints on changing prerelease status, and use only a supported mechanism. Do not disable immutability or pretend an unsupported promotion path works.

## GitHub App and permission boundaries
GitHub App name: `HA Integration Manager - Identity`; App ID `5415641`, Client ID `Iv23liAez6eOhxMbAFDk`, Installation ID `173871726`. These are nonsecret identifiers; accept installation-specific values through HA config rather than hardcoding them. Use GitHub App installation authentication with a private PEM key securely provided through HA, JWT and automatically refreshed short-lived installation tokens; **no OAuth Device Flow**. Never commit or log keys or tokens.

The owner has configured minimal permissions, including **Contents read-only** and no Administration/Rulesets rights. Check exact GitHub API permissions for status variable updates, workflow dispatch, and release promotion. Use a minimally privileged, functional separation between HA read access and GitHub Actions privileged release operations. If a necessary operation is blocked, communicate the precise API call, required permission and smallest owner-side permission change; the owner will resolve it during development. Do not quietly request broad Contents write or simulate success.

## Central status, health and promotion
Provide a durable GitHub-native status registry for both instances. Initial preference: GitHub Repository Variables `IM_STATUS_SANDBOX` and `IM_STATUS_PRODUCTION`, JSON keyed by managed integration with running/installed versions, health, timestamp, release identity and artifact hash. Verify variable API permissions, size limits, update behavior and concurrency; if unsuitable, propose the simplest viable GitHub-native alternative for owner approval. No new external service, database or server.

Define a standardized managed-integration health contract with `healthy`, `unhealthy` and `unknown`. Missing checks mean `unknown`, never healthy. Manager health must verify meaningful end-to-end functionality; no fabricated deep health checks for arbitrary integrations. Health must not transiently become unknown merely because an update check runs.

Sandbox dashboard promotion of a particular RC is permitted only after that exact version has been installed, activated (including required HA restart) and verified healthy, and when its version is newer than Production where applicable. During 0.x, missing Production state must not block testing promotion. Revalidate server-side through GitHub Actions; never trust only dashboard button eligibility. Report auditable promotion outcome and failures.

Include a distinct emergency owner override GitHub Actions workflow, triggered **only manually via `workflow_dispatch` in GitHub UI**, with explicit version and owner authorization. It may bypass Sandbox install/health eligibility, but **never** release identity, immutability, version, integrity or other security validation. Do not expose override in HA. Verify actor/permissions and audit execution. If technically infeasible, report the blocker.

Check GitHub on HA startup, on explicit manual dashboard request, and automatically once per **24 hours** as fallback. Report status independently as appropriate without wasteful polling. No GitHub inbound webhooks.

## Home Assistant interface
Provide a dedicated Home Assistant dashboard or the closest actually supported native HA mechanism, transparently documenting limitations. Centralize repository registration, installation, updates, uninstall, health/version status per environment, promotion, manual checks, progress, restart-pending/verification and errors. Provide proper config and options flows, native update entities, and admin-only actions where supported. No brittle monkey-patching, unsupported HA internals or undocumented manual dashboard configuration. Separate future Cloudflare mTLS certificate management integration is **out of scope**.

## CI, versions and documentation
**Before implementing CI**, research and verify the **currently stable Home Assistant Core**, its supported **Python version**, and the current supported GitHub Actions major versions. Use compatible current versions and document the verification. Do not silently fall back to obsolete Python, Home Assistant, dependency or Actions versions; surface environmental limitations explicitly.

Keep CI efficient: lint/static analysis, focused unit/integration tests, release artifact and integrity validation, security-oriented checks. Skip heavy checks for docs-only changes, avoid duplicate triggers, cancel superseded runs, and perform one final comprehensive run on the final PR head before merge. CI must not need private HA instances or credentials. Do not create noisy workflows or burn unnecessary Actions minutes.

Write concise English documentation for architecture, setup, GitHub App permission matrix, configuration, release and immutable promotion flow, status schema, testing, troubleshooting, security assumptions and known limitations. GitHub Wiki is intended for technical docs; if direct Wiki publishing is unavailable, provide ready-to-publish Markdown in the repo.

After CI check names are finalized, prepare **an import-ready GitHub branch ruleset JSON file** under `docs/github/`, targeting `main` with PR integration, deletion/force-push protection, resolved conversations, appropriate required CI checks and a sole-owner-compatible review policy. Document import considerations and avoid overlapping/conflicting rules. **Do not apply or alter any ruleset.** Owner retains exclusive control.

Respect legitimate GitHub author/committer attribution; do not spoof security identities or signatures. Explain unavoidable platform limitations.


### Mandatory CI and workflow conventions (owner-approved)
Use the following stable naming conventions:
- Workflow `CI - Validation` in `.github/workflows/ci.yml`.
- Workflow `Release - Publish` in `.github/workflows/release.yml`.
- Workflow `Release - Promote` in `.github/workflows/promote.yml`.
- Workflow `Release - Override` in `.github/workflows/override.yml` (manual `workflow_dispatch` only).
- Exactly **one CI validation workflow with one job**, named **`CI / Validation`**, as the sole required CI status check for branch protection. Do not create three or five independent CI jobs merely to separate validation categories.
- Within this single job, execute clearly labeled steps grouped as **Quality**, **Tests**, and **Security**. Retain all five functional validation areas: lint/formatting, unit tests, Home Assistant compatibility, integration/package checks, and security/dependency checks. Do not reduce coverage merely to reduce job count.
- Install the Python environment and dependencies once per run, and reuse them across steps. Prefer a lean sequential pipeline; split jobs only if measured runtime or an actual technical requirement justifies it, and explain any deviation before implementation.
- Run CI on relevant pull requests; avoid duplicate full CI on `main` after a validated merge. Keep the required check green and present for docs-only PRs by executing a lightweight successful validation path instead of skipping the entire required workflow through path filters.
- Use concurrency cancellation for superseded PR runs; avoid redundant release-time reruns of full CI when the exact release commit has already passed validation.
- Workflow and job names must remain stable and match the proposed ruleset JSON exactly. Pull request titles must be `PR - <branch-name>`, e.g. `PR - codex/0.1.0`.
- Check current stable supported GitHub Actions majors, Python, HA Core and dependencies before pinning versions. Do not introduce deprecated versions; document verified compatibility.
- Keep publish, promote and emergency override responsibilities logically distinct, but reuse common implementation for promotion and override to avoid duplicate code.

## Required acceptance evidence
Demonstrate through tests: initial config and GitHub App authentication, repository registration, RC discovery and Sandbox install, update entity, accurate restart and health transitions, central status read/write, promotion eligibility and GitHub-side execution, Production Stable-only filtering, manual emergency override, artifact integrity, failure/recovery, uninstall, manager self-update, and no inbound webhook dependency. Clearly distinguish mocks from live HA/GitHub end-to-end tests; never claim untested external APIs or UI paths are verified.

Before PR submission, inspect current `main` and changed files, reconcile any divergence, run final applicable checks, request Copilot review, and provide a concise report of implementation, verification, risks and any exact owner actions required. **Leave PR `PR - codex/0.1.0` unmerged.**
