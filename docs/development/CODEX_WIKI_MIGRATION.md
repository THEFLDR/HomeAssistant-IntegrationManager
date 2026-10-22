# Codex assignment: GitHub Wiki migration and contributor identity

Work exclusively on branch `codex/docs-wiki-migration` in `THEFLDR/HomeAssistant-IntegrationManager`. This is a documentation-only change. Create PR titled exactly `PR - codex/docs-wiki-migration` against `main`; do not merge.

## Goals
1. Move the existing technical documentation from `docs/wiki/*.md` into the **native GitHub Wiki** for this repository, which is the separate Git repository `THEFLDR/HomeAssistant-IntegrationManager.wiki.git`. Do not substitute GitHub Pages, a wiki folder in the main repository, or a generated website.
2. Preserve the substantive English documentation, internal cross-page links, navigation, and page titles. Create/update a useful Wiki Home page and sidebar if appropriate. Ensure that wiki page names and links resolve in GitHub Wiki.
3. Verify actual Wiki publishing by reading back the pages from the native Wiki repository. Only after successful publication and verification, remove the migrated files under `docs/wiki/` from the main repository. If Wiki write access is unavailable, **do not delete the source pages**; report the exact blocker and leave a non-destructive PR for review instead.
4. Keep `docs/development/`, `docs/github/`, and other repo-specific engineering material in the main repository. Update `README.md` and any relevant links to point to `https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki`. Do not duplicate ongoing documentation in both places.
5. Use `THEFLDR` as the desired Git author identity for commits genuinely made under the owner's account, with the account's verified GitHub noreply email. Do not invent a noreply ID, impersonate a different account, falsify authorship, or rewrite already merged history. Check actual identity configuration and document any limitations. Ensure future Codex workflow instructions reflect the owner's preference that `THEFLDR` be the only intended human contributor. GitHub's `web-flow` or bot committer attribution may still occur depending on the platform.
6. Inspect the existing commit history for why `Stefan Felder` is displayed separately from `THEFLDR`, and report the observed author/committer names, emails (redact private email values), GitHub attribution, and what can safely be done without rewriting history. Do not claim that merely changing future commit config removes an existing contributor.
7. Do not modify functional integration code, GitHub Rulesets, branch protection, repository settings, or GitHub App permissions. Do not request a Copilot review. Avoid heavy CI for this docs-only PR.

## Deliverables and validation
- Actual native GitHub Wiki pages published and verified, or an explicit access blocker with the source pages preserved.
- Documentation links updated and obsolete `docs/wiki/` removed only after verified migration.
- Minimal changes to relevant development/contributor instructions.
- A concise report of pages migrated, verified Wiki URLs, link checks, contributor-attribution findings, and any manual owner actions required.
- Final diff self-review; PR against main with exact title `PR - codex/docs-wiki-migration`. Do not merge.
