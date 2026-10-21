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
| Publish workflow | Draft, assets, publication; commit checks and validation steps | `GITHUB_TOKEN`: Contents write, Checks read, Actions read |
| Promote/override workflow | `PATCH /repos/{owner}/{repo}/releases/{id}` | `GITHUB_TOKEN`: Contents write |
| Workflow registry reader | Central registry variable GET | Downscoped installation token: Variables read, Contents read |

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

Each managed repository owns its reviewed release workflows and `scripts/release.py`
with shared core modules. A repository's `GITHUB_TOKEN` writes only its own releases;
this avoids a central cross-repository Contents-write credential. The central status
repository remains `THEFLDR/HomeAssistant-IntegrationManager`. Adapt the publish
source directory for another integration's domain.

The owner provides Actions variables **`IM_CLIENT_ID`** (or **`IM_APP_ID`**) and
**`IM_INSTALLATION_ID`**, and secret **`IM_APP_PRIVATE_KEY`** in each repository requiring
promotion. The shared JWT helper explicitly requests a short-lived token scoped to
the registry repository with `actions_variables: read` and `contents: read`, and
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
