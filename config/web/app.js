"use strict";

/* ============================================================
   Mail Platform - admin web UI
   Talks to the control-plane REST API through nginx at /api/.
   ============================================================ */

const API = "/api";
const TOKEN_KEY = "mp_token";

const state = {
    view: "dashboard",
    domains: [],
};

/* ---------- token ---------- */
const getToken = () => localStorage.getItem(TOKEN_KEY);
const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
const clearToken = () => localStorage.removeItem(TOKEN_KEY);

/* ---------- helpers ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function toast(message, kind = "ok") {
    const root = $("#toasts");
    const el = document.createElement("div");
    el.className = `toast ${kind}`;
    el.textContent = message;
    root.appendChild(el);
    setTimeout(() => {
        el.style.transition = "opacity .3s";
        el.style.opacity = "0";
        setTimeout(() => el.remove(), 300);
    }, kind === "error" ? 5000 : 3000);
}

/* ---------- API layer ---------- */
async function login(username, password) {
    const res = await fetch(`${API}/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username, password }),
    });
    if (!res.ok) throw new Error("Invalid username or password");
    const data = await res.json();
    if (!data.access_token) throw new Error("No token in response");
    setToken(data.access_token);
}

async function api(method, path, body) {
    const headers = { Authorization: `Bearer ${getToken()}` };
    const opts = { method, headers };
    if (body !== undefined) {
        headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(body);
    }
    const res = await fetch(`${API}${path}`, opts);

    if (res.status === 401) {
        clearToken();
        renderLogin();
        throw new Error("Session expired, please log in again");
    }

    let json;
    try { json = await res.json(); } catch { json = null; }

    if (!res.ok || (json && json.ok === false)) {
        throw new Error((json && json.error) || `Request failed (${res.status})`);
    }
    return json ? json.data : null;
}

/* ============================================================
   Modal
   ============================================================ */
function closeModal() { $("#modal-root").innerHTML = ""; }

/**
 * openModal({ title, fields, html, confirmLabel, onConfirm, wide })
 * fields: [{ name, label, type, value, placeholder, hint, options, checked }]
 * onConfirm(values) -> may return a Promise; modal closes on resolve.
 * If onConfirm is omitted, only a Close button is shown (info panel).
 */
function openModal({ title, fields = [], html = "", confirmLabel = "Save", onConfirm = null, wide = false }) {
    const fieldsHtml = fields.map((f) => {
        const id = `f_${f.name}`;
        if (f.type === "checkbox") {
            return `<div class="field checkbox-row">
                <input type="checkbox" id="${id}" data-field="${f.name}" ${f.checked ? "checked" : ""}>
                <label for="${id}">${esc(f.label)}</label>
            </div>`;
        }
        let control;
        if (f.type === "textarea") {
            control = `<textarea id="${id}" data-field="${f.name}" placeholder="${esc(f.placeholder || "")}">${esc(f.value || "")}</textarea>`;
        } else if (f.type === "select") {
            const opts = (f.options || []).map((o) => `<option value="${esc(o.value)}" ${o.value === f.value ? "selected" : ""}>${esc(o.label)}</option>`).join("");
            control = `<select id="${id}" data-field="${f.name}">${opts}</select>`;
        } else {
            control = `<input type="${f.type || "text"}" id="${id}" data-field="${f.name}" value="${esc(f.value ?? "")}" placeholder="${esc(f.placeholder || "")}">`;
        }
        return `<div class="field">
            <label for="${id}">${esc(f.label)}</label>
            ${control}
            ${f.hint ? `<div class="hint">${esc(f.hint)}</div>` : ""}
        </div>`;
    }).join("");

    $("#modal-root").innerHTML = `
        <div class="modal-overlay">
            <div class="modal ${wide ? "wide" : ""}">
                <div class="modal-head">
                    <h3>${esc(title)}</h3>
                    <button class="x" data-act="close">&times;</button>
                </div>
                <div class="modal-body">${fieldsHtml}${html}</div>
                <div class="modal-foot">
                    <button class="ghost" data-act="close">${onConfirm ? "Cancel" : "Close"}</button>
                    ${onConfirm ? `<button data-act="confirm">${esc(confirmLabel)}</button>` : ""}
                </div>
            </div>
        </div>`;

    const overlay = $(".modal-overlay");
    overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
    $("#modal-root").querySelectorAll('[data-act="close"]').forEach((b) => b.addEventListener("click", closeModal));

    const firstInput = $(".modal-body input, .modal-body textarea, .modal-body select");
    if (firstInput) firstInput.focus();

    if (onConfirm) {
        const confirmBtn = $('[data-act="confirm"]');
        const submit = async () => {
            const values = {};
            $("#modal-root").querySelectorAll("[data-field]").forEach((el) => {
                values[el.dataset.field] = el.type === "checkbox" ? el.checked : el.value;
            });
            confirmBtn.disabled = true;
            confirmBtn.innerHTML = '<span class="spinner"></span>';
            try {
                await onConfirm(values);
                closeModal();
            } catch (err) {
                confirmBtn.disabled = false;
                confirmBtn.textContent = confirmLabel;
                toast(err.message, "error");
            }
        };
        confirmBtn.addEventListener("click", submit);
        $(".modal-body").addEventListener("keydown", (e) => {
            if (e.key === "Enter" && e.target.tagName !== "TEXTAREA") { e.preventDefault(); submit(); }
        });
    }
}

function confirmAction(message, onYes, { confirmLabel = "Confirm", danger = false } = {}) {
    openModal({
        title: "Please confirm",
        html: `<p style="margin:0">${esc(message)}</p>`,
        confirmLabel,
        onConfirm: onYes,
    });
    if (danger) { const b = $('[data-act="confirm"]'); if (b) b.classList.add("danger"); }
}

/* ============================================================
   Login screen
   ============================================================ */
function renderLogin() {
    document.getElementById("app").innerHTML = `
        <div class="login-wrap">
            <form class="login-card" id="login-form">
                <div class="brand"><div class="logo">M</div></div>
                <h1>Mail Platform</h1>
                <p class="sub">Sign in with your admin credentials.</p>
                <div class="field">
                    <label for="u">Username</label>
                    <input id="u" autocomplete="username" autofocus>
                </div>
                <div class="field">
                    <label for="p">Password</label>
                    <input id="p" type="password" autocomplete="current-password">
                </div>
                <button type="submit" id="login-btn">Sign in</button>
            </form>
        </div>`;

    $("#login-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = $("#login-btn");
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span>';
        try {
            await login($("#u").value.trim(), $("#p").value);
            renderShell();
        } catch (err) {
            toast(err.message, "error");
            btn.disabled = false;
            btn.textContent = "Sign in";
        }
    });
}

/* ============================================================
   Shell + navigation
   ============================================================ */
const NAV = [
    { key: "dashboard", label: "Dashboard", ico: "📊" },
    { key: "domains", label: "Domains", ico: "🌐" },
    { key: "users", label: "Users", ico: "👤" },
    { key: "aliases", label: "Aliases", ico: "↪" },
    { key: "queue", label: "Mail queue", ico: "📬" },
    { key: "certs", label: "Certificates", ico: "🔒" },
    { key: "logs", label: "Logs", ico: "📜" },
    { key: "security", label: "Security", ico: "🛡️" },
];

function renderShell() {
    document.getElementById("app").innerHTML = `
        <div class="shell">
            <aside class="sidebar">
                <div class="brand"><div class="logo">M</div><span>Mail Platform</span></div>
                <nav class="nav">
                    ${NAV.map((n) => `<a data-view="${n.key}"><span class="ico">${n.ico}</span><span>${n.label}</span></a>`).join("")}
                </nav>
                <div class="spacer"></div>
                <nav class="nav"><a class="logout" data-act="logout"><span class="ico">⎋</span><span>Log out</span></a></nav>
            </aside>
            <div class="main">
                <div class="topbar"><h2 id="page-title"></h2><div id="topbar-actions"></div></div>
                <div class="content" id="content"></div>
            </div>
        </div>`;

    $(".sidebar").addEventListener("click", (e) => {
        const navItem = e.target.closest("[data-view]");
        if (navItem) { go(navItem.dataset.view); return; }
        if (e.target.closest('[data-act="logout"]')) { clearToken(); renderLogin(); }
    });

    go(state.view);
}

function go(view) {
    state.view = view;
    // stop any live polling (dashboard resources, live logs) from the old view
    ["_statsTimer", "_logTimer"].forEach((k) => { if (state[k]) { clearInterval(state[k]); state[k] = null; } });
    // #content persists across navigation; replace it so delegated click
    // listeners from the previous view do not stack up on the same node.
    const old = $("#content");
    old.replaceWith(old.cloneNode(false));
    document.querySelectorAll(".nav a[data-view]").forEach((a) => a.classList.toggle("active", a.dataset.view === view));
    $("#page-title").textContent = NAV.find((n) => n.key === view).label;
    $("#topbar-actions").innerHTML = "";
    const views = { dashboard: viewDashboard, domains: viewDomains, users: viewUsers, aliases: viewAliases, queue: viewQueue, certs: viewCerts, logs: viewLogs, security: viewSecurity };
    views[view]();
}

function loading() { $("#content").innerHTML = `<div class="empty"><span class="spinner" style="border-color:#ccc;border-top-color:var(--accent)"></span></div>`; }
function statusBadge(active) { return active ? '<span class="badge ok">active</span>' : '<span class="badge off">disabled</span>'; }

/* ============================================================
   Domains
   ============================================================ */
async function viewDomains() {
    loading();
    let domains;
    try { domains = await api("GET", "/domains"); }
    catch (e) { return errorState(e); }
    state.domains = domains;

    const rows = domains.length ? domains.map((d) => `
        <tr>
            <td><strong>${esc(d.name)}</strong></td>
            <td>${statusBadge(d.active)}</td>
            <td class="dcheck" data-domain="${esc(d.name)}"><span class="muted">…</span></td>
            <td class="actions">
                <button class="ghost sm" data-act="dns" data-name="${esc(d.name)}">DNS</button>
                <button class="ghost sm" data-act="check" data-name="${esc(d.name)}">Check</button>
                <button class="ghost sm" data-act="toggle" data-name="${esc(d.name)}" data-active="${d.active}">${d.active ? "Disable" : "Enable"}</button>
                <button class="danger sm" data-act="delete" data-name="${esc(d.name)}">Delete</button>
            </td>
        </tr>`).join("") : `<tr><td colspan="4" class="empty">No domains yet. Add one above.</td></tr>`;

    $("#content").innerHTML = `
        <div class="card">
            <div class="card-head"><h3>Add domain</h3></div>
            <div class="card-body">
                <form class="inline-form" id="add-domain">
                    <div class="field"><label>Domain name</label><input id="d-name" placeholder="example.com"></div>
                    <button type="submit">Add domain</button>
                </form>
                <p class="hint" style="margin:10px 0 0">Generates a DKIM key, reconciles config and tries to issue a certificate. This can take a few seconds.</p>
            </div>
        </div>
        <div class="card">
            <div class="card-head"><h3>Domains</h3><span class="muted">${domains.length} total</span></div>
            <table><thead><tr><th>Name</th><th>Active</th><th>Deliverability</th><th></th></tr></thead><tbody>${rows}</tbody></table>
        </div>`;

    $("#add-domain").addEventListener("submit", async (e) => {
        e.preventDefault();
        const name = $("#d-name").value.trim();
        if (!name) return;
        const btn = e.submitter; btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>';
        try {
            const res = await api("POST", "/domains", { name });
            toast(`Domain ${name} added`);
            showDnsModal(res.name, res.dns, res.cert_message);
            viewDomains();
        } catch (err) {
            toast(err.message, "error");
            btn.disabled = false; btn.textContent = "Add domain";
        }
    });

    $("#content").addEventListener("click", onDomainAction);
    loadDomainBadges();
}

async function onDomainAction(e) {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const name = btn.dataset.name;
    const act = btn.dataset.act;

    if (act === "dns") {
        try { const dns = await api("GET", `/domains/${encodeURIComponent(name)}/dns`); showDnsModal(name, dns); }
        catch (err) { toast(err.message, "error"); }
    } else if (act === "check") {
        showCheckModal(name);
    } else if (act === "toggle") {
        const active = btn.dataset.active === "true";
        try {
            await api("POST", `/domains/${encodeURIComponent(name)}/${active ? "disable" : "enable"}`);
            toast(`Domain ${active ? "disabled" : "enabled"}`);
            viewDomains();
        } catch (err) { toast(err.message, "error"); }
    } else if (act === "delete") {
        confirmAction(`Delete ${name}? This removes its users and aliases too.`, async () => {
            await api("DELETE", `/domains/${encodeURIComponent(name)}`);
            toast(`Domain ${name} deleted`); viewDomains();
        }, { confirmLabel: "Delete", danger: true });
    }
}

function showDnsModal(name, records, certMessage) {
    const rows = records.map((r) => `
        <tr>
            <td><span class="badge neutral">${esc(r.type)}</span></td>
            <td class="mono">${esc(r.name)}</td>
            <td><div class="dns-val"><span>${esc(r.value)}</span><button class="ghost sm copy" data-copy="${esc(r.value)}">Copy</button></div>
                <div class="hint">${esc(r.purpose || "")}</div></td>
        </tr>`).join("");
    openModal({
        title: `DNS records — ${name}`,
        wide: true,
        html: `
            ${certMessage ? `<p class="hint" style="margin-top:0">${esc(certMessage)}</p>` : ""}
            <table class="dns-table"><thead><tr><th>Type</th><th>Name</th><th>Value</th></tr></thead><tbody>${rows}</tbody></table>
            <p class="hint">Set A and MX first, wait for propagation, then issue the certificate. Add SPF, DKIM and DMARC after.</p>`,
    });
    // Attach to the freshly created modal body, not the persistent #modal-root,
    // so the handler is discarded when the modal closes.
    $(".modal-body").addEventListener("click", (e) => {
        const c = e.target.closest("[data-copy]");
        if (c) { navigator.clipboard.writeText(c.dataset.copy).then(() => toast("Copied")); }
    });
}

async function showCheckModal(name) {
    openModal({ title: `Deliverability check — ${name}`, html: `<div class="empty"><span class="spinner" style="border-color:#ccc;border-top-color:var(--accent)"></span> Looking up live DNS…</div>` });
    try {
        const items = await api("GET", `/domains/${encodeURIComponent(name)}/check`);
        const html = items.map((it) => {
            const cls = it.ok === true ? "ok" : it.ok === false ? "bad" : "unk";
            return `<div class="check-item"><span class="dot ${cls}"></span><span class="c-name">${esc(it.check)}</span><span class="c-detail">${esc(it.detail)}</span></div>`;
        }).join("");
        $(".modal-body").innerHTML = html;
    } catch (err) {
        $(".modal-body").innerHTML = `<p class="muted">${esc(err.message)}</p>`;
    }
}

/* ============================================================
   Users
   ============================================================ */
async function viewUsers() {
    loading();
    if (!state.domains.length) {
        try { state.domains = await api("GET", "/domains"); } catch (e) { return errorState(e); }
    }
    const filter = state._userFilter || "";
    let users, usage = {};
    try {
        [users, usage] = await Promise.all([
            api("GET", `/users${filter ? `?domain=${encodeURIComponent(filter)}` : ""}`),
            api("GET", "/users/usage").catch(() => ({})),
        ]);
    } catch (e) { return errorState(e); }

    const domainOpts = `<option value="">All domains</option>` +
        state.domains.map((d) => `<option value="${esc(d.name)}" ${d.name === filter ? "selected" : ""}>${esc(d.name)}</option>`).join("");

    const usageCell = (u) => {
        const used = usage[u.email] ? usage[u.email].used_mb : null;
        if (!u.quota_mb) {
            return used != null ? `${used} MB <span class="muted">/ ∞</span>` : '<span class="muted">unlimited</span>';
        }
        const pct = used != null ? Math.min(Math.round(used / u.quota_mb * 100), 100) : 0;
        const kind = pct >= 90 ? "bad" : pct >= 75 ? "warn" : "";
        return `<div class="bar mini" style="margin-bottom:3px"><div class="bar-fill ${kind}" style="width:${pct}%"></div></div>
            <span class="muted" style="font-size:12px">${used != null ? used : "?"} / ${u.quota_mb} MB</span>`;
    };

    const rows = users.length ? users.map((u) => `
        <tr>
            <td><strong>${esc(u.email)}</strong></td>
            <td>${statusBadge(u.active)}</td>
            <td style="min-width:140px">${usageCell(u)}</td>
            <td>${u.autoreply ? '<span class="badge ok">on</span>' : '<span class="badge neutral">off</span>'}</td>
            <td class="actions">
                <button class="ghost sm" data-act="password" data-email="${esc(u.email)}">Password</button>
                <button class="ghost sm" data-act="quota" data-email="${esc(u.email)}" data-quota="${u.quota_mb}">Quota</button>
                <button class="ghost sm" data-act="autoreply" data-email="${esc(u.email)}">Auto-reply</button>
                <button class="ghost sm" data-act="toggle" data-email="${esc(u.email)}" data-active="${u.active}">${u.active ? "Disable" : "Enable"}</button>
                <button class="danger sm" data-act="delete" data-email="${esc(u.email)}">Delete</button>
            </td>
        </tr>`).join("") : `<tr><td colspan="5" class="empty">No users.</td></tr>`;

    $("#content").innerHTML = `
        <div class="card">
            <div class="card-head"><h3>Add user</h3></div>
            <div class="card-body">
                <form class="inline-form" id="add-user">
                    <div class="field"><label>Email</label><input id="u-email" placeholder="info@example.com"></div>
                    <div class="field"><label>Password</label><input id="u-pass" type="password"></div>
                    <div class="field" style="flex:0 0 130px"><label>Quota (MB)</label><input id="u-quota" type="number" value="0" min="0"></div>
                    <button type="submit">Add user</button>
                </form>
                <p class="hint" style="margin:10px 0 0">Quota 0 means unlimited. The domain must exist first.</p>
            </div>
        </div>
        <div class="card">
            <div class="card-head">
                <h3>Users</h3>
                <div style="width:220px"><select id="u-filter">${domainOpts}</select></div>
            </div>
            <table><thead><tr><th>Email</th><th>Status</th><th>Usage</th><th>Auto-reply</th><th></th></tr></thead><tbody>${rows}</tbody></table>
        </div>`;

    $("#u-filter").addEventListener("change", (e) => { state._userFilter = e.target.value; viewUsers(); });

    $("#add-user").addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = $("#u-email").value.trim();
        const password = $("#u-pass").value;
        const quota_mb = parseInt($("#u-quota").value || "0", 10);
        const btn = e.submitter; btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>';
        try {
            await api("POST", "/users", { email, password, quota_mb });
            toast(`User ${email} added`); viewUsers();
        } catch (err) { toast(err.message, "error"); btn.disabled = false; btn.textContent = "Add user"; }
    });

    $("#content").addEventListener("click", onUserAction);
}

async function onUserAction(e) {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const email = btn.dataset.email;
    const act = btn.dataset.act;

    if (act === "password") {
        openModal({
            title: `Change password — ${email}`,
            fields: [{ name: "password", label: "New password", type: "password" }],
            confirmLabel: "Update",
            onConfirm: async (v) => {
                if (!v.password) throw new Error("Password is required");
                await api("PUT", `/users/${encodeURIComponent(email)}/password`, { password: v.password });
                toast("Password updated");
            },
        });
    } else if (act === "quota") {
        openModal({
            title: `Set quota — ${email}`,
            fields: [{ name: "quota_mb", label: "Quota (MB)", type: "number", value: btn.dataset.quota, hint: "0 means unlimited" }],
            confirmLabel: "Save",
            onConfirm: async (v) => {
                await api("PUT", `/users/${encodeURIComponent(email)}/quota`, { quota_mb: parseInt(v.quota_mb || "0", 10) });
                toast("Quota updated"); viewUsers();
            },
        });
    } else if (act === "autoreply") {
        openModal({
            title: `Auto-reply — ${email}`,
            fields: [
                { name: "active", label: "Enable auto-reply", type: "checkbox" },
                { name: "subject", label: "Subject", placeholder: "Out of office" },
                { name: "text", label: "Message", type: "textarea", placeholder: "I am away until…" },
            ],
            confirmLabel: "Save",
            onConfirm: async (v) => {
                await api("PUT", `/users/${encodeURIComponent(email)}/autoreply`, { active: v.active, subject: v.subject, text: v.text });
                toast("Auto-reply saved"); viewUsers();
            },
        });
    } else if (act === "toggle") {
        const active = btn.dataset.active === "true";
        try {
            await api("POST", `/users/${encodeURIComponent(email)}/${active ? "disable" : "enable"}`);
            toast(`User ${active ? "disabled" : "enabled"}`); viewUsers();
        } catch (err) { toast(err.message, "error"); }
    } else if (act === "delete") {
        confirmAction(`Delete ${email}? The mailbox stays on disk but the account is removed.`, async () => {
            await api("DELETE", `/users/${encodeURIComponent(email)}`);
            toast(`User ${email} deleted`); viewUsers();
        }, { confirmLabel: "Delete", danger: true });
    }
}

/* ============================================================
   Aliases
   ============================================================ */
async function viewAliases() {
    loading();
    let aliases;
    try { aliases = await api("GET", "/aliases"); }
    catch (e) { return errorState(e); }

    const rows = aliases.length ? aliases.map((a) => `
        <tr>
            <td class="mono">${esc(a.address)}</td>
            <td>→</td>
            <td class="mono">${esc(a.goto)}</td>
            <td class="actions">
                <button class="danger sm" data-act="delete" data-address="${esc(a.address)}" data-goto="${esc(a.goto)}">Delete</button>
            </td>
        </tr>`).join("") : `<tr><td colspan="4" class="empty">No aliases.</td></tr>`;

    $("#content").innerHTML = `
        <div class="card">
            <div class="card-head"><h3>Add alias / forwarding</h3></div>
            <div class="card-body">
                <form class="inline-form" id="add-alias">
                    <div class="field"><label>Address</label><input id="a-address" placeholder="info@example.com or @example.com"></div>
                    <div class="field"><label>Forward to</label><input id="a-goto" placeholder="user@example.org"></div>
                    <div class="field checkbox-row" style="flex:0 0 auto;padding-bottom:10px">
                        <input type="checkbox" id="a-keep"><label for="a-keep">Keep a copy</label>
                    </div>
                    <button type="submit">Add alias</button>
                </form>
                <p class="hint" style="margin:10px 0 0">Use <span class="mono">@example.com</span> for a domain catch-all. "Keep a copy" only works when the address is a real mailbox.</p>
            </div>
        </div>
        <div class="card">
            <div class="card-head"><h3>Aliases</h3><span class="muted">${aliases.length} total</span></div>
            <table><thead><tr><th>Address</th><th></th><th>Target</th><th></th></tr></thead><tbody>${rows}</tbody></table>
        </div>`;

    $("#add-alias").addEventListener("submit", async (e) => {
        e.preventDefault();
        const address = $("#a-address").value.trim();
        const goto = $("#a-goto").value.trim();
        const keep_copy = $("#a-keep").checked;
        const btn = e.submitter; btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>';
        try {
            await api("POST", "/aliases", { address, goto, keep_copy });
            toast("Alias added"); viewAliases();
        } catch (err) { toast(err.message, "error"); btn.disabled = false; btn.textContent = "Add alias"; }
    });

    $("#content").addEventListener("click", (e) => {
        const btn = e.target.closest('button[data-act="delete"]');
        if (!btn) return;
        const { address, goto } = btn.dataset;
        confirmAction(`Remove forwarding ${address} → ${goto}?`, async () => {
            await api("DELETE", `/aliases?address=${encodeURIComponent(address)}&goto=${encodeURIComponent(goto)}`);
            toast("Alias removed"); viewAliases();
        }, { confirmLabel: "Delete", danger: true });
    });
}

/* ============================================================
   Certificates
   ============================================================ */
async function viewCerts() {
    loading();
    let s;
    try { s = await api("GET", "/status"); }
    catch (e) { return errorState(e); }

    const rows = s.certs.length ? s.certs.map((c) => {
        let badge;
        if (!c.valid) badge = '<span class="badge off">missing</span>';
        else if (c.days_left < 15) badge = `<span class="badge warn-b">${c.days_left}d left</span>`;
        else badge = `<span class="badge ok">${c.days_left}d left</span>`;
        return `<tr>
            <td><strong>${esc(c.domain)}</strong></td>
            <td>${badge}</td>
            <td class="muted">${c.valid ? esc(c.expires) : "-"}</td>
            <td class="actions"><button class="ghost sm" data-act="renew" data-domain="${esc(c.domain)}">${c.valid ? "Renew now" : "Issue"}</button></td>
        </tr>`;
    }).join("") : `<tr><td colspan="4" class="empty">No domains yet. Add one under Domains.</td></tr>`;

    $("#content").innerHTML = `
        <div class="card">
            <div class="card-head">
                <h3>Certificates</h3>
                <button class="ghost sm" id="renew-all">Renew all</button>
            </div>
            <table><thead><tr><th>Domain</th><th>Status</th><th>Expires</th><th></th></tr></thead><tbody>${rows}</tbody></table>
        </div>
        <p class="hint">Certificates renew automatically twice a day. "Renew now" re-checks one domain (issues if missing, renews if due). HTTP-01 needs <span class="mono">mail.&lt;domain&gt;</span> to resolve to the server; it restarts HAProxy briefly.</p>`;

    $("#renew-all").addEventListener("click", async (e) => {
        const btn = e.currentTarget; btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>';
        try { await api("POST", "/certs/renew"); toast("Renewal finished"); viewCerts(); }
        catch (err) { toast(err.message, "error"); btn.disabled = false; btn.textContent = "Renew all"; }
    });

    const table = $("#content table");
    if (table) table.addEventListener("click", async (e) => {
        const btn = e.target.closest('button[data-act="renew"]');
        if (!btn) return;
        const domain = btn.dataset.domain;
        btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>';
        try {
            await api("POST", `/certs/issue/${encodeURIComponent(domain)}`);
            toast(`Certificate updated for ${domain}`);
            viewCerts();
        } catch (err) {
            toast(err.message, "error");
            btn.disabled = false; btn.textContent = "Renew now";
        }
    });
}

/* ============================================================
   Dashboard
   ============================================================ */
function fmtBytes(b) {
    if (b == null) return "-";
    const u = ["B", "KB", "MB", "GB", "TB"];
    let i = 0, n = b;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(1)} ${u[i]}`;
}

// dependency-free SVG donut gauge (0-100%)
function donut(percent, label, sub = "") {
    const p = Math.max(0, Math.min(100, percent || 0));
    const r = 42, circ = 2 * Math.PI * r;
    const off = circ * (1 - p / 100);
    const color = p >= 90 ? "var(--danger)" : p >= 75 ? "var(--warn)" : "var(--accent)";
    return `<div class="donut">
        <svg viewBox="0 0 100 100">
            <circle class="donut-bg" cx="50" cy="50" r="${r}"></circle>
            <circle class="donut-fg" cx="50" cy="50" r="${r}" stroke="${color}" stroke-dasharray="${circ.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}"></circle>
            <text class="donut-num" x="50" y="54" text-anchor="middle">${p.toFixed(0)}%</text>
        </svg>
        <div class="donut-label">${esc(label)}</div>
        ${sub ? `<div class="donut-sub muted">${esc(sub)}</div>` : ""}
    </div>`;
}

async function refreshStats() {
    let st;
    try { st = await api("GET", "/stats"); }
    catch { return; }
    const cpuEl = $("#donut-cpu"), memEl = $("#donut-mem"), listEl = $("#ctr-stats");
    if (!cpuEl || !memEl || !listEl) return;   // navigated away mid-request
    cpuEl.innerHTML = donut(st.totals.cpu, "CPU", `${st.cpus} core${st.cpus > 1 ? "s" : ""}`);
    memEl.innerHTML = donut(st.totals.mem, "Memory", "of host");
    listEl.innerHTML = st.containers.map((c) => `
        <div class="ctr">
            <span class="ctr-name">${esc(c.name)}</span>
            <div class="ctr-bar"><span class="ctr-tag">CPU</span><div class="bar mini"><div class="bar-fill" style="width:${Math.min(c.cpu, 100)}%"></div></div><span class="ctr-pct">${c.cpu}%</span></div>
            <div class="ctr-bar"><span class="ctr-tag">MEM</span><div class="bar mini"><div class="bar-fill" style="width:${Math.min(c.mem, 100)}%"></div></div><span class="ctr-pct">${esc(c.mem_usage)}</span></div>
        </div>`).join("");
}

async function viewDashboard() {
    loading();
    let s;
    try { s = await api("GET", "/status"); }
    catch (e) { return errorState(e); }

    const stat = (label, value, sub = "", kind = "") =>
        `<div class="stat ${kind}"><div class="stat-val">${value}</div><div class="stat-label">${esc(label)}</div>${sub ? `<div class="stat-sub">${esc(sub)}</div>` : ""}</div>`;

    const services = s.services.map((sv) =>
        `<div class="svc"><span class="dot ${sv.up ? "ok" : "bad"}"></span><span class="svc-name">${esc(sv.name)}</span><span class="svc-status muted">${esc(sv.status)}</span></div>`).join("");

    const certRows = s.certs.length ? s.certs.map((c) => {
        let badge;
        if (!c.valid) badge = '<span class="badge off">missing</span>';
        else if (c.days_left != null && c.days_left < 15) badge = `<span class="badge warn-b">${c.days_left}d left</span>`;
        else badge = `<span class="badge ok">${c.days_left}d left</span>`;
        return `<tr><td><strong>${esc(c.domain)}</strong></td><td>${badge}</td><td class="muted">${c.valid ? esc(c.expires) : "-"}</td></tr>`;
    }).join("") : `<tr><td colspan="3" class="empty">No domains yet.</td></tr>`;

    const d = s.disk;

    $("#content").innerHTML = `
        <div class="stats">
            ${stat("Domains", s.domains.active, `${s.domains.total} total`)}
            ${stat("Users", s.users)}
            ${stat("Aliases", s.aliases)}
            ${stat("Mail queue", s.queue.count, s.queue.count ? "needs attention" : "empty", s.queue.count ? "warn" : "")}
        </div>
        <div class="card">
            <div class="card-head"><h3>Resources</h3><span class="muted">live · refreshes every 5s</span></div>
            <div class="card-body">
                <div class="donuts">
                    <div id="donut-cpu">${donut(0, "CPU", "…")}</div>
                    <div id="donut-mem">${donut(0, "Memory", "…")}</div>
                    ${donut(d.percent, "Disk", `${fmtBytes(d.used)} / ${fmtBytes(d.total)}`)}
                </div>
                <div id="ctr-stats" class="ctr-stats"><div class="empty"><span class="spinner" style="border-color:#ccc;border-top-color:var(--accent)"></span></div></div>
            </div>
        </div>
        <div class="grid-2">
            <div class="card">
                <div class="card-head"><h3>Services</h3></div>
                <div class="card-body svc-grid">${services}</div>
            </div>
            <div class="card">
                <div class="card-head"><h3>Certificates</h3><span class="muted">auto-renewed</span></div>
                <table><thead><tr><th>Domain</th><th>Status</th><th>Expires</th></tr></thead><tbody>${certRows}</tbody></table>
            </div>
        </div>`;

    refreshStats();
    state._statsTimer = setInterval(refreshStats, 5000);
}

/* ============================================================
   Mail queue
   ============================================================ */
async function viewQueue() {
    loading();
    let items;
    try { items = await api("GET", "/queue"); }
    catch (e) { return errorState(e); }

    const senderDomain = (m) => ((m.sender || "").split("@")[1] || "—").toLowerCase();
    const domains = [...new Set(items.map(senderDomain))].sort();

    const renderRows = (list) => list.length ? list.map((m) => `
        <tr>
            <td class="mono">${esc(m.id)}</td>
            <td><span class="badge neutral">${esc(m.queue)}</span></td>
            <td class="mono">${esc(m.sender)}</td>
            <td class="mono">${esc((m.recipients || []).join(", "))}</td>
            <td class="muted" style="max-width:260px;word-break:break-word">${esc(m.reason || "")}</td>
            <td class="actions"><button class="danger sm" data-act="del" data-id="${esc(m.id)}">Delete</button></td>
        </tr>`).join("") : `<tr><td colspan="6" class="empty">No messages.</td></tr>`;

    $("#content").innerHTML = `
        <div class="card">
            <div class="card-head">
                <h3>Mail queue</h3>
                <div class="row-gap">
                    <span class="muted" id="q-count">${items.length} message(s)</span>
                    ${domains.length > 1 ? `<select id="q-filter" style="width:auto"><option value="">All domains</option>${domains.map((d) => `<option value="${esc(d)}">${esc(d)}</option>`).join("")}</select>` : ""}
                    <button class="ghost sm" id="q-flush">Flush all</button>
                    ${items.length ? '<button class="danger sm" id="q-delall">Delete all</button>' : ""}
                </div>
            </div>
            <table><thead><tr><th>ID</th><th>Queue</th><th>Sender</th><th>Recipients</th><th>Reason</th><th></th></tr></thead><tbody id="q-body">${items.length ? renderRows(items) : '<tr><td colspan="6" class="empty">Queue is empty 🎉</td></tr>'}</tbody></table>
        </div>
        <p class="hint">Filter by the sending domain. Flush retries delivery now; deferred messages are retried automatically by Postfix until they expire.</p>`;

    const qFilter = $("#q-filter");
    if (qFilter) qFilter.addEventListener("change", () => {
        const dom = qFilter.value;
        const list = dom ? items.filter((m) => senderDomain(m) === dom) : items;
        $("#q-body").innerHTML = renderRows(list);
        $("#q-count").textContent = `${list.length} message(s)`;
    });

    $("#q-flush").addEventListener("click", async (e) => {
        const b = e.currentTarget; b.disabled = true; b.innerHTML = '<span class="spinner"></span>';
        try { await api("POST", "/queue/flush"); toast("Queue flush triggered"); viewQueue(); }
        catch (err) { toast(err.message, "error"); b.disabled = false; b.textContent = "Flush all"; }
    });

    const delAll = $("#q-delall");
    if (delAll) delAll.addEventListener("click", () => {
        confirmAction("Delete ALL queued messages? This cannot be undone.", async () => {
            await api("DELETE", "/queue/ALL"); toast("Queue cleared"); viewQueue();
        }, { confirmLabel: "Delete all", danger: true });
    });

    // delegate row deletes on the table (fresh node each render, so no stacking)
    const table = $("#content table");
    if (table) table.addEventListener("click", (e) => {
        const btn = e.target.closest('button[data-act="del"]');
        if (!btn) return;
        confirmAction(`Delete message ${btn.dataset.id}?`, async () => {
            await api("DELETE", `/queue/${encodeURIComponent(btn.dataset.id)}`); toast("Message deleted"); viewQueue();
        }, { confirmLabel: "Delete", danger: true });
    });
}

/* ============================================================
   Logs
   ============================================================ */
async function viewLogs() {
    const src = state._logSource || "postfix";
    const q = state._logQuery || "";
    $("#content").innerHTML = `
        <div class="card">
            <div class="card-head">
                <h3>Logs</h3>
                <div class="row-gap">
                    <select id="l-source" style="width:auto">
                        <option value="postfix" ${src === "postfix" ? "selected" : ""}>Postfix (SMTP)</option>
                        <option value="dovecot" ${src === "dovecot" ? "selected" : ""}>Dovecot (IMAP)</option>
                    </select>
                    <input id="l-q" placeholder="search: email, message-id…" value="${esc(q)}" style="width:220px">
                    <button class="ghost sm" id="l-go">Search</button>
                    <label class="row-gap" style="gap:5px;font-weight:500;cursor:pointer"><input type="checkbox" id="l-live" style="width:auto"> Live</label>
                    <label class="row-gap" style="gap:5px;font-weight:500;cursor:pointer"><input type="checkbox" id="l-noise" style="width:auto"> Show health checks</label>
                </div>
            </div>
            <div class="card-body"><pre class="logbox" id="l-out"><span class="muted">Loading…</span></pre></div>
        </div>
        <p class="hint">Last 300 lines (or matches when you search). HAProxy health-check chatter is hidden by default. Tip: paste a recipient or message-id to trace one mail.</p>`;

    const load = async (quiet) => {
        const out = $("#l-out");
        if (!out) return;
        if (!quiet) out.innerHTML = '<span class="muted">Loading…</span>';
        const noise = $("#l-noise").checked ? "&noise=1" : "";
        try {
            const r = await api("GET", `/logs?source=${encodeURIComponent($("#l-source").value)}&q=${encodeURIComponent($("#l-q").value.trim())}&limit=300${noise}`);
            const atBottom = out.scrollTop + out.clientHeight >= out.scrollHeight - 30;
            out.textContent = r.lines.length ? r.lines.join("\n") : "No matching log lines.";
            if (atBottom || !quiet) out.scrollTop = out.scrollHeight;
        } catch (e) { if (!quiet) out.textContent = e.message; }
    };

    $("#l-source").addEventListener("change", () => { state._logSource = $("#l-source").value; load(); });
    $("#l-go").addEventListener("click", () => { state._logQuery = $("#l-q").value.trim(); load(); });
    $("#l-noise").addEventListener("change", () => load());
    $("#l-q").addEventListener("keydown", (e) => { if (e.key === "Enter") { state._logQuery = $("#l-q").value.trim(); load(); } });
    $("#l-live").addEventListener("change", (e) => {
        if (state._logTimer) { clearInterval(state._logTimer); state._logTimer = null; }
        if (e.target.checked) state._logTimer = setInterval(() => load(true), 3000);
    });
    load();
}

/* ============================================================
   Security (fail2ban)
   ============================================================ */
async function viewSecurity() {
    loading();
    let jails;
    try { jails = await api("GET", "/fail2ban"); }
    catch (e) { return errorState(e); }

    const cards = jails.length ? jails.map((j) => `
        <div class="card">
            <div class="card-head"><h3>${esc(j.jail)}</h3><span class="muted">${j.count} banned</span></div>
            <div class="card-body">
                ${j.banned.length
                    ? `<div class="chips">${j.banned.map((ip) => `<span class="chip">${esc(ip)}<button class="chip-x" data-ip="${esc(ip)}" title="unban">&times;</button></span>`).join("")}</div>`
                    : '<p class="muted" style="margin:0">No banned IPs.</p>'}
            </div>
        </div>`).join("") : '<div class="card"><div class="card-body"><p class="muted" style="margin:0">No active jails.</p></div></div>';

    $("#content").innerHTML = `${cards}<p class="hint">fail2ban bans IPs that fail SMTP or IMAP login too many times. Click × to unban an address.</p>`;

    $("#content").querySelectorAll(".chip-x").forEach((b) => b.addEventListener("click", () => {
        const ip = b.dataset.ip;
        confirmAction(`Unban ${ip}?`, async () => {
            await api("DELETE", `/fail2ban/banned/${encodeURIComponent(ip)}`);
            toast(`Unbanned ${ip}`); viewSecurity();
        }, { confirmLabel: "Unban" });
    }));
}

/* ---------- domain deliverability badges (lazy) ---------- */
function loadDomainBadges() {
    document.querySelectorAll(".dcheck").forEach(async (cell) => {
        const name = cell.dataset.domain;
        cell.innerHTML = '<span class="spinner" style="border-color:#ddd;border-top-color:var(--accent);width:12px;height:12px"></span>';
        try {
            const items = await api("GET", `/domains/${encodeURIComponent(name)}/check`);
            const checkable = items.filter((i) => i.ok !== null);
            const total = checkable.length;
            const okCount = checkable.filter((i) => i.ok === true).length;
            const cls = okCount === total && total > 0 ? "ok" : okCount >= total - 1 ? "warn-b" : "off";
            const tip = items.map((i) => `${i.check}: ${i.ok === true ? "ok" : i.ok === false ? "fail" : "?"}`).join(" · ");
            cell.innerHTML = `<span class="badge ${cls}" title="${esc(tip)}">${okCount}/${total} ✓</span>`;
        } catch {
            cell.innerHTML = '<span class="muted">—</span>';
        }
    });
}

/* ---------- shared error state ---------- */
function errorState(err) {
    $("#content").innerHTML = `<div class="card"><div class="card-body"><p class="muted">Could not load data: ${esc(err.message)}</p><button class="ghost" onclick="go(state.view)">Retry</button></div></div>`;
}

/* ============================================================
   Boot
   ============================================================ */
if (getToken()) renderShell();
else renderLogin();
