# Home Assistant dashboard

The supported native custom-panel API registers **Integration Manager** automatically
in the sidebar, with `require_admin=true`. All WebSocket status, subscription and
mutation handlers also require HA administrator authorization on the server.
Native update installation also checks the calling user's administrator status;
trusted internal HA calls are allowed. No
separate login or undocumented manual dashboard configuration is required.

The overview shows environment, manager running version, registration/update/error
counts, release check and registry timestamps, and connection/permission errors.
Cards show repository/domain, installed/running/offered versions, channel, health,
operation progress, restart/verifying state, error, release identity/hash and promotion
audit outcome. Values from GitHub and integration code are rendered as text, not HTML.
HA pushes local state updates over an authenticated subscription; leaving the panel
open does not create GitHub polling or Actions runs.

Administration supports explicit repository approval, verified adoption of existing
files, installation/update, unregister/uninstall, retained-backup restore, restart,
manual update checks, connection settings and key rotation through native options.
Newly installed integrations are configured through their normal HA integration setup.
Existing HA config entry titles are shown before uninstall; configuration/user data
are not deleted. Destructive operations require domain-specific typed confirmation.

Sandbox offers RCs and a promotion button only when the cached current eligibility
checks pass; backend and Actions checks remain authoritative. Production absence
confirmation is shown only for target versions from 1.0.0 onward; 0.x promotion
needs only the applicable Sandbox and artifact checks. Production has no
promotion or RC installation path. Emergency override is never exposed in HA.

Each approved integration has one native update entity and one diagnostic health
sensor. Update entity attributes distinguish running version and operation state from
installed files. Native update release notes link to the authenticated GitHub release.
The panel defaults to the newest eligible release and permits selection of other
eligible versions. Updates must still be newer than the installed version; manual recovery uses the retained backup
rather than an unrestricted downgrade path. Global HA Settings-banner behavior and a
real mobile/browser session require live Sandbox acceptance; they are not promised
based solely on Python fixture tests.
