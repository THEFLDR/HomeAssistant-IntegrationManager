# Contributor and documentation instructions

Read the complete assignment under `docs/development/` for the current task before
making changes. Keep pull request titles exactly `PR - <branch-name>`.

## Technical documentation

Maintain published technical documentation in the native
[GitHub Wiki](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki), whose
Git remote is `https://github.com/THEFLDR/HomeAssistant-IntegrationManager.wiki.git`.
Keep development assignments, acceptance records and repository-specific GitHub
engineering material in this repository.

Do not replace native Wiki publication with repository Markdown, GitHub Pages or a
website. Preserve existing `docs/wiki/` source pages until publication has succeeded
and every migrated page has been read back from the native Wiki repository. If
access is blocked, retain those pages and report the exact failure. Once verified,
remove migrated source copies and update repository links; do not maintain duplicates.

## Commit identity

`THEFLDR` is the only intended human contributor. For work genuinely authenticated
under that owner's account, use Git author name `THEFLDR` and the account's verified
noreply email, currently `94011825+THEFLDR@users.noreply.github.com`. Verify the login
and email association with GitHub before configuring the local repository. Avoid
printing private email addresses. Do not change global Git identity configuration.

If the authenticated identity differs or verification is unavailable, report that
limitation and retain legitimate attribution. Never impersonate the owner, invent a
noreply ID, add false coauthors or rewrite merged history to change attribution.
GitHub's `web-flow` or other legitimate bot committer attribution may remain. Future
configuration does not remove historical contributor or commit records.

## Review and validation

For documentation-only changes, run the lightweight repository validation and link
checks, plus `git diff --check`; avoid the full application test/dependency pipeline.
Do not request Copilot review without explicit owner authorization; this Wiki
migration prohibits any request. Do not change Rulesets, branch protection,
repository security settings or GitHub App permissions. Leave the task's PR open
and unmerged when instructed.
