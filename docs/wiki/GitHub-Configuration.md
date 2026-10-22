# GitHub App and workflow configuration

App permissions, branch rules and repository security settings belong exclusively
to the owner. No integration or release script changes them.

| Actor / operation | Endpoint | Minimum permission |
| --- | --- | --- |
| HA release discovery and assets | `GET /repos/{owner}/{repo}/releases`, `/releases/{id}`, `/releases/assets/{id}` | Contents: read |
| HA immutable tag commit | `GET /repos/{owner}/{repo}/commits/{tag}` | Contents: read |
| HA registry read | `GET /repos/{owner}/{repo}/actions/variables/{name}` | Variables: read |
| HA registry create/update | `POST /repos/{owner}/{repo}/actions/variables`, `PATCH .../{name}` | Variables: write |
| HA promotion request | `POST /repos/{owner}/{repo}/actions/workflows/promote.yml/dispatches` | Actions: write |
| HA promotion audit | `GET /repos/{owner}/{repo}/actions/workflows/promote.yml/runs` | Actions: read (included in write) |
| Publish workflow | Draft, assets, publication; commit checks and validation steps | `GITHUB_TOKEN`: Contents write, Checks read, Actions write (automatic exact-commit CI dispatch) |
| Promote/override workflow | `PATCH /repos/{owner}/{repo}/releases/{id}` | `GITHUB_TOKEN`: Contents write |
| Workflow registry reader | Central registry variable GET | Downscoped installation token: Variables read only |

Metadata read is automatic. No Administration, Rulesets or OAuth Device Flow rights
are requested. Contents write stays in each managed repository's Actions token,
never the HA App token. GitHub may require Workflows write when a release's resolved
commit changes workflow files relative to the default branch. Publishing uses the
exact current default-branch commit and never silently requests that broader right.
Remote 403/404 failures remain visible.

If the existing App has only Contents read, the smallest owner-side change is
**Variables: read/write** for registry operations and **Actions: read/write** for
dispatch/audit. GitHub App permissions are installation-wide, not independently
assignable per repository within an installation. Restrict selected repositories,
or use a separate registry identity if tighter isolation is needed. Do not add
Contents write to HA to solve promotion access.

## Workflow placement and secrets

Each managed repository must install its own reviewed release workflows, CI and
`scripts/release.py` with vendored shared modules using the
[local preparation procedure](Managed-Repositories.md#workflow-installation).
These files must be merged onto that repository's default branch before dispatch.
A repository's `GITHUB_TOKEN` writes only its own releases;
this avoids a central cross-repository Contents-write credential. The central status
repository remains `THEFLDR/HomeAssistant-IntegrationManager`. The preparation
command sets the publish source to that integration's domain.

The owner provides Actions variables **`IM_CLIENT_ID`** (or **`IM_APP_ID`**) and
**`IM_INSTALLATION_ID`**, and secret **`IM_APP_PRIVATE_KEY`** in each repository requiring
promotion. The shared JWT helper explicitly requests a short-lived token scoped to
the registry repository with only `actions_variables: read`, and
revokes it after use. The current official App-token action v3 does not declare a
Variables permission input, so no unsupported input or inherited write privilege is used.
The private key can itself mint broader tokens allowed by its
App: every repository receiving the secret must be trusted. No untrusted PR CI
receives that secret. Registry routing is pinned in reviewed workflow code; HA also
requires explicit repository approval and the registry owner's namespace.

Immutable releases must already be enabled by the owner. The post-publication GET
must return `immutable: true`; no fallback weakens immutability.

## Verified API contract, 21 October 2026

Use REST API version `2026-03-10`. Variables read/write and Actions write are distinct
permissions. The Variables permission's API key is **`actions_variables`**, not
`variables`. HA explicitly requests Contents read, Actions write and Variables write
when minting its installation token. Variables are limited to **48 KB**; PATCH replaces the entire JSON value,
without a documented transaction or compare-and-swap. Exactly one writer per environment
and a serialized local lock are required. Registry GETs are uncached; release discovery
uses ETags, bounded pagination and bounded GET retries. Mutations are not retried
after ambiguous transport failures.

Sources: [variables API](https://docs.github.com/en/rest/actions/variables),
[App permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps),
[dispatch](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event),
[release API](https://docs.github.com/en/rest/releases/releases),
[limits](https://docs.github.com/en/actions/reference/workflows-and-actions/variables).
Documentation verification does not establish live access for the owner's App key.

## Permission verification and live acceptance, 22 October 2026

Rechecked GitHub's published REST documentation data for API `2026-03-10`:
[official Actions endpoint data](https://github.com/github/docs/blob/5815d11586b0796688963a98c889680e60d72dc4/src/rest/data/fpt-2026-03-10/actions.json),
`progAccess.permissions` for Get/Create/Update a repository variable and Create a
workflow dispatch event. Repository Variables GET requires **Variables read**;
POST/PATCH require **Variables write**, not Actions write or Administration.
Dispatch requires **Actions write**; workflow lookup/audit requires Actions read.
These operations support GitHub App installation tokens. Metadata read is implicit.
The workflow registry-reader token requests no Contents permission because it only
reads Variables. HA combines Contents read, Variables write and Actions write for
its separate release/status/dispatch responsibilities.

`GITHUB_TOKEN` cannot express Variables permission; use the downscoped App token
for central reads. Publish uses its local `GITHUB_TOKEN` Actions write for CI dispatch,
Checks read for evidence, and Contents write for its own release. CI receives only
Contents read. A `workflow_dispatch` generated by `GITHUB_TOKEN` can start CI:
[GitHub's documented exception](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow#triggering-a-workflow-from-a-workflow).

Still requires live owner acceptance: minting the configured App installation token
with these exact permissions; registry GET/POST/PATCH and token revocation; dispatch
and audit in every selected managed repository; publish-to-CI dispatch and exact-SHA
reuse after merge; and immutable RC publication/promotion. Mocked API tests verify
request scopes and rejection behavior, not the owner's effective installation grant.
A 403 needs review of that endpoint's permission; 404 may mean missing default-branch
workflow, installation repository access, or hidden/inaccessible resource. A disabled
workflow is reported separately. No settings are changed automatically.
