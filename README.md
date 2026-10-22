# Home Assistant Integration Manager

<img src="approved-icon.png" alt="Approved Integration Manager logo" width="144">

Version **0.1.0** manages the owner's HA custom integrations using outgoing HTTPS
and GitHub App authentication. Sandbox installs RCs; Production installs Stable
releases from 1.0.0 onward, after security review.

The admin-only HA panel provides repository approval, verified installation and
adoption, native update entities, uninstall, retained-backup recovery, restart and
activation status, health reporting and RC-to-Stable promotion. GitHub Actions
independently revalidates promotion, preserving release ID, tag, commit, asset ID
and SHA-256 without rebuilding. No inbound webhooks or additional services are needed.

Technical documentation is published in the
[native GitHub Wiki](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki).
See [installation](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Installation),
[GitHub configuration](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/GitHub-Configuration),
[architecture](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Architecture),
and [development](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Development).
The [migration report](docs/development/WIKI_MIGRATION_REPORT.md) records publication
and fresh-clone verification.

The complete functional scope is delivered together; the older concept's staged
roadmap is superseded by the owner's assignment.

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/pytest
.venv/bin/python scripts/check_repository.py
```

The proposed [main ruleset](docs/github/main-ruleset.json) is **for owner import only**.
This implementation never applies repository security configuration. Review the
[temporary upstream dependency exceptions](https://github.com/THEFLDR/HomeAssistant-IntegrationManager/wiki/Security) before development.
Automated tests mock GitHub; live Sandbox installation, restart and promotion require
owner-side acceptance after merge and RC publication.

Contributor identity and future documentation maintenance are described in
[AGENTS.md](AGENTS.md). `THEFLDR` is the intended human contributor; historical
commit attribution is preserved.
