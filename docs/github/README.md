# Owner-only branch ruleset import

`main-ruleset.json` is an import-ready proposal, not an applied setting. Import it
manually only after the final CI check is visible as **`CI / Validation`**. It targets
`main`, requires PRs, resolved review conversations, that exact current CI check,
and protects against deletion/force-push.

The approving review count is zero so a sole owner can merge their own PR after
explicit review; GitHub does not normally let authors approve their own PR. Owner
authorization remains part of the process. A Copilot Comment review is not assumed
to be a formal approval. There are no bypass actors or invented security identities.

Inspect the existing provisional ruleset before importing. GitHub combines matching
rulesets; replace/reconcile overlapping requirements rather than requiring obsolete
check names or an impossible human approval. The implementation never creates,
imports, modifies or deletes any ruleset, branch protection or App permission.

Read-only inspection on 21 October 2026 found `copilot_code_review` in the existing
active `main` ruleset (ID `25578748`), with `review_draft_pull_requests: true` and
`review_on_push: false`. It automatically requests review for PRs, including drafts.
The owner must manually disable/remove that rule to match the review-budget policy.
It remains unchanged by this implementation. The proposed JSON does not include a
Copilot rule and keeps required CI independent of review availability.
