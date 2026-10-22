// Supported HA custom-panel web component. All server text uses textContent.
class IntegrationManagerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.state = null;
    this.busy = false;
    this.message = "Loading Integration Manager…";
  }

  set hass(value) {
    this._hass = value;
    if (!this.unsubscribe && !this.subscribing && this.isConnected) this.connect();
  }

  connectedCallback() {
    this.render();
    if (this._hass && !this.unsubscribe) this.connect();
  }

  disconnectedCallback() {
    if (this.unsubscribe) this.unsubscribe();
    this.unsubscribe = null;
  }

  async connect() {
    this.subscribing = true;
    try {
      this.state = await this._hass.callWS({ type: "integration_manager/status" });
      const unsubscribe = await this._hass.connection.subscribeMessage(
        state => { this.state = state; this.render(); },
        { type: "integration_manager/subscribe" });
      if (this.isConnected) this.unsubscribe = unsubscribe;
      else unsubscribe();
      this.message = "";
    } catch (error) {
      this.message = error.message || "Cannot load the manager; verify administrator access.";
    } finally {
      this.subscribing = false;
      this.render();
    }
  }

  node(tag, text, parent) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (parent) parent.append(node);
    return node;
  }

  button(parent, text, action, data = {}, enabled = true) {
    const button = this.node("button", text, parent);
    button.disabled = this.busy || !enabled;
    button.addEventListener("click", () => this.run(action, data));
  }

  async run(action, data) {
    if (["uninstall", "restore", "confirm_absent", "restart"].includes(action)) {
      const expected = action === "restart" ? "restart Home Assistant"
        : action === "confirm_absent" ? `production has not installed ${data.domain}`
        : `${action} ${data.domain}`;
      const detail = action === "uninstall"
        ? "Managed files will be removed. HA config entries, entities and user data remain. Restart required. "
        : "";
      const confirmation = window.prompt(`${detail}Type exactly: ${expected}`);
      if (confirmation !== expected) return;
      data = { ...data, confirmation };
    }
    if (action === "promote" && !window.confirm("Promote this exact verified release to Stable?")) return;
    this.busy = true;
    this.message = "Operation in progress…";
    this.render();
    try {
      await this._hass.callWS({ type: "integration_manager/action", action, ...data });
      this.message = action === "promote" ? "Promotion requested. Awaiting the audited workflow result." : "Request completed; check activation and health below.";
      this.state = await this._hass.callWS({ type: "integration_manager/status" });
    } catch (error) {
      this.message = error.message || "Operation failed. Check manager status.";
    } finally {
      this.busy = false;
      this.render();
    }
  }

  render() {
    const root = this.shadowRoot;
    root.replaceChildren();
    const style = this.node("style", `
      :host { display:block; color:var(--primary-text-color); background:var(--primary-background-color); min-height:100vh; font:16px system-ui,sans-serif; }
      main { max-width:1100px; margin:auto; padding:28px; } header { display:flex; align-items:center; gap:18px; } img { width:76px; height:76px; border-radius:14px; }
      h1 { margin:0; } h2 { font-size:1.15rem; } section,article { background:var(--card-background-color); padding:20px; margin:18px 0; border:1px solid var(--divider-color); border-radius:12px; }
      p { overflow-wrap:anywhere; line-height:1.5; } button,input { font:inherit; padding:10px 14px; margin:5px; border:1px solid var(--divider-color); border-radius:7px; }
      button { cursor:pointer; background:var(--primary-color); color:var(--text-primary-color,#fff); } button:disabled { opacity:.45; cursor:default; }
      input { color:var(--primary-text-color); background:var(--card-background-color); max-width:90%; } .notice { color:var(--error-color); } label { display:block; } a { color:var(--primary-color); } code { font-size:.9em; }
      @media(max-width:600px) { main { padding:14px; } header { align-items:flex-start; } h1 { font-size:1.4rem; } }
    `, root);
    style.setAttribute("data-owner", "integration-manager");
    const main = this.node("main", undefined, root);
    const header = this.node("header", undefined, main);
    const logo = this.node("img", undefined, header);
    logo.src = "/integration_manager_static/logo.png";
    logo.alt = "Integration Manager approved logo";
    const title = this.node("div", undefined, header);
    this.node("h1", "Integration Manager", title);
    this.node("p", this.state ? `${this.state.environment.toUpperCase()} · Running manager ${this.state.running_manager_version}` : "Connecting…", title);
    if (this.message) this.node("p", this.message, main).setAttribute("role", "status");
    if (!this.state) return;
    const overview = this.node("section", undefined, main);
    this.node("h2", "Overview", overview);
    this.node("p", `${this.state.integrations.length} registered · ${this.state.updates} updates · ${this.state.errors} errors${this.state.checking ? " · Checking releases…" : ""}`, overview);
    this.node("p", `Last release check: ${this.state.last_check || "not completed"} · Last registry write: ${this.state.last_registry || "not completed"}`, overview);
    if (this.state.error) this.node("p", this.state.error, overview).className = "notice";
    this.button(overview, "Check for updates", "check");
    this.button(overview, "Restart Home Assistant", "restart");
    this.node("h2", "Managed integrations", main);
    for (const record of this.state.integrations) {
      const card = this.node("article", undefined, main);
      this.node("h2", record.name, card);
      this.node("p", `${record.repository} · ${record.domain}`, card);
      const installed = record.installed ? record.installed.version : "not managed/installed";
      const offered = record.available ? `${record.available.version} (${record.available.prerelease ? "RC" : "Stable"})` : "none for this environment";
      this.node("p", `Installed: ${installed} · Running: ${record.running_version || "not active"} · Offered: ${offered}`, card);
      this.node("p", `State: ${record.state} · Health: ${record.health} · Health observed: ${record.health_at || "never"}${record.progress ? ` · Progress: ${record.progress}%` : ""}`, card);
      if (record.error) this.node("p", record.error, card).className = "notice";
      if (record.installed) this.node("code", `Release ${record.installed.release_id} · ${record.installed.tag} · SHA-256 ${record.installed.sha256}`, card);
      if (record.config_entries.length) this.node("p", `HA configuration retained on uninstall: ${record.config_entries.join(", ")}`, card);
      const actions = this.node("div", undefined, card);
      const selection = { domain: record.domain };
      if (record.offers && record.offers.length) {
        const label = this.node("label", "Eligible release", card);
        const choose = this.node("select", undefined, label);
        for (const offer of record.offers) {
          const option = this.node("option", offer.version, choose);
          option.value = offer.version;
        }
        selection.version = choose.value;
        choose.addEventListener("change", () => { selection.version = choose.value; });
      }
      this.button(actions, record.installed ? "Update" : "Install", "install", selection, Boolean(record.available) && !["pending_restart", "downloaded"].includes(record.state));
      if (!record.installed) this.button(actions, "Verify and adopt existing files", "adopt", selection, Boolean(record.available));
      this.button(actions, "Uninstall / remove registration", "uninstall", { domain: record.domain });
      this.button(actions, "Restore retained backup", "restore", { domain: record.domain });
      const configLink = this.node("a", "Open HA integration setup", card);
      configLink.href = `/config/integrations/dashboard?domain=${encodeURIComponent(record.domain)}`;
      if (this.state.environment === "sandbox") {
        this.button(actions, "Promote to Stable", "promote", { domain: record.domain }, record.promotion_eligible);
        const promotionVersion = record.installed?.version || record.available?.version;
        if (promotionVersion && Number(promotionVersion.split(".")[0]) >= 1) {
          this.button(actions, "Confirm initial Production absence", "confirm_absent", { domain: record.domain });
        }
        if (record.promotion_blocker) this.node("p", record.promotion_blocker, card);
      }
      if (this.state.environment === "production" && !record.installed) {
        this.button(actions, "Confirm not installed on Production", "confirm_absent", { domain: record.domain });
      }
      if (record.promotion) {
        this.node("p", `Promotion: ${record.promotion.state}${record.promotion.error ? ` · ${record.promotion.error}` : ""}`, card);
        if (record.promotion.url && record.promotion.url.startsWith("https://github.com/")) {
          const link = this.node("a", "View promotion audit run", card);
          link.href = record.promotion.url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
        }
      }
    }
    if (this.state.removed_integrations && this.state.removed_integrations.length) {
      const removed = this.node("section", undefined, main);
      this.node("h2", "Removed integrations", removed);
      for (const record of this.state.removed_integrations) {
        this.node("p", `${record.repository} · ${record.domain} · ${record.state}${record.restart_pending ? " · Restart pending" : ""} · Absence ${record.owner_confirmed ? "confirmed" : "unconfirmed"}`, removed);
        if (this.state.environment === "production" && !record.owner_confirmed) {
          this.button(removed, `Confirm ${record.domain} is not installed`, "confirm_absent", { domain: record.domain }, record.state === "not_installed" && !record.restart_pending);
        }
      }
    }
    const admin = this.node("section", undefined, main);
    this.node("h2", "Administration", admin);
    this.node("p", `Registry: ${this.state.registry_repository}. GitHub App permissions: ${JSON.stringify(this.state.permissions)}. Rotate credentials in Settings → Devices & services → Integration Manager → Configure.`, admin);
    const form = this.node("form", undefined, admin);
    const repoLabel = this.node("label", "GitHub owner/repository", form);
    const repo = this.node("input", undefined, repoLabel);
    repo.required = true;
    repo.placeholder = "owner/repository";
    const domainLabel = this.node("label", "Home Assistant domain", form);
    const domain = this.node("input", undefined, domainLabel);
    domain.required = true;
    domain.placeholder = "integration_domain";
    const approvalLabel = this.node("label", undefined, form);
    const approval = this.node("input", undefined, approvalLabel);
    approval.type = "checkbox";
    approval.required = true;
    approvalLabel.append("I approve this repository and its executable integration code.");
    const submit = this.node("button", "Register repository", form);
    submit.type = "submit";
    submit.disabled = this.busy;
    form.addEventListener("submit", event => {
      event.preventDefault();
      this.run("register", { repository: repo.value.trim(), domain: domain.value.trim(), approved: approval.checked });
    });
  }
}

if (!customElements.get("integration-manager-panel")) {
  customElements.define("integration-manager-panel", IntegrationManagerPanel);
}
