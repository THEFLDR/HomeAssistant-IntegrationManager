# Codex assignment — v0.1.1 GitHub App onboarding fix

Work only on the existing branch `codex/0.1.1`, based on `main`. Open a PR titled exactly `PR - codex/0.1.1`; do not merge.

## Observed failure
The owner manually copied the v0.1.0 integration from main to an HA OS Sandbox. During first-time GitHub App configuration, the UI displayed:
`Cannot authenticate or store the key. Verify App ID, Installation ID, RSA PEM key, repository access and outgoing HTTPS.`
The user **did supply a PEM key**; the empty field in the screenshot was after the failure and does not mean the key was omitted. Home Assistant Settings > System > Logs showed no useful error. App ID, Client ID, and Installation ID were entered. Do not request or print the private key. We do not yet know whether the failure occurs during parsing, JWT signing, GitHub API authentication, installation access, persistence, or exception handling. Do not assume a cause.

## Tasks
1. Trace the full onboarding flow from UI/config flow to PEM validation, JWT generation, installation token exchange, repository access checks, secure storage, and any cleanup. Identify concrete defects in the actual code and fix them narrowly.
2. Add structured, actionable diagnostics: log the failed stage and sanitized exception category/details with appropriate severity; surface distinct actionable errors in the setup UI; never log or expose PEM content, JWTs, installation tokens, Authorization headers, or private credential paths. Ensure exceptions are not silently swallowed and no sensitive data leaks in tracebacks or responses.
3. Review compatibility with supported HA Core runtime and installed crypto/JWT libraries; verify RSA PEM formats and newline handling, GitHub App permissions and repository access requirements. Do not loosen security or invent extra mandatory permissions. Make failure to persist the key distinguishable from GitHub authentication failure.
4. Add targeted automated regression tests for success, wrong App/Installation ID, invalid/mismatched PEM, inaccessible repo, GitHub API/network failure, persistence failure, and sanitized logs. Mock GitHub calls; tests must not require real credentials.
5. Keep release scope strictly v0.1.1 bugfix. No unrelated refactors, dashboard changes, new security architecture, Wiki migration, or Ruleset edits. Respect concurrent `codex/docs-wiki-migration` branch. Follow existing CI policy, avoid redundant Actions runs, and do not request Copilot review.
6. Update only relevant version/changelog and technical docs as required by the repository conventions. Re-read the repository state and self-review the final diff before opening the PR. Explain root cause(s) supported by code and tests, exact changes, remaining unknowns, and Sandbox retest steps.

## Acceptance
- Configuration succeeds with a valid GitHub App installation and PEM (mocked automated test; live Sandbox validation still required).
- If it fails on HA OS, the user sees a meaningful error and HA logs show a sanitized, actionable diagnostic.
- No secrets in logs, exceptions shown to users, or persisted outside the intended secure store.
- PR titled `PR - codex/0.1.1`, **do not merge**.
