# Architecture

Sandbox and Production are independent HA OS instances. Both initiate verified HTTPS
requests to GitHub. Neither contacts the other. No inbound GitHub endpoint, database,
middleware, API server or additional listening port is required.

| Responsibility | Implementation |
| --- | --- |
| App JWT, installation tokens, HTTPS, pagination, ETags | `github.py` |
| Version/channel/registry eligibility | `models.py`, `policy.py` |
| Package limits, paths and integrity | `artifacts.py` |
| Domain-scoped replacement, backup, recovery journal | `installer.py` |
| Serialized operations and native private HA Store | `manager.py` |
| Setup, rotation and unload | `config_flow.py`, `__init__.py` |
| Native update and health entities | `update.py`, `sensor.py` |
| Supported admin custom panel and authorized WebSocket actions | `panel.py`, `frontend/panel.js` |
| Publish, promotion and emergency override | `scripts/release.py`, named workflows |

HA runs one manager entry and one serialized writer per environment. Installation
and registry operations share an async lock. Stored identity is bound to environment,
registry repository and a random instance ID. Another instance cannot silently take
over a variable. Repository Variables have no compare-and-swap API; this is a
single-writer design, not distributed consensus. Do not run a cloned HA backup
concurrently with its original: their cloned instance IDs cannot identify the clone.

All file updates conservatively require a full HA restart. A process-scoped boot ID,
HA's loaded integration manifest, loaded component status and installed file hashes
separate installed bytes from running code. Reloading a config entry does not satisfy
the restart gate. Configure newly installed integrations through their normal HA flow.
HA handles their exactly pinned Python requirements; failed setup remains unverified.

The panel requires no manual Lovelace configuration or unsupported frontend patching.
Native update entities supplement it. A global Settings update banner for every
custom update entity is not guaranteed by HA and is not assumed.

Files and HA Store survive restarts. Timers, subscriptions, in-memory tokens and
promotion watchers are restarted by HA. Persisted promotion requests are rechecked
against their audited workflow and final release identity.
