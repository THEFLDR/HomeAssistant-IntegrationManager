# Native Wiki migration and contributor identity report

Checked on **22 October 2026** for branch `codex/docs-wiki-migration`, following
[the complete migration assignment](CODEX_WIKI_MIGRATION.md).

## Publication status: blocked; source pages preserved

**Zero pages have been published or verified in the native GitHub Wiki.** All 11
existing `docs/wiki/*.md` files remain byte-for-byte unchanged. No replacement Wiki,
website, ongoing documentation copy or publishing workflow is introduced by this PR.

The exact publication target is
`https://github.com/THEFLDR/HomeAssistant-IntegrationManager.wiki.git`.
Both `git ls-remote` and an actual normal Git push to this native Wiki remote failed:

```text
remote: Repository not found.
fatal: repository 'https://github.com/THEFLDR/HomeAssistant-IntegrationManager.wiki.git/' not found
```

The push exited with status **128**. Repository API metadata reports `has_wiki: true`
and the authenticated account's repository permissions include push/admin access.
The session's `/user` response identifies `THEFLDR`. These checks establish repository
access, not access to the separate Wiki Git repository. No repository setting was changed.

Public HTTP GETs of both the
[Wiki landing URL](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki)
and [Home URL](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Home)
returned HTTP 200 **after redirecting to the main repository homepage**. This does
not verify a Wiki page. The observations are consistent with an uninitialized Wiki;
they do not prove whether initialization or a credential-specific Wiki access
restriction is the sole cause. The current tools cannot publish or read back that
remote, so deleting source pages would violate the assignment.

A temporary local Wiki Git checkout, outside the project repository, was prepared
with the 11 pages and `_Sidebar.md` for the actual push attempt. It preserves page
filenames/titles and substantive English content, converts cross-page `.md` links
to native Wiki URLs, and converts engineering-file links to repository `blob/main`
URLs. Its Home identifies the native Wiki as the documentation location. Local page,
heading-fragment and repository-file targets passed checks before the push. These
are preparation checks, **not evidence of successful remote publication**. Temporary
workspace files are not a deliverable or a durable substitute for the native Wiki;
recreate them from the preserved sources when access is available.

| Preserved source page | Intended native page name; not yet published |
| --- | --- |
| `docs/wiki/Home.md` | `Home` |
| `docs/wiki/Architecture.md` | `Architecture` |
| `docs/wiki/Installation.md` | `Installation` |
| `docs/wiki/GitHub-Configuration.md` | `GitHub-Configuration` |
| `docs/wiki/Managed-Repositories.md` | `Managed-Repositories` |
| `docs/wiki/Promotion-Workflow.md` | `Promotion-Workflow` |
| `docs/wiki/Health-and-Status.md` | `Health-and-Status` |
| `docs/wiki/Dashboard.md` | `Dashboard` |
| `docs/wiki/Security.md` | `Security` |
| `docs/wiki/Development.md` | `Development` |
| `docs/wiki/Troubleshooting.md` | `Troubleshooting` |

README links retain access to the preserved source pages and identify the native
Wiki destination as pending. Existing engineering links stay valid. No target Wiki
URL is represented as a verified published documentation page.

## Owner action and completion procedure

1. While signed in as `THEFLDR`, open the repository's **Wiki** tab. If offered,
   create and save the first `Home` page to initialize the native Wiki. This is a
   documentation publication action; no Ruleset or security-setting change is needed.
2. Retry `git ls-remote` and clone the exact `.wiki.git` remote using the configured
   identity. If it remains unavailable after a page exists, check whether this
   environment's GitHub credential supports access to the Wiki repository. Do not
   broaden the HA App's permissions or silently publish somewhere else.
3. Fetch and preserve any pages already on the remote. Copy the 11 source pages,
   preserve their titles/content, adapt links for GitHub Wiki, and add a useful
   Home/sidebar. Push normally, without force-pushing or deleting unrelated pages.
4. Clone the native Wiki into a second, fresh checkout. Compare all published pages
   and navigation with the intended content, verify page names and heading links,
   and confirm the rendered Wiki URLs do not redirect to the repository homepage.
5. Only after those checks succeed, remove the migrated `docs/wiki/` files in this
   development branch and replace repository documentation links with verified Wiki
   URLs. Keep `docs/development/`, `docs/github/` and engineering files in the main
   repository. Record the native Wiki commit and verified URLs in the PR.

## Contributor-attribution findings

GitHub identifies the authenticated account as login **`THEFLDR`**, numeric ID
**94011825**, with profile name **`Stefan Felder`**. These are the login and display
name of the same account, not evidence of two human contributors.

The inherited system Git configuration specified author name `Codex` and a private
email; the global user configuration overrode it with name `Stefan Felder` and a
private email. The effective former email is **not** in the account's verified-email
list. Private values were inspected only as needed for comparison and are redacted
here and in the PR report.

The GitHub `/user/emails` response confirms
**`94011825+THEFLDR@users.noreply.github.com` is verified**. This address was also
observed in existing commits attributed by GitHub to `THEFLDR`; it was not invented
from an assumed ID. This repository now has local Git author/committer configuration
`THEFLDR <94011825+THEFLDR@users.noreply.github.com>`, and both effective Git identities
were checked. Global/system configuration and existing commits remain unchanged.

| Observed commit | Raw Git author | Raw Git committer | GitHub author / committer attribution |
| --- | --- | --- | --- |
| Initial commit `351d420` | `Stefan Felder <94011825+THEFLDR@users.noreply.github.com>` | `GitHub <noreply@github.com>` | `THEFLDR` / `web-flow` |
| PR #1 merge `dd0989f` | `Stefan Felder <94011825+THEFLDR@users.noreply.github.com>` | `GitHub <noreply@github.com>` | `THEFLDR` / `web-flow` |
| PR #2 squash merge `c72b7da` | `Stefan Felder <94011825+THEFLDR@users.noreply.github.com>` | `GitHub <noreply@github.com>` | `THEFLDR` / `web-flow` |
| Migration assignment `8bda6d6` | `Stefan Felder <94011825+THEFLDR@users.noreply.github.com>` | `Stefan Felder <94011825+THEFLDR@users.noreply.github.com>` | `THEFLDR` / `THEFLDR` |
| Previous development head `1a3c1fa` | `Stefan Felder <private email redacted>` | `Stefan Felder <private email redacted>` | no associated account / no associated account |

Eight commits on the prior development history have the private-email pattern;
`1a3c1fa` is representative. Git author names are stored strings, distinct from
GitHub account attribution. The display name and unassociated private-email commits
explain the observed alternate labels without establishing another GitHub identity.
The live `contributors?anon=1` response currently lists only **`THEFLDR`**, with three
contributions; the contributor-statistics endpoint has no calculated result yet.
Contributor counts are a cached view of repository/default-branch history, not a
complete audit of all development refs. The separate `Stefan Felder` contributor
entry reported by the owner was **not reproduced** in that current API response.

The two older merges and initial commit have valid GitHub signatures. The assignment
and prior development head are unsigned. Verified ownership of a noreply **email**
is separate from a cryptographically verified commit **signature**; this task does
not fabricate a signature or promise GitHub's Verified badge for new local commits.

Safe future practice is documented in [AGENTS.md](../../AGENTS.md): verify the actual
owner account, configure only this repository, and use the confirmed noreply identity
for legitimate owner-authenticated work. If an old private address genuinely belongs
to the owner, adding and verifying it in the owner's GitHub email settings may link
eligible past commits; that is an optional owner action, not part of this task. Do not
add an address the owner does not control. Neither changing future configuration nor
waiting for cached statistics removes stored author names or guarantees removal of
an existing contributor label. No merged history was rewritten.

## Validation and scope

- Compared all 11 source-page hashes with the assignment branch: unchanged.
- Checked repository Markdown links and headings, and prepared native page/link targets.
- Ran the existing lightweight documentation/repository check and `git diff --check`.
- Final self-review checks that the diff contains only Markdown documentation.
- Application code, tests, dependencies, workflows, Rulesets, branch protection,
  repository security settings and GitHub App permissions remain unchanged.
- No Copilot review requested. The PR stays open and unmerged.
