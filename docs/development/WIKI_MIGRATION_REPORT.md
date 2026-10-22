# Native Wiki migration and contributor identity report

Verified on **22 October 2026** on branch `codex/docs-wiki-migration`, following
[the migration assignment](CODEX_WIKI_MIGRATION.md). The owner's later request also
authorizes correcting the historical owner name from `Stefan Felder` to `THEFLDR`;
repository protection and the ban on security-setting changes still apply.

## Native Wiki publication: complete

All **11 technical documentation pages and `_Sidebar.md`** are published in the
[native GitHub Wiki](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki).
The separate Git remote is
`https://github.com/THEFLDR/HomeAssistant-IntegrationManager.wiki.git`.
Published commit: **`9d152719e4802226793d64254ff5a10acd3e698f`**.

The first attempt failed with `Repository not found` before initialization. The
owner created the initial Home page (`9efba70`), after which cloning and a normal
fast-forward publication push succeeded. That initialization history was preserved;
no Wiki history was force-pushed or unrelated page deleted.

A **second, fresh clone** read back every page and the sidebar. All 12 SHA-256 content
hashes matched the intended published files. All 11 page URLs below returned HTTP 200
at the native Wiki and contained their expected rendered page headings, without
redirecting to the repository homepage. Cross-page links and heading fragments were
checked against the published page names; engineering links were checked against
files retained in `main`. Home and the sidebar provide navigation.

| Migrated source | Verified native Wiki URL |
| --- | --- |
| `docs/wiki/Architecture.md` | [Architecture](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Architecture) |
| `docs/wiki/Dashboard.md` | [Dashboard](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Dashboard) |
| `docs/wiki/Development.md` | [Development](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Development) |
| `docs/wiki/GitHub-Configuration.md` | [GitHub-Configuration](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/GitHub-Configuration) |
| `docs/wiki/Health-and-Status.md` | [Health-and-Status](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Health-and-Status) |
| `docs/wiki/Home.md` | [Home](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Home) |
| `docs/wiki/Installation.md` | [Installation](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Installation) |
| `docs/wiki/Managed-Repositories.md` | [Managed-Repositories](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Managed-Repositories) |
| `docs/wiki/Promotion-Workflow.md` | [Promotion-Workflow](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Promotion-Workflow) |
| `docs/wiki/Security.md` | [Security](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Security) |
| `docs/wiki/Troubleshooting.md` | [Troubleshooting](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Troubleshooting) |

Source page filenames and titles and substantive English content are preserved.
Cross-page `.md` links now use native Wiki URLs; links to acceptance evidence,
assignments and the dependency policy use repository `blob/main` URLs. Only staging
language on Home and Development was updated to describe the published Wiki.

**Only after publication and fresh readback succeeded** were the migrated
`docs/wiki/*.md` files removed from the development branch. README and acceptance
links now target the verified Wiki. Development assignments, acceptance records,
`docs/github/` and security policy files remain in the main repository. There is no
second ongoing technical-documentation collection or alternate publishing platform.

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
an existing contributor label. No remote history has been rewritten; see the owner-requested correction below.

## Owner-requested history correction: blocked from remote application

The owner subsequently requested renaming historical `Stefan Felder` commits to
`THEFLDR`. This newer instruction supersedes the assignment's earlier prohibition
on that specific correction; it does not authorize changing repository protections.

Read-only inspection of active ruleset **`main` (`25578748`)** found an enforced
**`non_fast_forward`** rule and **no bypass actors**, alongside PR/CI requirements.
Replacing existing commits on `main` requires a non-fast-forward update, which that
rule prohibits. No force push of `main` or other main-repository ref has been made,
and no Ruleset, protection, App permission or repository security setting was changed.

A local author-correction proposal and original-history backup are prepared for
review outside the repository. It covers the current `main` and open development
branch (six commits, four with the old owner name), changes the owner's raw
author/committer identity where it is `Stefan Felder`
to the verified `THEFLDR` noreply identity, and retains legitimate existing GitHub
committer metadata. Every proposed commit must have exactly the original tree and
message; parent IDs are mapped to corrected commits. Rewritten commits cannot retain
the old GitHub signatures, and new commit IDs do not remove old objects retained by
GitHub, merged PRs or other clones. The older deleted development branch and GitHub's
PR refs are not silently rewritten. No published release tags currently exist.

**The history correction is not applied remotely.** The owner must decide how to
permit the required history replacement under repository governance; this task will
not modify or bypass the active rule. No `.mailmap` substitute is presented as a
rewrite of stored commits. Future work already uses the verified owner identity.

## Validation and scope

- Verified all 11 page titles and native Wiki URLs, and fresh-clone hashes for every
  page plus sidebar before removing source copies.
- Checked repository Markdown links and heading targets, plus Wiki page/heading links.
- Ran the existing lightweight documentation/repository check and `git diff --check`.
- Final self-review confirms the PR contains only Markdown changes.
- Application code, tests, dependencies, workflows, Rulesets, branch protection,
  repository security settings and GitHub App permissions remain unchanged.
- No Copilot review requested. PR #3 remains open and unmerged.
