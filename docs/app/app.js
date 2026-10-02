import { runAll, GROOT_SHA } from "./checks.js";
import { HubView, FetchError, parseDatasetId, withFile, LIST_CAP } from "./hub.js";
import { draftModality, formatModality } from "./draft.js";
import { GROUPS, CHECKS, VERDICTS, sourceUrl } from "./explain.js";

const REPO_URL = "https://github.com/vincentstanfordlead/lerobot-groot-conformance";
const EXAMPLES = ["youliangtan/tictac-bot", "whosricky/so101_pick_red_cube_3cams", "lerobot/svla_so100_sorting"];
const STORE = "gripcheck.runs.v1";
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const app = $("#app");

// ---------------------------------------------------------------- mascot

function bot(mood = "happy", cls = "") {
  const eyes = mood === "think"
    ? `<circle cx="84" cy="100" r="9" fill="#3b2314"/><circle cx="136" cy="100" r="9" fill="#3b2314"/><circle cx="87" cy="96" r="3" fill="#fff"/><circle cx="139" cy="96" r="3" fill="#fff"/>`
    : mood === "oops"
      ? `<path d="M74 96l18 10M92 96l-18 10" stroke="#3b2314" stroke-width="6" stroke-linecap="round"/><path d="M128 96l18 10M146 96l-18 10" stroke="#3b2314" stroke-width="6" stroke-linecap="round"/>`
      : `<ellipse cx="84" cy="102" rx="10" ry="12" fill="#3b2314"/><ellipse cx="136" cy="102" rx="10" ry="12" fill="#3b2314"/><circle cx="88" cy="97" r="4" fill="#fff"/><circle cx="140" cy="97" r="4" fill="#fff"/>`;
  const mouth = mood === "think" ? `<path d="M98 130h24" stroke="#3b2314" stroke-width="6" stroke-linecap="round"/>`
    : mood === "oops" ? `<ellipse cx="110" cy="132" rx="9" ry="7" fill="#3b2314"/><path d="M168 60c6 9 6 15 0 18-6-3-6-9 0-18z" fill="#8cc8f2"/>`
      : `<path d="M96 124q14 14 28 0" stroke="#3b2314" stroke-width="6" fill="#f08a7b" stroke-linecap="round" stroke-linejoin="round"/>`;
  return `<svg class="${cls}" viewBox="0 0 220 200" role="img" aria-label="GripCheck robot mascot">
    <path d="M110 44V22" stroke="#6b3a1e" stroke-width="6" stroke-linecap="round"/><circle cx="110" cy="16" r="10" fill="#f5a524" stroke="#6b3a1e" stroke-width="5"/>
    <path d="M38 88c-20 0-28 14-28 26s8 26 28 26M30 100c-8 4-8 24 0 28" fill="none" stroke="#6b3a1e" stroke-width="7" stroke-linecap="round"/>
    <path d="M182 88c20 0 28 14 28 26s-8 26-28 26M190 100c8 4 8 24 0 28" fill="none" stroke="#6b3a1e" stroke-width="7" stroke-linecap="round"/>
    <rect x="36" y="44" width="148" height="128" rx="46" fill="#ffd36e" stroke="#6b3a1e" stroke-width="7"/>
    <rect x="52" y="58" width="56" height="18" rx="9" fill="#fff" opacity=".45"/>
    ${eyes}<circle cx="66" cy="124" r="9" fill="#f6a0a0" opacity=".7"/><circle cx="154" cy="124" r="9" fill="#f6a0a0" opacity=".7"/>${mouth}
  </svg>`;
}

const ICON = {
  pass: `<svg class="st" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#1a8f55"/><path d="M7.5 12.5l3 3 6-6.5" stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  fail: `<svg class="st" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="#cf3f3f" stroke-width="2"/><path d="M9 9l6 6M15 9l-6 6" stroke="#cf3f3f" stroke-width="2.2" stroke-linecap="round"/></svg>`,
  warn: `<svg class="st" viewBox="0 0 24 24"><path d="M12 3l10 18H2z" fill="#f5b53b"/><path d="M12 10v5" stroke="#5a3700" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="18" r="1.3" fill="#5a3700"/></svg>`,
  skip: `<svg class="st" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="#9aa0a8" stroke-width="2" stroke-dasharray="3 3"/><path d="M8 12h8" stroke="#9aa0a8" stroke-width="2" stroke-linecap="round"/></svg>`,
  info: `<svg class="st" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#eaf1fd" stroke="#2f6fdb" stroke-width="1.6"/><path d="M12 11v6" stroke="#2f6fdb" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="7.5" r="1.3" fill="#2f6fdb"/></svg>`,
  spark: `<svg class="st" viewBox="0 0 24 24"><path d="M12 2l2.2 6.3L20.5 10l-6.3 2.2L12 18.5l-2.2-6.3L3.5 10l6.3-1.7z" fill="#f5a524" stroke="#6b3a1e" stroke-width="1.2" stroke-linejoin="round"/></svg>`,
  chat: `<svg class="st" viewBox="0 0 24 24"><path d="M4 5h16v11H9l-5 4z" fill="none" stroke="#2f6fdb" stroke-width="1.8" stroke-linejoin="round"/></svg>`,
  shield: `<svg class="st" viewBox="0 0 24 24"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" fill="none" stroke="#7c5cd6" stroke-width="1.8" stroke-linejoin="round"/></svg>`,
  rerun: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/></svg>`,
  trash: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>`,
  x: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>`,
  share: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>`,
  ext: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/></svg>`,
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
function saveRuns(runs) {
  try { localStorage.setItem(STORE, JSON.stringify(runs.slice(0, 25))); } catch { /* private mode: history just isn't kept */ }
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
    const id = parseDatasetId(d);
    renderDashboard();
    if (id) startRun(id);
    return;
  }
  if (location.hash === "#checks") renderDashboard();
  else renderLanding();
}
window.addEventListener("popstate", route);
function go(hash) {
  history.pushState(null, "", location.pathname + hash);
  route();
}

// ---------------------------------------------------------------- landing

function renderLanding() {
  document.title = "GripCheck — is your robot dataset GR00T-ready?";
  const doodles = [[6, 14, "⚙"], [88, 22, "⚙"], [12, 70, "◔"], [90, 64, "✦"], [76, 86, "⚙"]]
    .map(([x, y, ch], i) => `<span class="doodle" style="left:${x}%;top:${y}%;font-size:${22 + i * 4}px;animation-delay:${i * .7}s">${ch}</span>`).join("");
  app.innerHTML = `
  <section class="landing">
    ${doodles}
    <nav class="topnav"><button id="toChecks">My checks${runs.length ? ` (${runs.length})` : ""}</button><a href="${REPO_URL}" target="_blank" rel="noopener">How it works</a></nav>
    <div class="wordmark">GripCheck</div>
    <p class="tagline">Is your robot dataset ready for NVIDIA Isaac GR00T?</p>
    ${bot("happy", "hero-bot")}
    <div class="hero-q">Not sure if your dataset will load?<br>Let me check it out!</div>
    <form class="hero-form" id="heroForm" autocomplete="off">
      <label class="sr" for="heroIn">Hugging Face dataset link or id</label>
      <input id="heroIn" placeholder="huggingface.co/datasets/you/your-robot-data" spellcheck="false">
      <button class="pill-btn" type="submit">Check it 🔍</button>
    </form>
    <p class="hint" id="heroHint">Paste a Hugging Face dataset link, or try one:</p>
    <div class="chips">${EXAMPLES.map((e) => `<button class="chip" data-ex="${e}">${e}</button>`).join("")}</div>
    <div class="trust"><span>Reads metadata only</span><span>Runs in your browser</span><span>No sign-in</span><span>28 checks, each cited to GR00T's code</span></div>
    <footer>Built from an audit of 562 public robot datasets · <a href="${REPO_URL}" target="_blank" rel="noopener">lerobot-groot-conformance</a>
      <small>No robots were harmed in the making of this checker. Independent project, not affiliated with NVIDIA or Hugging Face.</small></footer>
  </section>`;
  $("#toChecks").onclick = () => go("#checks");
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

function shell(inner) {
  return `<div class="shell"><header><div class="bar">
      <button class="brand" id="home">${bot("happy")}<span class="wordmark">GripCheck</span></button>
      <nav><span class="pin">checks pinned to Isaac-GR00T @${GROOT_SHA.slice(0, 7)}</span><a href="${REPO_URL}" target="_blank" rel="noopener">How it works</a></nav>
    </div></header><main class="page">${inner}</main></div>`;
}

function timeAgo(ts) {
  const d = new Date(ts);
  return d.toLocaleString(undefined, { month: "numeric", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

function renderDashboard() {
  document.title = "My checks · GripCheck";
  const list = runs.length ? `<div class="runs">${runs.map((r, i) => {
    const v = VERDICTS[r.verdict];
    const status = r.error ? ICON.fail : r.verdict === "READY" ? ICON.pass : v && ["close", "mid"].includes(v.tone) ? ICON.warn : ICON.fail;
    const badge = r.error ? `<span class="badge t-bad">Couldn't check</span>` : `<span class="badge t-${v.tone}">${esc(v.headline)}</span>`;
    return `<div class="run" data-i="${i}" tabindex="0" role="button" aria-label="Open check for ${esc(r.dataset)}">
      ${status}<div class="meta"><div class="name">${esc(r.dataset)}</div>
      <div class="sub"><span>${timeAgo(r.at)}</span><span>Duration: ${(r.ms / 1000).toFixed(1)}s</span>${badge}</div></div>
      <button class="icon-btn blue" data-rerun="${i}" title="Run again" aria-label="Run again">${ICON.rerun}</button>
      <button class="icon-btn red" data-del="${i}" title="Remove" aria-label="Remove from history">${ICON.trash}</button></div>`;
  }).join("")}</div>`
    : `<div class="empty">${bot("happy")}<p><b>No checks yet.</b><br>Check a dataset and it'll show up here, saved in this browser only.</p></div>`;
  app.innerHTML = shell(`
    <div class="page-head"><div><h1>Dataset Checks</h1><p>Static GR00T-readiness checks on Hugging Face robot datasets</p></div>
      <button class="btn primary" id="newRun">${ICON.plus} New Check</button></div>${list}`);
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

// ---------------------------------------------------------------- new-check wizard

function openWizard(prefill = "") {
  let step = 1, id = parseDatasetId(prefill), raw = prefill;
  const ov = document.createElement("div");
  ov.className = "overlay";
  document.body.append(ov);
  const close = () => ov.remove();
  ov.onclick = (e) => { if (e.target === ov) close(); };
  const labels = ["Dataset", "Check against", "Review"];
  const draw = () => {
    const dots = labels.map((l, i) => `<div class="dot ${i + 1 === step ? "on" : i + 1 < step ? "done" : ""}">${i + 1 < step ? "✓" : i + 1}</div><span class="lbl ${i + 1 === step ? "on" : ""}">${l}</span>${i < labels.length - 1 ? '<div class="ln"></div>' : ""}`).join("");
    let body = "";
    if (step === 1) body = `<h3>Step 1: Which Hugging Face dataset should I check?</h3>
      <input class="field" id="wIn" value="${esc(raw)}" placeholder="https://huggingface.co/datasets/<user>/<name>" spellcheck="false">
      <p class="hint ${raw && !id ? "err" : ""}" id="wHint">${raw && !id ? "That doesn't look like a dataset link." : "A full link or just <user>/<name>. Public datasets only."}</p>
      <div class="chips" style="justify-content:flex-start">${EXAMPLES.map((e) => `<button class="chip" data-ex="${e}">${e}</button>`).join("")}</div>`;
    if (step === 2) body = `<h3>Step 2: What should it be ready for?</h3>
      <label class="opt sel"><input type="radio" checked name="tgt"><div><b>NVIDIA Isaac-GR00T reference loader</b><span>Pinned to commit ${GROOT_SHA.slice(0, 7)} (N1.7). 28 static checks, each cited to the line of GR00T code that requires it.</span></div></label>
      <label class="opt dis"><input type="radio" disabled name="tgt"><div><b>LeRobot's built-in <code>groot</code> policy</b><span>Reads datasets through LeRobot's own loader. Not covered yet.</span></div></label>`;
    if (step === 3) body = `<h3>Step 3: Ready to check</h3>
      <dl class="kv"><dt>Dataset</dt><dd><a href="https://huggingface.co/datasets/${esc(id)}" target="_blank" rel="noopener">${esc(id)}</a></dd>
      <dt>Target</dt><dd>Isaac-GR00T reference loader @${GROOT_SHA.slice(0, 7)}</dd><dt>Checks</dt><dd>12 LeRobot + 16 GR00T</dd></dl>
      <div class="note blue"><b>What happens:</b> your browser reads about 8 small metadata files from Hugging Face (nothing over 2 MB, no videos or episode data). Nothing is uploaded anywhere. The result is saved in this browser only.</div>`;
    ov.innerHTML = `<div class="modal ${ov.dataset.drawn ? "noanim" : ""}" role="dialog" aria-modal="true" aria-labelledby="wTitle">
      <div class="modal-h"><h2 id="wTitle">Create New Check</h2><button class="icon-btn" id="wX" aria-label="Close">${ICON.x}</button></div>
      <div class="stepper">${dots}</div><div class="modal-b">${body}</div>
      <div class="modal-f"><button class="btn" id="wBack">${step === 1 ? "Cancel" : "Back"}</button>
      <button class="btn primary" id="wNext" ${step === 1 && !id ? "disabled" : ""}>${step === 3 ? "Run check 🔍" : "Next ›"}</button></div></div>`;
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
        h.textContent = raw && !id ? "That doesn't look like a dataset link." : id ? `Will check ${id}` : "A full link or just <user>/<name>. Public datasets only.";
      };
      inp.onkeydown = (e) => { if (e.key === "Enter" && id) { step = 2; draw(); } };
      ov.querySelectorAll("[data-ex]").forEach((b) => (b.onclick = () => { raw = b.dataset.ex; id = raw; step = 2; draw(); }));
    }
  };
  draw();
}

// ---------------------------------------------------------------- running a check

let active = null; // { ov, abort }

async function startRun(datasetId) {
  const abort = new AbortController();
  const ov = openResultShell(datasetId, abort);
  const log = [];
  const t0 = performance.now();
  const paint = () => {
    $("#side", ov).innerHTML = `<div class="grp">Progress</div>` + log.map((l, i) =>
      `<div class="item"><span>${i === log.length - 1 ? '<span class="spin"></span>' : ICON.pass}</span><div><div class="t">${esc(l)}</div></div></div>`).join("");
    $("#detail", ov).innerHTML = `<div class="hero-v">${bot("think", "think-bot")}<div><div class="big">Checking…</div>
      <p>Reading ${esc(datasetId)}'s metadata straight from Hugging Face.</p></div></div>
      <ul class="log">${log.map((l, i) => `<li class="${i === log.length - 1 ? "now" : ""}">${i === log.length - 1 ? '<span class="spin"></span>' : "✓"} ${esc(l)}</li>`).join("")}</ul>`;
  };
  log.push("Contacting Hugging Face");
  paint();
  let rec;
  try {
    const view = await new HubView(datasetId).load((_, msg) => { log.push(msg); paint(); }, abort.signal);
    log.push("Running 28 checks");
    paint();
    const r = runAll(view);
    const draft = r.checks.find((c) => c.id === "G6")?.passed === false && r.info ? draftModality(r.info) : null;
    let draftVerdict = null;
    if (draft?.ok) draftVerdict = runAll(withFile(view, "meta/modality.json", JSON.stringify(draft.draft))).verdict;
    rec = {
      dataset: datasetId, at: Date.now(), ms: Math.round(performance.now() - t0), sha: view.sha,
      verdict: r.verdict, steps: r.steps, unverified: r.unverified_size, checks: r.checks.map(({ id, level, passed, detail, source, blocked_by }) => ({ id, level, passed, detail, source, blocked_by })),
      fetch: { requests: view.nRequests, bytes: view.bytesDownloaded, listingComplete: view.listingComplete }, nested: view.nestedRoots.slice(0, 5),
      draft, draftVerdict,
    };
  } catch (e) {
    if (e.name === "AbortError") return;
    rec = { dataset: datasetId, at: Date.now(), ms: Math.round(performance.now() - t0), error: { kind: e instanceof FetchError ? e.kind : "network", message: e.message || String(e) } };
  }
  runs = [rec, ...runs.filter((r) => !(r.dataset === datasetId && r.at === rec.at))];
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
    <div class="res-h"><div><h2 id="rTitle">Dataset Check <span class="badge t-run" id="rBadge">Running</span></h2>
      <a class="link" href="https://huggingface.co/datasets/${esc(datasetId)}" target="_blank" rel="noopener">huggingface.co/datasets/${esc(datasetId)} ${ICON.ext}</a></div>
      <div class="acts" id="rActs"><button class="icon-btn" id="rX" aria-label="Close">${ICON.x}</button></div></div>
    <div class="res-body"><div class="side" id="side"></div><div class="detail" id="detail"></div></div></div>`;
  document.body.append(ov);
  const close = () => { abort?.abort(); ov.remove(); if (new URLSearchParams(location.search).get("d")) history.replaceState(null, "", location.pathname + "#checks"); };
  $("#rX", ov).onclick = close;
  ov.onclick = (e) => { if (e.target === ov) close(); };
  document.addEventListener("keydown", function esc_(e) { if (e.key === "Escape") { close(); document.removeEventListener("keydown", esc_); } });
  active = { ov, abort };
  return ov;
}

function showResult(rec) {
  const ov = openResultShell(rec.dataset, null);
  fillResult(ov, rec);
}

// ---------------------------------------------------------------- results

function fillResult(ov, rec) {
  const v = rec.error ? null : VERDICTS[rec.verdict];
  $("#rBadge", ov).className = `badge t-${rec.error ? "bad" : v.tone}`;
  $("#rBadge", ov).innerHTML = rec.error ? "⊗ Couldn't check" : esc(v.headline);
  const acts = $("#rActs", ov);
  acts.insertAdjacentHTML("afterbegin", `<button class="btn" id="rRerun">${ICON.rerun} Run again</button>` +
    (rec.error ? "" : `<button class="btn" id="rJson">${ICON.dl} JSON</button>`) + `<button class="btn" id="rShare">${ICON.share} Share</button>`);
  $("#rRerun", ov).onclick = () => startRun(rec.dataset);
  $("#rShare", ov).onclick = async () => {
    const url = `${location.origin}${location.pathname}?d=${encodeURIComponent(rec.dataset)}`;
    try { await navigator.clipboard.writeText(url); toast("Link copied. Opening it re-runs this check."); } catch { prompt("Copy this link:", url); }
  };
  if (!rec.error) $("#rJson", ov).onclick = () => download(`gripcheck_${rec.dataset.replace("/", "__")}.json`, JSON.stringify(rec, null, 2), "application/json");

  if (rec.error) return fillError(ov, rec);

  const byId = Object.fromEntries(rec.checks.map((c) => [c.id, c]));
  const items = [{ key: "summary", icon: ICON.chat, t: "Summary", d: v.headline }];
  if (byId.G6?.passed === false) {
    items.push(rec.draft?.ok ? { key: "draft", icon: ICON.spark, t: "Draft my modality.json", d: `Proposed from dimension names · would make this ${VERDICTS[rec.draftVerdict]?.headline.toLowerCase() || rec.draftVerdict}`, spark: true }
      : { key: "draft", icon: ICON.info, t: "Why no modality.json draft", d: rec.draft?.reason || "info.json unavailable" });
  }
  let html = items.map((it) => itemHtml(it)).join("");
  const order = (c) => ({ fail: 0, warn: 1, info: 2, skip: 3, pass: 4 }[checkStatus(c)]);
  for (const g of GROUPS) {
    const cs = g.ids.map((id) => byId[id]).filter(Boolean).sort((a, b) => order(a) - order(b));
    if (!cs.length) continue;
    const nOk = cs.filter((c) => c.passed === true).length;
    html += `<div class="grp">${esc(g.title)} · ${nOk}/${cs.length}</div>` + cs.map((c) =>
      itemHtml({ key: c.id, icon: ICON[checkStatus(c)], t: CHECKS[c.id].title, d: c.detail })).join("");
  }
  html += `<div class="grp">About this run</div>` + itemHtml({ key: "run", icon: ICON.shield, t: "How this was checked", d: `${rec.fetch.requests} requests · ${(rec.ms / 1000).toFixed(1)}s · repo @${rec.sha.slice(0, 7)}` });
  const side = $("#side", ov);
  side.innerHTML = html;
  const select = (key) => {
    side.querySelectorAll(".item").forEach((el) => el.classList.toggle("sel", el.dataset.k === key));
    const d = $("#detail", ov);
    d.scrollTop = 0;
    if (key === "summary") d.innerHTML = summaryHtml(rec, v, byId);
    else if (key === "draft") d.innerHTML = draftHtml(rec);
    else if (key === "run") d.innerHTML = runHtml(rec);
    else d.innerHTML = checkHtml(byId[key], rec.dataset);
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
  return li.length ? `<h4>Steps to ready</h4><ol class="steps-to">${li.map((x) => `<li>${x}</li>`).join("")}</ol>` : "";
}

function summaryHtml(rec, v, byId) {
  const n = { pass: 0, fail: 0, warn: 0, skip: 0, info: 0 };
  for (const c of rec.checks) n[checkStatus(c)]++;
  const nested = rec.verdict === "NOT_LEROBOT" && rec.nested?.length
    ? `<div class="note amber">This repo holds several datasets in subfolders, for example ${rec.nested.map((p) => `<code>${esc(p)}</code>`).join(", ")}. GR00T loads one dataset directory at a time; check each subfolder as its own dataset.</div>` : "";
  const unver = rec.unverified?.length ? `<div class="note amber">Some checks (${rec.unverified.join(", ")}) couldn't run because a metadata file or file listing is larger than this checker reads. The result may understate what's needed.</div>` : "";
  return `<div class="hero-v">${bot(v.mood)}<div><div class="big">${esc(v.headline)}</div><p>${esc(v.sub)}</p></div></div>
    <div class="tally"><div><b style="color:var(--good)">${n.pass}</b><span>passed</span></div><div><b style="color:var(--bad)">${n.fail}</b><span>failed</span></div>
    <div><b style="color:var(--warn)">${n.warn + n.info}</b><span>warnings / notes</span></div><div><b style="color:var(--skip)">${n.skip}</b><span>skipped</span></div></div>
    ${nested}${unver}${stepsHtml(rec, byId)}
    <div class="note blue"><b>Static checks only.</b> This reads metadata; it doesn't load data through GR00T or judge data quality. "Passes" means nothing in the files stands in the way, not that a model will train well.</div>`;
}

function checkHtml(c, dataset) {
  const e = CHECKS[c.id];
  const st = checkStatus(c);
  const tone = { pass: "good", fail: "bad", warn: "warn", info: "close", skip: "skip" }[st];
  const label = { pass: "Passed", fail: "Failed", warn: "Warning", info: "Note", skip: "Skipped" }[st];
  const src = c.source ? sourceUrl(c.source) : [];
  return `<h3>${esc(e.title)}</h3><span class="badge t-${tone}">${label}</span> <span class="badge t-skip">${c.id} · ${c.level}</span>
    <h4>What this means</h4><p>${esc(e.why)}</p>
    <h4>Result</h4><div class="box"><pre>${esc(c.detail)}</pre></div>
    ${st !== "pass" && st !== "skip" ? `<h4>How to fix</h4><div class="box"><pre>${esc(e.fix.replace("<user>/<dataset>", dataset))}</pre></div>` : ""}
    ${st === "skip" && c.blocked_by ? `<p style="margin-top:12px">Skipped because ${c.blocked_by === "size" ? "its input is over the 2 MB metadata cap" : `it depends on <a href="#" data-go="${esc(c.blocked_by)}">${esc(c.blocked_by)}</a>`}; it isn't counted as a second failure.</p>` : ""}
    ${src.length ? `<h4>Where GR00T requires it</h4><div class="src">${src.map((s) => `<a href="${s.url}" target="_blank" rel="noopener">${esc(s.label)} ↗</a>`).join("")}</div>` : ""}`;
}

const draftText = (rec) => formatModality(rec.draft.draft);

function draftHtml(rec) {
  const d = rec.draft;
  if (!d?.ok) return `<div class="hero-v">${bot("think")}<div><div class="big">No draft this time</div><p>${esc(d?.reason || "info.json could not be read.")}</p></div></div>
    ${d?.bad?.length ? `<h4>Names that couldn't be interpreted</h4><div class="box"><pre>${esc(d.bad.join(", "))}</pre></div>` : ""}
    <div class="note blue">Someone who knows the robot can still write it by hand: about ten lines that say which slice of the state/action vector is the arm, the gripper, and so on. See <a href="https://github.com/NVIDIA/Isaac-GR00T/blob/${GROOT_SHA}/getting_started/data_preparation.md#the-metamodalityjson-configuration" target="_blank" rel="noopener">GR00T's data preparation guide</a>.</div>`;
  const rows = ["state", "action"].flatMap((s) => d.groups[s].map((g) => `<tr><td>${s}</td><td><b>${esc(g.name)}</b></td><td class="mono">[${g.start}:${g.end}]</td><td class="mono">${esc(g.dims.join(", "))}</td></tr>`)).join("");
  const after = VERDICTS[rec.draftVerdict];
  return `<div class="hero-v">${bot("happy")}<div><div class="big">Here's a draft modality.json</div>
    <p>Built from this dataset's own dimension names. With it in place, the checks say: <span class="badge t-${after.tone}">${esc(after.headline)}</span></p></div></div>
    <div class="note amber"><b>Please check before using.</b> This is a proposal from names, not knowledge of your robot. A wrong range doesn't raise an error in GR00T: it quietly trains on the wrong joints.</div>
    <h4>How the dimensions were grouped</h4><table class="groups"><thead><tr><th>section</th><th>group</th><th>slice</th><th>dimension names</th></tr></thead><tbody>${rows}</tbody></table>
    <h4>meta/modality.json</h4><pre class="code">${esc(draftText(rec))}</pre>
    <div style="display:flex;gap:8px;margin-top:10px"><button class="btn primary" id="dlDraft">${ICON.dl} Download</button><button class="btn" id="copyDraft">Copy</button></div>
    ${d.notes.length ? `<h4>Notes</h4><ul style="color:var(--ink-2);line-height:1.6;padding-left:20px;margin:0">${d.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}`;
}

function runHtml(rec) {
  return `<h3>How this was checked</h3><p>Everything ran in your browser against Hugging Face's public API. No video or episode data was downloaded, nothing was uploaded, and no file over 2 MB was read.</p>
    <dl class="kv" style="margin-top:14px"><dt>Dataset</dt><dd>${esc(rec.dataset)}</dd><dt>Repo commit</dt><dd class="mono">${esc(rec.sha)}</dd>
    <dt>Checked against</dt><dd><a href="https://github.com/NVIDIA/Isaac-GR00T/tree/${GROOT_SHA}" target="_blank" rel="noopener">Isaac-GR00T @${GROOT_SHA.slice(0, 7)}</a></dd>
    <dt>Requests</dt><dd>${rec.fetch.requests} (${(rec.fetch.bytes / 1024).toFixed(1)} KB of metadata)</dd><dt>Duration</dt><dd>${(rec.ms / 1000).toFixed(1)} s</dd>
    <dt>File listing</dt><dd>${rec.fetch.listingComplete ? "complete" : `capped at ${LIST_CAP.toLocaleString("en-US")} files per folder; the episode-files check was skipped`}</dd>
    <dt>Checked at</dt><dd>${new Date(rec.at).toLocaleString()}</dd></dl>
    <div class="note blue">The same 28 checks run in the <a href="${REPO_URL}" target="_blank" rel="noopener">command-line linter</a> used for the audit of 562 public datasets, and a test keeps the two in agreement. Not affiliated with NVIDIA or Hugging Face.</div>`;
}

function fillError(ov, rec) {
  const e = rec.error;
  $("#side", ov).innerHTML = itemHtml({ key: "e1", icon: ICON.chat, t: "Hugging Face response", d: e.message }) +
    `<button class="item sel" data-k="e2">${ICON.shield}<div><div class="t">Check failed</div><div class="d">View error details</div></div></button>`;
  const tips = {
    not_found_or_private: "Check the spelling. Private and gated datasets can't be read without signing in, and this checker doesn't ask for your token.",
    gated: "This dataset is gated: Hugging Face requires accepting its terms first. This checker only reads public data.",
    rate_limited: "Hugging Face limits anonymous requests per network. Wait a few minutes and try again.",
    empty_repo: "The repo exists but has no files yet.",
  };
  $("#detail", ov).innerHTML = `<div class="hero-v">${bot("oops")}<div><div class="big" style="color:var(--bad)">Couldn't check this one</div><p>The check stopped before it could read the dataset.</p></div></div>
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
