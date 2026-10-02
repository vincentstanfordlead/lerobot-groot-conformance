import { runAll, GROOT_SHA } from "./checks.js";
import { HubView, FetchError, parseDatasetId, withFile, LIST_CAP } from "./hub.js";
import { draftModality, formatModality } from "./draft.js";
import { classifyEmbodiment } from "./embodiment.js";
import { GROUPS, CHECKS, VERDICTS, sourceUrl } from "./explain.js";
import { renderLeaderboard, renderValidation } from "./preview.js";

const NAME = "Robot Data Smog Check";
const REPO_URL = "https://github.com/vincentstanfordlead/lerobot-groot-conformance";
// One example per outcome, so a click shows something different. The dot is the traffic light for what the inspection found.
const EXAMPLES = [
  { id: "lerobot/aloha_sim_transfer_cube_human", tone: "red", says: "two steps away" },
  { id: "youliangtan/tictac-bot", tone: "yellow", says: "one step away" },
  { id: "Kovavavvavava/peg_insertion_onehouse_fixed", tone: "green", says: "passes every static check" },
];
// One traffic light for every verdict, used by the chips, history list, badges and mascot:
// green = passes, yellow = one fix away, red = more than one fix or blocked.
const tn = (tone) => ({ good: "good", close: "close", warn: "close", mid: "bad", bad: "bad" }[tone] ?? "bad");
const chipHtml = ({ id, tone, says }) => `<button class="chip" data-ex="${id}" title="${id}: ${says}"><i class="dot ${tone}" aria-hidden="true"></i>${esc(id.split("/")[1])}<span class="sr"> (${says})</span></button>`;
const STORE = "smogcheck.runs.v1";
// Open-weight models that read LeRobot datasets. Only GR00T has checks today; the rest are listed so people can see what's coming.
const MODELS = [
  { id: "groot", name: "NVIDIA GR00T N1.7", short: "GR00T N1.7", by: "NVIDIA", ready: true },
  { id: "pi05", name: "π0.5 (openpi)", short: "π0.5", by: "Physical Intelligence" },
  { id: "pi0", name: "π0 / π0-FAST (openpi)", short: "π0 / π0-FAST", by: "Physical Intelligence" },
  { id: "smolvla", name: "SmolVLA", short: "SmolVLA", by: "Hugging Face" },
  { id: "xvla", name: "X-VLA", short: "X-VLA", by: "Tsinghua AIR" },
  { id: "wall-oss", name: "WALL-OSS", short: "WALL-OSS", by: "X Square Robot" },
  { id: "go1", name: "GO-1", short: "GO-1", by: "AgiBot" },
];
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const app = $("#app");

// Model picker: a custom dropdown so the closed button can say "+6 coming soon" and the list can group ready and upcoming models.
const SOON = MODELS.filter((m) => !m.ready).length;
function modelPicker() {
  const cur = MODELS[0];
  return `<div class="mp" id="mp"><button type="button" class="mp-btn" id="mpBtn" aria-haspopup="listbox" aria-expanded="false" aria-controls="mpMenu">
      <span class="mp-t"><small>Model · +${SOON} coming soon</small><b>${esc(cur.short)}</b></span>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></button>
    <ul class="mp-menu" id="mpMenu" role="listbox" aria-label="Model to check against" hidden>
      <li class="hd" role="presentation">Check readiness for</li>
      ${MODELS.filter((m) => m.ready).map((m) => `<li role="option" aria-selected="true" class="on" data-m="${m.id}">${esc(m.name)}<span>✓</span></li>`).join("")}
      <li class="hd" role="presentation">Coming soon</li>
      ${MODELS.filter((m) => !m.ready).map((m) => `<li role="option" aria-disabled="true" data-m="${m.id}">${esc(m.short)}<em>${esc(m.by)}</em></li>`).join("")}
    </ul></div>`;
}
function bindModelPicker(root) {
  const btn = $("#mpBtn", root), menu = $("#mpMenu", root);
  const set = (open) => { menu.hidden = !open; btn.setAttribute("aria-expanded", String(open)); };
  btn.onclick = (e) => { e.stopPropagation(); set(menu.hidden); };
  menu.onclick = (e) => {
    const li = e.target.closest("li[data-m]");
    if (!li) return;
    if (li.getAttribute("aria-disabled")) toast(`${li.firstChild.textContent} is coming soon. GR00T N1.7 is the only model checked today.`);
    set(false);
  };
  root.addEventListener("keydown", (e) => { if (e.key === "Escape" && !menu.hidden) { e.stopPropagation(); set(false); btn.focus(); } });
  document.addEventListener("click", (e) => { if (!root.contains(e.target)) set(false); });
}

// ---------------------------------------------------------------- art: brick-robot mascot

// One green brick head with four moods: look (inspecting), happy (ready), work (needs work), sad (blocked).
// Mood shows in the eyes, mouth, antenna, backdrop colour and a small prop, so they read apart at a glance.
function mascot(mood = "happy", { disc = true, cls = "", light = null } = {}) {
  const LB = { green: "#DDF3E6", yellow: "#FFF3C4", red: "#FBE0E0" }, LC = { green: "#00A650", yellow: "#FFCF00", red: "#E3000B" };
  const bg = LB[light] ?? { look: "#EEF0F2", happy: "#DDF3E6", work: "#FFF3C4", sad: "#FBE0E0" }[mood];
  const ant = mood === "sad"
    ? `<path d="M50 24V16l8-5" stroke="#1b1b1b" stroke-width="3" fill="none" stroke-linecap="round"/><circle cx="59" cy="11" r="4" fill="#9aa0a6"/>`
    : `<path d="M50 24V12" stroke="#1b1b1b" stroke-width="3" stroke-linecap="round"/><circle cx="50" cy="11" r="4.5" fill="${LC[light] ?? { look: "#E3000B", happy: "#00A650", work: "#FFCF00" }[mood]}"/>`;
  const eyes = {
    look: `<circle cx="40" cy="48" r="6" fill="#fff"/><circle cx="60" cy="48" r="6" fill="#fff"/><circle cx="43" cy="48" r="3.4" fill="#1b1b1b"/><circle cx="63" cy="48" r="3.4" fill="#1b1b1b"/>`,
    happy: `<path d="M34 50q6 -8 12 0M54 50q6 -8 12 0" stroke="#1b1b1b" stroke-width="4" fill="none" stroke-linecap="round"/>`,
    work: `<circle cx="40" cy="48" r="4.5" fill="#1b1b1b"/><path d="M54 48h12" stroke="#1b1b1b" stroke-width="4" stroke-linecap="round"/>`,
    sad: `<path d="M35 43l9 9M44 43l-9 9M56 43l9 9M65 43l-9 9" stroke="#1b1b1b" stroke-width="3.6" stroke-linecap="round"/>`,
  }[mood];
  const mouth = {
    look: `<circle cx="50" cy="62" r="3.2" fill="#1b1b1b"/>`,
    happy: `<path d="M38 59q12 12 24 0z" fill="#1b1b1b"/>`,
    work: `<path d="M39 63q3.7 -4 7.3 0t7.3 0t7.3 0" stroke="#1b1b1b" stroke-width="3.4" fill="none" stroke-linecap="round"/>`,
    sad: `<path d="M39 67q11 -9 22 0" stroke="#1b1b1b" stroke-width="4" fill="none" stroke-linecap="round"/>`,
  }[mood];
  const prop = {
    look: `<path d="M84 72l7 8" stroke="#1b1b1b" stroke-width="4.5" stroke-linecap="round"/><circle cx="77" cy="64" r="11" fill="#dff1ff" fill-opacity=".75" stroke="#1b1b1b" stroke-width="3.5"/>`,
    happy: `<path d="M14 22l2 5 5 2-5 2-2 5-2-5-5-2 5-2zM86 18l1.5 4 4 1.5-4 1.5-1.5 4-1.5-4-4-1.5 4-1.5z" fill="#FFCF00"/>`,
    work: `<path d="M80 78l10 -16" stroke="#555" stroke-width="5" stroke-linecap="round"/><path d="M86 58a6 6 0 1 1 9 4" stroke="#555" stroke-width="5" fill="none" stroke-linecap="round"/>`,
    sad: `<circle cx="74" cy="16" r="5" fill="#b5bac0"/><circle cx="83" cy="9" r="6.5" fill="#c9cdd2"/><circle cx="93" cy="13" r="5" fill="#dadde1"/>`,
  }[mood];
  const tilt = mood === "work" ? ` transform="rotate(-9 50 50)"` : "";
  const label = { look: "inspecting", happy: "ready", work: "needs work", sad: "blocked" }[mood];
  return `<svg class="${cls}" viewBox="0 0 100 100" role="img" aria-label="Brick robot mascot, ${label}">
    ${disc ? `<circle cx="50" cy="52" r="46" fill="${bg}"/>` : ""}
    <g class="bob"${tilt}>${ant}<rect x="32" y="19" width="13" height="8" rx="2" fill="#00A650"/><rect x="55" y="19" width="13" height="8" rx="2" fill="#00A650"/>
    <rect x="22" y="26" width="56" height="52" rx="6" fill="#00A650"/><rect x="22" y="72" width="56" height="6" rx="2" fill="#007a3b"/>${eyes}${mouth}</g>${disc ? prop : ""}</svg>`;
}

const logoMark = () => mascot("happy", { disc: false });

// The readiness picture is the mascot's mood: ready = happy, fixable = wrench, blocked or not LeRobot = X eyes.
const MOOD = { READY: "happy", BLOCKED: "sad", NOT_LEROBOT: "sad" };
const gauge = (verdict, error = false) => mascot(error ? "sad" : MOOD[verdict] ?? "work",
  { cls: "verdict-art", light: error ? "red" : { good: "green", close: "yellow" }[tn(VERDICTS[verdict]?.tone)] ?? "red" });

const ICON = {
  pass: `<svg class="st" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#15803d"/><path d="M7.5 12.5l3 3 6-6.5" stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  fail: `<svg class="st" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="#c62828" stroke-width="2"/><path d="M9 9l6 6M15 9l-6 6" stroke="#c62828" stroke-width="2.2" stroke-linecap="round"/></svg>`,
  warn: `<svg class="st" viewBox="0 0 24 24"><path d="M12 3l10 18H2z" fill="#ffc400" stroke="#111" stroke-width="1.2" stroke-linejoin="round"/><path d="M12 10v5" stroke="#111" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="18" r="1.3" fill="#111"/></svg>`,
  skip: `<svg class="st" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="#9aa0a8" stroke-width="2" stroke-dasharray="3 3"/><path d="M8 12h8" stroke="#9aa0a8" stroke-width="2" stroke-linecap="round"/></svg>`,
  info: `<svg class="st" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#eaf0fe" stroke="#2563eb" stroke-width="1.6"/><path d="M12 11v6" stroke="#2563eb" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="7.5" r="1.3" fill="#2563eb"/></svg>`,
  scope: `<svg class="st" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#f3eefe" stroke="#6d28d9" stroke-width="1.6"/><path d="M12 7v6" stroke="#6d28d9" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="16.5" r="1.3" fill="#6d28d9"/></svg>`,
  robot: `<svg class="st" viewBox="0 0 24 24" fill="none" stroke="#111318" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 21h14M8 21v-3h8v3M12 18L8 11l7-4"/><circle cx="8" cy="11" r="1.6" fill="#ffc400"/><path d="M15 7l3-1.5M15.5 8.5l3 .5"/></svg>`,
  draft: `<svg class="st" viewBox="0 0 24 24" fill="none" stroke="#111318" stroke-width="1.8" stroke-linejoin="round"><path d="M6 3h9l4 4v14H6z" fill="#ffc400"/><path d="M15 3v4h4M9 12h7M9 16h5" stroke-linecap="round"/></svg>`,
  report: `<svg class="st" viewBox="0 0 24 24" fill="none" stroke="#111318" stroke-width="1.8" stroke-linecap="round"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>`,
  shield: `<svg class="st" viewBox="0 0 24 24"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" fill="none" stroke="#414754" stroke-width="1.8" stroke-linejoin="round"/></svg>`,
  rerun: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/></svg>`,
  trash: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>`,
  x: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>`,
  share: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>`,
  ext: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/></svg>`,
  plus: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>`,
  dl: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>`,
};

function checkStatus(c) {
  if (c.passed === true) return "pass";
  if (c.passed === null) return "skip";
  return c.level === "FAIL" ? "fail" : c.level === "WARN" ? "warn" : "info";
}

// ---------------------------------------------------------------- storage

function loadRuns() {
  try { return JSON.parse(localStorage.getItem(STORE)) || []; } catch { return []; }
}
function saveRuns(rs) {
  try { localStorage.setItem(STORE, JSON.stringify(rs.slice(0, 25))); } catch { /* private mode: no history */ }
}
let runs = loadRuns();

function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.append(t);
  setTimeout(() => t.remove(), 2200);
}

// ---------------------------------------------------------------- routing

function route() {
  const d = new URLSearchParams(location.search).get("d");
  if (d) {
    renderDashboard();
    const id = parseDatasetId(d);
    if (id) startRun(id);
    return;
  }
  if (location.hash === "#checks") renderDashboard();
  else if (location.hash === "#leaderboard") { document.title = `Leaderboard · ${NAME}`; renderLeaderboard(pageCtx()); }
  else if (location.hash === "#validation") { document.title = `Model Validation · ${NAME}`; renderValidation(pageCtx()); }
  else renderLanding();
}
window.addEventListener("popstate", route);
const pageCtx = () => ({ app, shell, esc, toast, mascot });
function go(hash) {
  history.pushState(null, "", location.pathname + hash);
  route();
}

const brand = (sub = true) => `${logoMark()}<span class="name">${NAME}${sub ? `<small>Robot dataset inspection</small>` : ""}</span>`;

// ---------------------------------------------------------------- landing

function renderLanding() {
  document.title = `${NAME}: is your robot dataset GR00T-ready?`;
  app.innerHTML = `
  <section class="landing">
    <nav class="topnav"><button class="logo" id="homeLogo">${brand()}</button>
      <div class="links"><button id="toChecks">My inspections${runs.length ? ` (${runs.length})` : ""}</button><button id="toBoard">Leaderboard <i class="soon-tag">coming soon</i></button><button id="toBuild">Model Validation <i class="soon-tag">coming soon</i></button><a href="${REPO_URL}" target="_blank" rel="noopener">How it works</a></div></nav>
    <div class="hero">
      <div>
        <div class="label">Pre-training inspection · Isaac-GR00T @${GROOT_SHA.slice(0, 7)}</div>
        <h1>Check your robot data <em>before</em> you train on it.</h1>
        <p class="lede">Paste a Hugging Face dataset link and pick a model. In seconds, see what GR00T's loader accepts, what's missing, and how to fix it.</p>
        <form class="console" id="heroForm" autocomplete="off">
          <label class="sr" for="heroIn">Hugging Face dataset link or id</label>
          <input id="heroIn" placeholder="huggingface.co/datasets/you/your-robot-data" spellcheck="false">
          ${modelPicker()}
          <button class="go-btn" type="submit">Run inspection</button>
        </form>
        <p class="hint" id="heroHint">Or try one:</p>
        <div class="chips">${EXAMPLES.map(chipHtml).join("")}</div>
      </div>
      <div class="hero-art">${mascot("happy")}</div>
    </div>
    <div class="readouts">
      <div><b>28</b><span>checks, each cited to a line of GR00T's code</span></div>
      <div><b>~3 s</b><span>metadata only, read in your browser</span></div>
      <div><b>0</b><span>sign-ins, uploads or video downloads</span></div>
      <div><b>562</b><span>public datasets in the audit behind it</span></div>
    </div>
    <footer>Built from <a href="${REPO_URL}" target="_blank" rel="noopener">lerobot-groot-conformance</a>, an audit of public LeRobot datasets.
      <small>No emissions were measured. Independent project, not affiliated with NVIDIA or Hugging Face.</small></footer>
  </section>`;
  bindModelPicker($("#mp"));
  $("#toChecks").onclick = () => go("#checks");
  $("#toBoard").onclick = () => go("#leaderboard");
  $("#toBuild").onclick = () => go("#validation");
  $("#homeLogo").onclick = () => go("");
  const submit = (val) => {
    const id = parseDatasetId(val);
    if (!id) {
      const h = $("#heroHint");
      h.textContent = "That doesn't look like a dataset. Try huggingface.co/datasets/<user>/<name> or <user>/<name>.";
      h.className = "hint err";
      return;
    }
    go("#checks");
    startRun(id);
  };
  $("#heroForm").onsubmit = (e) => { e.preventDefault(); submit($("#heroIn").value); };
  app.querySelectorAll("[data-ex]").forEach((b) => (b.onclick = () => submit(b.dataset.ex)));
}

// ---------------------------------------------------------------- dashboard

const SECTIONS = [["checks", "Inspections"], ["leaderboard", "Leaderboard"], ["validation", "Model Validation"]];
function shell(inner, active = "checks") {
  const html = `<div class="shell"><header><div class="bar">
      <button class="logo" id="home">${brand()}</button>
      <nav><span class="pin">GR00T @${GROOT_SHA.slice(0, 7)}</span><a href="${REPO_URL}" target="_blank" rel="noopener">How it works</a></nav>
    </div><div class="sections" role="navigation" aria-label="Sections">${SECTIONS.map(([k, l]) =>
      `<button data-sec="${k}"${k === active ? ' aria-current="page"' : ""}>${l}${k === "checks" ? "" : ' <i class="soon-tag">coming soon</i>'}</button>`).join("")}</div></header><main class="page">${inner}</main></div>`;
  queueMicrotask(() => {
    app.querySelectorAll("[data-sec]").forEach((b) => (b.onclick = () => go("#" + b.dataset.sec)));
  });
  return html;
}

const when = (ts) => new Date(ts).toLocaleString(undefined, { month: "numeric", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });

function renderDashboard() {
  document.title = `My inspections · ${NAME}`;
  const list = runs.length ? `<div class="runs">${runs.map((r, i) => {
    const v = VERDICTS[r.verdict];
    const tone = r.error ? "bad" : tn(v.tone);
    const status = r.error ? ICON.fail : r.verdict === "READY" ? ICON.pass : tn(v.tone) === "close" ? ICON.warn : ICON.fail;
    const badge = r.error ? `<span class="badge t-bad">Couldn't inspect</span>` : `<span class="badge t-${tn(v.tone)}">${esc(v.headline)}</span>`;
    const scope = r.embodiment?.fit === "outside" ? `<span class="badge t-scope">${esc(r.embodiment.label)}</span>` : "";
    return `<div class="run z-${tone}" data-i="${i}" tabindex="0" role="button" aria-label="Open inspection of ${esc(r.dataset)}">
      ${status}<div class="meta"><div class="name">${esc(r.dataset)}</div>
      <div class="sub"><span>${when(r.at)}</span><span>Duration: ${(r.ms / 1000).toFixed(1)}s</span>${badge}${scope}</div></div>
      <button class="icon-btn blue" data-rerun="${i}" title="Run again" aria-label="Run again">${ICON.rerun}</button>
      <button class="icon-btn red" data-del="${i}" title="Remove" aria-label="Remove from history">${ICON.trash}</button></div>`;
  }).join("")}</div>`
    : `<div class="empty">${mascot("happy")}<p><b>No inspections yet.</b><br>Inspect a dataset and it'll show up here, saved in this browser only.</p></div>`;
  app.innerHTML = shell(`
    <div class="page-head"><div><div class="label">Inspection log</div><h1>Dataset Inspections</h1><p>Static GR00T-readiness inspections of Hugging Face robot datasets</p></div>
      <button class="btn primary" id="newRun">${ICON.plus} New Inspection</button></div>${list}`);
  $("#home").onclick = () => go("");
  $("#newRun").onclick = () => openWizard();
  app.querySelectorAll(".run").forEach((el) => {
    const open = () => showResult(runs[+el.dataset.i]);
    el.onclick = (e) => { if (!e.target.closest("button")) open(); };
    el.onkeydown = (e) => { if (e.key === "Enter") open(); };
  });
  app.querySelectorAll("[data-rerun]").forEach((b) => (b.onclick = () => startRun(runs[+b.dataset.rerun].dataset)));
  app.querySelectorAll("[data-del]").forEach((b) => (b.onclick = () => { runs.splice(+b.dataset.del, 1); saveRuns(runs); renderDashboard(); }));
}

// ---------------------------------------------------------------- new-inspection wizard

function openWizard(prefill = "") {
  let step = 1, id = parseDatasetId(prefill), raw = prefill;
  const ov = document.createElement("div");
  ov.className = "overlay";
  document.body.append(ov);
  const close = () => ov.remove();
  ov.onclick = (e) => { if (e.target === ov) close(); };
  const labels = ["Dataset", "Inspect against", "Review"];
  const draw = () => {
    const dots = labels.map((l, i) => `<div class="dot ${i + 1 === step ? "on" : i + 1 < step ? "done" : ""}">${i + 1 < step ? "✓" : i + 1}</div><span class="lbl ${i + 1 === step ? "on" : ""}">${l}</span>${i < labels.length - 1 ? '<div class="ln"></div>' : ""}`).join("");
    let body = "";
    if (step === 1) body = `<h3>Step 1: Which Hugging Face dataset should I inspect?</h3>
      <input class="field" id="wIn" value="${esc(raw)}" placeholder="https://huggingface.co/datasets/<user>/<name>" spellcheck="false">
      <p class="hint ${raw && !id ? "err" : ""}" id="wHint">${raw && !id ? "That doesn't look like a dataset link." : "A full link or just <user>/<name>. Public datasets only."}</p>
      <div class="chips">${EXAMPLES.map(chipHtml).join("")}</div>`;
    if (step === 2) body = `<h3>Step 2: What should it be ready for?</h3>
      <label class="opt sel"><input type="radio" checked name="tgt"><div><b>NVIDIA Isaac-GR00T reference loader</b><span>Pinned to commit ${GROOT_SHA.slice(0, 7)} (N1.7). 28 static checks, each cited to the line of GR00T code that requires it, plus a check of what kind of robot data it is.</span></div></label>
      <label class="opt dis"><input type="radio" disabled name="tgt"><div><b>LeRobot's built-in <code>groot</code> policy</b><span>Reads datasets through LeRobot's own loader. Not covered yet.</span></div></label>
      <div class="soon">${MODELS.filter((m) => !m.ready).map((m) => `<label class="opt dis"><input type="radio" disabled name="tgt"><div><b>${esc(m.name)}</b><span>${esc(m.by)} · <span class="badge t-skip">Coming soon</span></span></div></label>`).join("")}</div>`;
    if (step === 3) body = `<h3>Step 3: Ready to inspect</h3>
      <dl class="kv"><dt>Dataset</dt><dd><a href="https://huggingface.co/datasets/${esc(id)}" target="_blank" rel="noopener">${esc(id)}</a></dd>
      <dt>Standard</dt><dd>Isaac-GR00T reference loader @${GROOT_SHA.slice(0, 7)}</dd><dt>Checks</dt><dd>12 LeRobot + 16 GR00T + data type</dd></dl>
      <div class="note blue"><b>What happens:</b> your browser reads about 8 small metadata files from Hugging Face (nothing over 2 MB, no videos or episode data). Nothing is uploaded anywhere. The result is saved in this browser only.</div>`;
    ov.innerHTML = `<div class="modal ${ov.dataset.drawn ? "noanim" : ""}" role="dialog" aria-modal="true" aria-labelledby="wTitle">
      <div class="modal-h"><h2 id="wTitle">New Inspection</h2><button class="icon-btn" id="wX" aria-label="Close">${ICON.x}</button></div>
      <div class="stepper">${dots}</div><div class="modal-b">${body}</div>
      <div class="modal-f"><button class="btn" id="wBack">${step === 1 ? "Cancel" : "Back"}</button>
      <button class="btn primary" id="wNext" ${step === 1 && !id ? "disabled" : ""}>${step === 3 ? "Run inspection" : "Next ›"}</button></div></div>`;
    ov.dataset.drawn = "1";
    $("#wX", ov).onclick = close;
    $("#wBack", ov).onclick = () => { if (step === 1) close(); else { step--; draw(); } };
    $("#wNext", ov).onclick = () => { if (step < 3) { step++; draw(); } else { close(); startRun(id); } };
    const inp = $("#wIn", ov);
    if (inp) {
      inp.focus();
      inp.setSelectionRange(inp.value.length, inp.value.length);
      inp.oninput = () => {
        raw = inp.value; id = parseDatasetId(raw);
        $("#wNext", ov).disabled = !id;
        const h = $("#wHint", ov);
        h.className = "hint" + (raw && !id ? " err" : "");
        h.textContent = raw && !id ? "That doesn't look like a dataset link." : id ? `Will inspect ${id}` : "A full link or just <user>/<name>. Public datasets only.";
      };
      inp.onkeydown = (e) => { if (e.key === "Enter" && id) { step = 2; draw(); } };
      ov.querySelectorAll("[data-ex]").forEach((b) => (b.onclick = () => { raw = b.dataset.ex; id = raw; step = 2; draw(); }));
    }
  };
  draw();
}

// ---------------------------------------------------------------- running an inspection

let active = null;

async function startRun(datasetId) {
  const abort = new AbortController();
  const ov = openResultShell(datasetId, abort);
  const log = [];
  const t0 = performance.now();
  const paint = () => {
    $("#side", ov).innerHTML = `<div class="grp">Progress</div>` + log.map((l, i) =>
      `<div class="item"><span>${i === log.length - 1 ? '<span class="spin"></span>' : ICON.pass}</span><div><div class="t">${esc(l)}</div></div></div>`).join("");
    $("#detail", ov).innerHTML = `<div class="scan"><div>${mascot("look", { cls: "working" })}</div><div><div class="label" style="color:var(--muted)">Inspection in progress</div>
      <h3 style="margin-top:6px">Reading ${esc(datasetId)}</h3><p>Metadata straight from Hugging Face, in your browser.</p>
      <ul class="log">${log.map((l, i) => `<li class="${i === log.length - 1 ? "now" : ""}">${i === log.length - 1 ? '<span class="spin"></span>' : "✓"} ${esc(l)}</li>`).join("")}</ul></div></div>`;
  };
  log.push("Contacting Hugging Face");
  paint();
  let rec;
  try {
    const view = await new HubView(datasetId).load((_, msg) => { log.push(msg); paint(); }, abort.signal);
    log.push("Running 28 checks + data-type check");
    paint();
    const r = runAll(view);
    const draft = r.checks.find((c) => c.id === "G6")?.passed === false && r.info ? draftModality(r.info) : null;
    const draftVerdict = draft?.ok ? runAll(withFile(view, "meta/modality.json", JSON.stringify(draft.draft))).verdict : null;
    rec = {
      dataset: datasetId, at: Date.now(), ms: Math.round(performance.now() - t0), sha: view.sha,
      verdict: r.verdict, steps: r.steps, unverified: r.unverified_size,
      checks: r.checks.map(({ id, level, passed, detail, source, blocked_by }) => ({ id, level, passed, detail, source, blocked_by })),
      embodiment: r.info ? { ...classifyEmbodiment(r.info, datasetId), robot_type: r.info.robot_type ?? null } : null,
      fetch: { requests: view.nRequests, bytes: view.bytesDownloaded, listingComplete: view.listingComplete }, nested: view.nestedRoots.slice(0, 5),
      draft, draftVerdict,
    };
  } catch (e) {
    if (e.name === "AbortError") return;
    rec = { dataset: datasetId, at: Date.now(), ms: Math.round(performance.now() - t0), error: { kind: e instanceof FetchError ? e.kind : "network", message: e.message || String(e) } };
  }
  runs = [rec, ...runs];
  saveRuns(runs);
  if (location.hash === "#checks" || new URLSearchParams(location.search).get("d")) renderDashboard();
  if (document.body.contains(ov)) fillResult(ov, rec);
}

function openResultShell(datasetId, abort) {
  active?.abort?.abort();
  document.querySelectorAll(".overlay").forEach((o) => o.remove());
  const ov = document.createElement("div");
  ov.className = "overlay";
  ov.innerHTML = `<div class="modal wide" role="dialog" aria-modal="true" aria-labelledby="rTitle">
    <div class="res-h"><div><div class="label">Inspection report · GR00T @${GROOT_SHA.slice(0, 7)}</div><h2 id="rTitle">${esc(datasetId)} <span class="badge t-run" id="rBadge">Inspecting…</span></h2>
      <a class="link" href="https://huggingface.co/datasets/${esc(datasetId)}" target="_blank" rel="noopener">huggingface.co/datasets/${esc(datasetId)} ${ICON.ext}</a></div>
      <div class="acts" id="rActs"><button class="icon-btn" id="rX" aria-label="Close">${ICON.x}</button></div></div>
    <div class="res-body"><div class="side" id="side"></div><div class="detail" id="detail"></div></div></div>`;
  document.body.append(ov);
  const close = () => { abort?.abort(); ov.remove(); if (new URLSearchParams(location.search).get("d")) history.replaceState(null, "", location.pathname + "#checks"); };
  $("#rX", ov).onclick = close;
  ov.onclick = (e) => { if (e.target === ov) close(); };
  document.addEventListener("keydown", function onEsc(e) { if (e.key === "Escape") { close(); document.removeEventListener("keydown", onEsc); } });
  active = { ov, abort };
  return ov;
}

function showResult(rec) {
  fillResult(openResultShell(rec.dataset, null), rec);
}

// ---------------------------------------------------------------- results

function fillResult(ov, rec) {
  const v = rec.error ? null : VERDICTS[rec.verdict];
  $("#rBadge", ov).className = `badge t-${rec.error ? "bad" : tn(v.tone)}`;
  $("#rBadge", ov).innerHTML = rec.error ? "Couldn't inspect" : esc(v.headline);
  $("#rActs", ov).insertAdjacentHTML("afterbegin", `<button class="btn" id="rRerun">${ICON.rerun} Re-inspect</button>` +
    (rec.error ? "" : `<button class="btn" id="rJson">${ICON.dl} JSON</button>`) + `<button class="btn" id="rShare">${ICON.share} Share</button>`);
  $("#rRerun", ov).onclick = () => startRun(rec.dataset);
  $("#rShare", ov).onclick = async () => {
    const url = `${location.origin}${location.pathname}?d=${encodeURIComponent(rec.dataset)}`;
    try { await navigator.clipboard.writeText(url); toast("Link copied. Opening it re-runs this inspection."); } catch { prompt("Copy this link:", url); }
  };
  if (!rec.error) $("#rJson", ov).onclick = () => download(`smogcheck_${rec.dataset.replace("/", "__")}.json`, JSON.stringify(rec, null, 2), "application/json");
  if (rec.error) return fillError(ov, rec);

  const byId = Object.fromEntries(rec.checks.map((c) => [c.id, c]));
  const em = rec.embodiment;
  const items = [{ key: "summary", icon: ICON.report, t: "Inspection summary", d: v.headline }];
  if (em) items.push({ key: "kind", icon: em.fit === "outside" ? ICON.scope : ICON.robot, t: "What kind of data is this?", d: em.fit === "outside" ? `${em.label}: likely outside GR00T's scope` : em.label });
  if (byId.G6?.passed === false) {
    items.push(rec.draft?.ok ? { key: "draft", icon: ICON.draft, t: "Draft my modality.json", d: `Proposed from dimension names · would make this ${VERDICTS[rec.draftVerdict]?.headline.toLowerCase() || rec.draftVerdict}`, spark: true }
      : { key: "draft", icon: ICON.info, t: "Why no modality.json draft", d: rec.draft?.reason || "info.json unavailable" });
  }
  let html = items.map(itemHtml).join("");
  const order = (c) => ({ fail: 0, warn: 1, info: 2, skip: 3, pass: 4 }[checkStatus(c)]);
  for (const g of GROUPS) {
    const cs = g.ids.map((id) => byId[id]).filter(Boolean).sort((a, b) => order(a) - order(b));
    if (!cs.length) continue;
    html += `<div class="grp"><span>${esc(g.title)}</span><span>${cs.filter((c) => c.passed === true).length}/${cs.length}</span></div>` +
      cs.map((c) => itemHtml({ key: c.id, icon: ICON[checkStatus(c)], t: CHECKS[c.id].title, d: c.detail })).join("");
  }
  html += `<div class="grp">About this inspection</div>` + itemHtml({ key: "run", icon: ICON.shield, t: "How this was inspected", d: `${rec.fetch.requests} requests · ${(rec.ms / 1000).toFixed(1)}s · repo @${rec.sha.slice(0, 7)}` });
  const side = $("#side", ov);
  side.innerHTML = html;
  const select = (key) => {
    side.querySelectorAll(".item").forEach((el) => el.classList.toggle("sel", el.dataset.k === key));
    const d = $("#detail", ov);
    d.scrollTop = 0;
    d.innerHTML = key === "summary" ? summaryHtml(rec, v, byId) : key === "kind" ? kindHtml(rec) : key === "draft" ? draftHtml(rec)
      : key === "run" ? runHtml(rec) : checkHtml(byId[key], rec.dataset);
    d.querySelectorAll("[data-go]").forEach((a) => (a.onclick = (e) => { e.preventDefault(); select(a.dataset.go); }));
    $("#copyDraft", d)?.addEventListener("click", async () => { try { await navigator.clipboard.writeText(draftText(rec)); toast("modality.json copied"); } catch { toast("Copy failed; use Download"); } });
    $("#dlDraft", d)?.addEventListener("click", () => download("modality.json", draftText(rec), "application/json"));
  };
  side.querySelectorAll(".item").forEach((el) => (el.onclick = () => select(el.dataset.k)));
  select("summary");
}

const itemHtml = ({ key, icon, t, d, spark }) =>
  `<button class="item ${spark ? "spark" : ""}" data-k="${esc(key)}">${icon}<div style="min-width:0"><div class="t">${esc(t)}</div><div class="d">${esc(d)}</div></div></button>`;

function stepsHtml(rec, byId) {
  const li = [];
  for (const s of rec.steps) {
    if (s === "DOWNCONVERT") li.push(`<b>Convert v3.0 → v2.</b> GR00T reads the LeRobot v2 layout today. Run NVIDIA's <code>convert_v3_to_v2.py</code> (<a href="#" data-go="G7">details</a>).`);
    if (s === "MODALITY") li.push(`<b>Add <code>meta/modality.json</code>.</b> ${rec.draft?.ok ? `A draft is ready: <a href="#" data-go="draft">review it</a>.` : `It names which numbers are the arm, the gripper, etc. (<a href="#" data-go="G6">details</a>).`}`);
    if (s === "INCONSISTENT_MODALITY") li.push(`<b>Fix <code>modality.json</code>.</b> See the failing modality checks on the left.`);
    if (s === "REPAIR") li.push(`<b>Restore missing episode files</b>, or drop those episodes with NVIDIA's repair script (<a href="#" data-go="G14">details</a>).`);
    if (s === "BLOCKED") li.push(byId.L3?.passed === false ? `<b>Upload the recorded episodes.</b> The repo has metadata but no parquet files under <code>data/</code> (<a href="#" data-go="L3">details</a>).`
      : `<b>Fix the structural problems</b> flagged on the left. No converter handles these.`);
  }
  if (!li.length) return "";
  const caveat = rec.embodiment?.fit === "outside" ? `<p style="margin:-2px 0 10px">These only matter if you still want GR00T to load it; see <a href="#" data-go="kind">what kind of data this is</a>.</p>` : "";
  return `<h4>Steps to ready</h4>${caveat}<ol class="steps-to">${li.map((x) => `<li>${x}</li>`).join("")}</ol>`;
}

function scopeNote(rec) {
  const em = rec.embodiment;
  if (!em || em.fit !== "outside") return "";
  return `<div class="note violet"><b>Format and fit are different questions.</b> This looks like <b>${esc(em.label.toLowerCase())}</b> data (${esc(em.evidence)}). It may load, but GR00T is built for robot arms, hands and humanoids, so it's likely outside GR00T's scope as training data. <a href="#" data-go="kind">Why</a></div>`;
}

function summaryHtml(rec, v, byId) {
  const n = { pass: 0, fail: 0, warn: 0, skip: 0, info: 0 };
  for (const c of rec.checks) n[checkStatus(c)]++;
  const stamp = rec.verdict === "READY" ? `<span class="stamp" style="color:var(--good)">PASS</span>` : `<span class="stamp" style="color:${tn(v.tone) === "bad" ? "var(--bad)" : "#9a6a00"}">NOT YET</span>`;
  const nested = rec.verdict === "NOT_LEROBOT" && rec.nested?.length
    ? `<div class="note amber">This repo holds several datasets in subfolders, for example ${rec.nested.map((p) => `<code>${esc(p)}</code>`).join(", ")}. GR00T loads one dataset directory at a time; inspect each subfolder as its own dataset.</div>` : "";
  const unver = rec.unverified?.length ? `<div class="note amber">Some checks (${rec.unverified.join(", ")}) couldn't run because a metadata file or file listing is larger than this inspection reads. The result may understate what's needed.</div>` : "";
  return `<div class="verdict"><div>${gauge(rec.verdict)}</div><div><div class="label">Readiness · ${stamp}</div><div class="big">${esc(v.headline)}</div><p>${esc(v.sub)}</p></div></div>
    ${scopeNote(rec)}
    <div class="tally"><div><b style="color:var(--good)">${n.pass}</b><span>passed</span></div><div><b style="color:var(--bad)">${n.fail}</b><span>failed</span></div>
    <div><b style="color:var(--warn)">${n.warn + n.info}</b><span>warnings</span></div><div><b style="color:var(--skip)">${n.skip}</b><span>skipped</span></div></div>
    ${nested}${unver}${stepsHtml(rec, byId)}
    <div class="note blue"><b>Static checks only.</b> This reads metadata; it doesn't load data through GR00T or judge data quality. "Passes" means nothing in the files stands in the way, not that a model will train well.</div>`;
}

function kindHtml(rec) {
  const em = rec.embodiment;
  const fitTxt = { fits: "Fits the kinds of robot GR00T is built for.", outside: "Likely outside GR00T's scope as training data.", unclear: "Couldn't tell from the metadata." }[em.fit];
  const badge = { fits: "t-good", outside: "t-scope", unclear: "t-skip" }[em.fit];
  return `<h3>What kind of data is this?</h3><span class="badge ${badge}">${esc(em.label)}</span>
    <h4>Verdict</h4><p>${fitTxt} ${em.fit === "outside" ? "The format checks still apply. A well-formed dataset can be the wrong kind of data for a given model." : ""}</p>
    <h4>Evidence</h4><div class="box"><dl class="kv"><dt>robot_type</dt><dd class="mono">${esc(em.robot_type ?? "(not set)")}</dd><dt>Reason</dt><dd>${esc(em.evidence)}</dd></dl></div>
    <h4>How this is decided</h4><p>From metadata only, strongest evidence first: <code>info.json:robot_type</code> (LeRobot writes it automatically), then vehicle controls (steering, brake, throttle) or human-motion fields (SMPL), then arm and body dimension names, and last, robot names in the dataset name. GR00T N1.7 targets single arms, bimanual setups, mobile manipulators and humanoids.</p>
    ${em.fit === "unclear" ? `<div class="note amber">Set <code>robot_type</code> in <code>meta/info.json</code> (e.g. <code>so101_follower</code>, <code>franka</code>, <code>unitree_g1</code>) so people and tools can tell what the data is.</div>` : ""}
    <div class="note blue">This is a heuristic. It's a separate question from loadability and doesn't change the readiness verdict.</div>`;
}

function checkHtml(c, dataset) {
  const e = CHECKS[c.id];
  const st = checkStatus(c);
  const tone = { pass: "good", fail: "bad", warn: "warn", info: "close", skip: "skip" }[st];
  const label = { pass: "Passed", fail: "Failed", warn: "Warning", info: "Note", skip: "Skipped" }[st];
  const src = c.source ? sourceUrl(c.source) : [];
  return `<h3>${esc(e.title)}</h3><span class="badge t-${tone}">${label}</span> <span class="badge t-skip">${c.id} · ${c.level}</span>
    <h4>What this means</h4><p>${esc(e.why)}</p>
    <h4>Reading</h4><div class="box"><pre>${esc(c.detail)}</pre></div>
    ${st !== "pass" && st !== "skip" ? `<h4>How to fix</h4><div class="box"><pre>${esc(e.fix.replace("<user>/<dataset>", dataset))}</pre></div>` : ""}
    ${st === "skip" && c.blocked_by ? `<p style="margin-top:12px">Skipped because ${c.blocked_by === "size" ? "its input is over the 2 MB metadata cap" : `it depends on <a href="#" data-go="${esc(c.blocked_by)}">${esc(c.blocked_by)}</a>`}; it isn't counted as a second failure.</p>` : ""}
    ${src.length ? `<h4>Where GR00T requires it</h4><div class="src">${src.map((s) => `<a href="${s.url}" target="_blank" rel="noopener">${esc(s.label)} ↗</a>`).join("")}</div>` : ""}`;
}

const draftText = (rec) => formatModality(rec.draft.draft);

function draftHtml(rec) {
  const d = rec.draft;
  if (!d?.ok) return `<h3>No draft this time</h3><p>${esc(d?.reason || "info.json could not be read.")}</p>
    ${d?.bad?.length ? `<h4>Names that couldn't be interpreted</h4><div class="box"><pre>${esc(d.bad.join(", "))}</pre></div>` : ""}
    <div class="note blue">Someone who knows the robot can still write it by hand: about ten lines that say which slice of the state/action vector is the arm, the gripper, and so on. See <a href="https://github.com/NVIDIA/Isaac-GR00T/blob/${GROOT_SHA}/getting_started/data_preparation.md#the-metamodalityjson-configuration" target="_blank" rel="noopener">GR00T's data preparation guide</a>.</div>`;
  const rows = ["state", "action"].flatMap((s) => d.groups[s].map((g) => `<tr><td>${s}</td><td><b>${esc(g.name)}</b></td><td class="mono">[${g.start}:${g.end}]</td><td class="mono">${esc(g.dims.join(", "))}</td></tr>`)).join("");
  const after = VERDICTS[rec.draftVerdict];
  return `<h3>Draft meta/modality.json</h3><p>Built from this dataset's own dimension names. With it in place, the inspection reads: <span class="badge t-${tn(after.tone)}">${esc(after.headline)}</span></p>
    ${scopeNote(rec)}
    <div class="note amber"><b>Please check before using.</b> This is a proposal from names, not knowledge of your robot. A wrong range doesn't raise an error in GR00T: it quietly trains on the wrong joints.</div>
    <h4>How the dimensions were grouped</h4><table class="groups"><thead><tr><th>section</th><th>group</th><th>slice</th><th>dimension names</th></tr></thead><tbody>${rows}</tbody></table>
    <h4>meta/modality.json</h4><pre class="code">${esc(draftText(rec))}</pre>
    <div style="display:flex;gap:8px;margin-top:10px"><button class="btn primary" id="dlDraft">${ICON.dl} Download</button><button class="btn" id="copyDraft">Copy</button></div>
    ${d.notes.length ? `<h4>Notes</h4><ul style="color:var(--ink-2);line-height:1.6;padding-left:20px;margin:0">${d.notes.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}`;
}

function runHtml(rec) {
  return `<h3>How this was inspected</h3><p>Everything ran in your browser against Hugging Face's public API. No video or episode data was downloaded, nothing was uploaded, and no file over 2 MB was read.</p>
    <div class="box" style="margin-top:14px"><dl class="kv"><dt>Dataset</dt><dd>${esc(rec.dataset)}</dd><dt>Repo commit</dt><dd class="mono">${esc(rec.sha)}</dd>
    <dt>Standard</dt><dd><a href="https://github.com/NVIDIA/Isaac-GR00T/tree/${GROOT_SHA}" target="_blank" rel="noopener">Isaac-GR00T @${GROOT_SHA.slice(0, 7)}</a></dd>
    <dt>Requests</dt><dd>${rec.fetch.requests} (${(rec.fetch.bytes / 1024).toFixed(1)} KB of metadata)</dd><dt>Duration</dt><dd>${(rec.ms / 1000).toFixed(1)} s</dd>
    <dt>File listing</dt><dd>${rec.fetch.listingComplete ? "complete" : `capped at ${LIST_CAP.toLocaleString("en-US")} files per folder; the episode-files check was skipped`}</dd>
    <dt>Inspected</dt><dd>${new Date(rec.at).toLocaleString()}</dd></dl></div>
    <div class="note blue">The same 28 checks run in the <a href="${REPO_URL}" target="_blank" rel="noopener">command-line linter</a> used for the audit of 562 public datasets, and a test keeps the two in agreement. Not affiliated with NVIDIA or Hugging Face.</div>`;
}

function fillError(ov, rec) {
  const e = rec.error;
  $("#side", ov).innerHTML = itemHtml({ key: "e1", icon: ICON.info, t: "Hugging Face response", d: e.message }) +
    `<button class="item sel" data-k="e2">${ICON.fail}<div><div class="t">Inspection failed</div><div class="d">View error details</div></div></button>`;
  const tips = {
    not_found_or_private: "Check the spelling. Private and gated datasets can't be read without signing in, and this tool doesn't ask for your token.",
    gated: "This dataset is gated: Hugging Face requires accepting its terms first. This tool only reads public data.",
    rate_limited: "Hugging Face limits anonymous requests per network. Wait a few minutes and try again.",
    empty_repo: "The repo exists but has no files yet.",
  };
  $("#detail", ov).innerHTML = `<div class="verdict"><div>${gauge(null, true)}</div><div><div class="label">No reading</div><div class="big" style="color:var(--bad)">Couldn't inspect this one</div><p>The inspection stopped before it could read the dataset.</p></div></div>
    <div class="note red"><b>Error details</b><br><span class="mono" style="font-size:13px">${esc(e.message)}</span></div>
    <div class="box" style="margin-top:14px"><dl class="kv"><dt>Dataset</dt><dd>${esc(rec.dataset)}</dd><dt>Status</dt><dd style="color:var(--bad)">Failed (${esc(e.kind)})</dd><dt>At</dt><dd>${new Date(rec.at).toLocaleString()}</dd></dl></div>
    <div class="note blue"><b>Troubleshooting:</b> ${esc(tips[e.kind] || "Check your connection and the dataset link, then try again.")}</div>`;
}

function download(name, text, type) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

route();
