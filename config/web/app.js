"use strict";

/* ============================================================
   Mail Platform - admin web UI
   Talks to the control-plane REST API through nginx at /api/.
   ============================================================ */

const API = "/api";
const TOKEN_KEY = "mp_token";

const state = {
    view: "domains",
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
    { key: "domains", label: "Domains", ico: "🌐" },
    { key: "users", label: "Users", ico: "👤" },
    { key: "aliases", label: "Aliases", ico: "↪" },
    { key: "certs", label: "Certificates", ico: "🔒" },
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
    // #content persists across navigation; replace it so delegated click
    // listeners from the previous view do not stack up on the same node.
    const old = $("#content");
    old.replaceWith(old.cloneNode(false));
    document.querySelectorAll(".nav a[data-view]").forEach((a) => a.classList.toggle("active", a.dataset.view === view));
    $("#page-title").textContent = NAV.find((n) => n.key === view).label;
    $("#topbar-actions").innerHTML = "";
    const views = { domains: viewDomains, users: viewUsers, aliases: viewAliases, certs: viewCerts };
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
            <td class="actions">
                <button class="ghost sm" data-act="dns" data-name="${esc(d.name)}">DNS</button>
                <button class="ghost sm" data-act="check" data-name="${esc(d.name)}">Check</button>
                <button class="ghost sm" data-act="toggle" data-name="${esc(d.name)}" data-active="${d.active}">${d.active ? "Disable" : "Enable"}</button>
                <button class="danger sm" data-act="delete" data-name="${esc(d.name)}">Delete</button>
            </td>
        </tr>`).join("") : `<tr><td colspan="3" class="empty">No domains yet. Add one above.</td></tr>`;

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
            <table><thead><tr><th>Name</th><th>Status</th><th></th></tr></thead><tbody>${rows}</tbody></table>
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
    let users;
    try { users = await api("GET", `/users${filter ? `?domain=${encodeURIComponent(filter)}` : ""}`); }
    catch (e) { return errorState(e); }

    const domainOpts = `<option value="">All domains</option>` +
        state.domains.map((d) => `<option value="${esc(d.name)}" ${d.name === filter ? "selected" : ""}>${esc(d.name)}</option>`).join("");

    const rows = users.length ? users.map((u) => `
        <tr>
            <td><strong>${esc(u.email)}</strong></td>
            <td>${statusBadge(u.active)}</td>
            <td>${u.quota_mb ? `${u.quota_mb} MB` : '<span class="muted">unlimited</span>'}</td>
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
            <table><thead><tr><th>Email</th><th>Status</th><th>Quota</th><th>Auto-reply</th><th></th></tr></thead><tbody>${rows}</tbody></table>
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
    if (!state.domains.length) {
        try { state.domains = await api("GET", "/domains"); } catch (e) { return errorState(e); }
    }
    const opts = state.domains.map((d) => `<option value="${esc(d.name)}">${esc(d.name)}</option>`).join("")
        || `<option value="">No domains yet</option>`;

    $("#content").innerHTML = `
        <div class="card">
            <div class="card-head"><h3>Issue certificate</h3></div>
            <div class="card-body">
                <form class="inline-form" id="issue-cert">
                    <div class="field"><label>Domain</label><select id="c-domain">${opts}</select></div>
                    <button type="submit" ${state.domains.length ? "" : "disabled"}>Issue</button>
                </form>
                <p class="hint" style="margin:10px 0 0">HTTP-01 needs <span class="mono">mail.&lt;domain&gt;</span> to resolve to the server first. Run after DNS propagates.</p>
            </div>
        </div>
        <div class="card">
            <div class="card-head"><h3>Renew all</h3></div>
            <div class="card-body">
                <p class="muted" style="margin:0 0 14px">Renew every certificate that is due. Restarts HAProxy briefly.</p>
                <button id="renew-all">Renew all certificates</button>
            </div>
        </div>`;

    $("#issue-cert").addEventListener("submit", async (e) => {
        e.preventDefault();
        const domain = $("#c-domain").value;
        if (!domain) return;
        const btn = e.submitter; btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>';
        try {
            await api("POST", `/certs/issue/${encodeURIComponent(domain)}`);
            toast(`Certificate issued for ${domain}`);
        } catch (err) { toast(err.message, "error"); }
        btn.disabled = false; btn.textContent = "Issue";
    });

    $("#renew-all").addEventListener("click", async (e) => {
        const btn = e.currentTarget; btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Renewing…';
        try {
            await api("POST", "/certs/renew");
            toast("Renewal finished");
        } catch (err) { toast(err.message, "error"); }
        btn.disabled = false; btn.textContent = "Renew all certificates";
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
