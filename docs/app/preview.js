// Preview pages: Leaderboard and Model Validation. Everything here is sample data for a feature that doesn't exist yet.
// Nothing is fetched, saved or sent. The banner on each page says so.

const banner = `<div class="pv-banner" role="note"><b>Coming soon</b><span>These pages show planned features. Every name and number is made-up sample data.</span></div>`;

// ---------------------------------------------------------------- leaderboard

// kinds of brick: plain = clean episodes, task/robot/scene = new coverage bonus, gold = Model Validation bonus, dup = grey plate (near-duplicates add no height)
const BUILDERS = [
  { who: "lab-alpha", bricks: ["plain", "plain", "task", "plain", "robot", "plain", "scene", "plain", "task", "gold", "gold", "plain", "plain", "task"], dup: 1, pass: 98, eps: 4210 },
  { who: "kitchen-bots", bricks: ["plain", "task", "plain", "plain", "scene", "plain", "gold", "plain", "plain", "task"], dup: 2, pass: 91, eps: 3170 },
  { who: "garage-arm", bricks: ["plain", "plain", "robot", "plain", "plain", "plain", "task"], dup: 0, pass: 96, eps: 2050 },
  { who: "you", bricks: ["plain", "plain", "task"], dup: 0, pass: 100, eps: 214, me: true },
  { who: "dupe-farm", bricks: ["plain", "plain"], dup: 9, pass: 100, eps: 5000 },
];
const BRICK_NAME = { plain: "50 clean episodes", task: "new task", robot: "new robot", scene: "new scene", gold: "Model Validation bonus", dup: "near-duplicates, no height" };

const DATASETS = [
  { id: "lab-alpha/towel_fold", eps: 220, robot: "bimanual", d: -0.084, sim: "+11%" },
  { id: "kitchen-bots/drawer_open", eps: 410, robot: "mobile", d: -0.051, sim: "+6%" },
  { id: "garage-arm/cube_sort", eps: 160, robot: "arm", d: -0.032, sim: "+4%" },
  { id: "dupe-farm/pick_cube_v3", eps: 5000, robot: "arm", d: -0.004, sim: "+0%", note: "saturated: near-duplicates" },
  { id: "lab-alpha/pour_water", eps: 90, robot: "bimanual", d: +0.011, sim: "-1%", note: "hurts: inconsistent labels" },
];

const WANTED = [
  { t: "Bimanual cloth folding", n: 200, got: 104, by: "team-x", reward: "500 bricks + co-author credit", tag: "GR00T-ready" },
  { t: "Failure and recovery demos, any arm", n: 50, got: 11, by: "open-vla-lab", reward: "300 bricks", tag: "any format that passes" },
  { t: "Mobile manipulator, kitchen drawers", n: 120, got: 96, by: "kitchen-bots", reward: "400 bricks + Model Validation free", tag: "GR00T-ready" },
];

function brickStack(b, max) {
  const cells = b.bricks.map((k) => `<i class="bk k-${k}" title="${BRICK_NAME[k]}"></i>`).join("");
  const dups = Array.from({ length: Math.min(b.dup, 6) }, () => `<i class="bk k-dup" title="${BRICK_NAME.dup}"></i>`).join("");
  return `<div class="tower${b.me ? " me" : ""}" style="--h:${b.bricks.length / max}">
    <div class="stack" role="img" aria-label="${b.who}: ${b.bricks.length} bricks">${cells}${dups}</div>
    <div class="tw-name">${b.me ? "@you" : "@" + b.who}</div><div class="tw-num">${b.bricks.length} bricks</div></div>`;
}

function datasetsTab(esc) {
  const max = Math.max(...DATASETS.map((r) => Math.abs(r.d)));
  return `<div class="lb-table" role="table" aria-label="Datasets ranked by Model Validation gain">
    <div class="lb-row lb-head" role="row"><span>#</span><span>Dataset</span><span>Episodes</span><span>Robot</span><span>Smog check</span><span>Loss change on reference set</span><span>Sim success</span></div>
    ${DATASETS.map((r, i) => {
      const good = r.d < -0.01, bad = r.d > 0;
      return `<div class="lb-row" role="row">
        <span class="rk">${i + 1}</span>
        <span class="nm"><b>${esc(r.id)}</b>${r.note ? `<small class="${bad ? "neg" : "warnc"}">${esc(r.note)}</small>` : ""}</span>
        <span>${r.eps.toLocaleString()}</span><span>${r.robot}</span>
        <span><span class="badge t-good">Pass</span></span>
        <span class="dl"><span class="bar ${good ? "g" : bad ? "r" : "y"}" style="width:${Math.max(4, Math.abs(r.d) / max * 100)}%"></span><b>${r.d > 0 ? "+" : "−"}${Math.abs(r.d).toFixed(3)}</b></span>
        <span>${r.sim}</span></div>`;
    }).join("")}</div>
    <p class="pv-note">Lower loss change is better. The reference model and the held-out reference set are the same for every dataset. The dataset with the most episodes ranks fourth, and the one with inconsistent labels makes the model worse. That is the point of ranking by effect instead of by count.</p>`;
}

function buildersTab() {
  const max = Math.max(...BUILDERS.map((b) => b.bricks.length));
  return `<div class="towers">${BUILDERS.map((b) => brickStack(b, max)).join("")}</div>
    <div class="legend">${["plain", "task", "robot", "scene", "gold", "dup"].map((k) => `<span><i class="bk k-${k}"></i>${BRICK_NAME[k]}</span>`).join("")}</div>
    <div class="next-brick"><b>@you</b> is 36 clean episodes away from the next brick. A new robot type would add a blue brick right away.</div>`;
}

function wantedTab(esc) {
  return `<div class="wanted">${WANTED.map((w) => `<article class="want">
      <div class="want-top"><h3>${esc(w.t)}</h3><span class="badge t-scope">${esc(w.tag)}</span></div>
      <p>${w.n} episodes · posted by @${esc(w.by)}</p>
      <div class="meter" role="progressbar" aria-valuenow="${w.got}" aria-valuemax="${w.n}"><i style="width:${w.got / w.n * 100}%"></i></div>
      <div class="want-foot"><span>${w.got} of ${w.n} filled</span><span>${esc(w.reward)}</span><button class="btn" data-claim>Claim</button></div></article>`).join("")}</div>`;
}

export function renderLeaderboard({ app, shell, esc, toast }) {
  let tab = "datasets";
  const PANELS = { datasets: datasetsTab, builders: buildersTab, wanted: wantedTab };
  const body = () => `
    <div class="page-head"><div><div class="label">Season 1 · sample data</div><h1>Leaderboard</h1>
      <p>Rewards the data that makes models better, not just the data there's more of.</p></div></div>
    ${banner}
    <div class="rules"><div><b>1</b><span>Pass the smog check. Only clean episodes can earn bricks.</span></div>
      <div><b>2</b><span>One brick per 50 clean episodes. Near-duplicates become flat grey plates that add no height. New tasks, robots and scenes earn a colour bonus.</span></div>
      <div><b>3</b><span>Run a Model Validation. If your data lowers loss on the reference set, you earn gold bricks.</span></div></div>
    <div class="tabs" role="tablist">${[["datasets", "Datasets"], ["builders", "Builders"], ["wanted", "Wanted"]].map(([k, l]) =>
      `<button role="tab" aria-selected="${k === tab}" data-tab="${k}">${l}</button>`).join("")}</div>
    <div class="panel">${PANELS[tab](esc)}</div>`;
  const paint = () => {
    app.innerHTML = shell(body(), "leaderboard");
    app.querySelectorAll("[data-tab]").forEach((b) => (b.onclick = () => { tab = b.dataset.tab; paint(); }));
    app.querySelectorAll("[data-claim]").forEach((b) => (b.onclick = () => toast("Coming soon: claiming isn't built yet")));
  };
  paint();
}

// ---------------------------------------------------------------- model validation

const BT_MODELS = [
  { id: "smolvla", name: "SmolVLA", by: "Hugging Face", gpuh: 1.4, usd: 4, base: 0.214, d: -0.084 },
  { id: "act", name: "ACT", by: "Tony Zhao et al.", gpuh: 0.6, usd: 2, base: 0.262, d: -0.061 },
  { id: "pi0", name: "π0", by: "Physical Intelligence", gpuh: 6.5, usd: 20, base: 0.188, d: -0.072 },
  { id: "groot", name: "GR00T N1.7", by: "NVIDIA", gpuh: 8.0, usd: 26, base: 0.171, d: -0.066 },
];
const SCALING = [[25, 0.208], [50, 0.176], [100, 0.130]];
const STAGES = ["Queued", "Training without your data", "Training with your data", "Scoring on reference set"];

// smooth decaying curve plus a little deterministic wobble, so the sample looks like a real training run
const curve = (s, end, start, k, seed) => end + (start - end) * Math.exp(-k * s) + Math.sin(s * 23 + seed) * 0.006 * Math.exp(-2 * s);

function lossChart(m) {
  const W = 720, H = 360, L = 52, R = 18, T = 16, B = 40;
  const base = m.base, mine = m.base + m.d;
  const x = (s) => L + s * (W - L - R), y = (v) => T + (0.34 - v) / 0.28 * (H - T - B);
  const arr = (end, seed) => Array.from({ length: 61 }, (_, i) => { const s = i / 60; return [x(s).toFixed(1), y(curve(s, end, 0.32, 4.2, seed)).toFixed(1)]; });
  const pts = (end, seed) => arr(end, seed).map((p) => p.join(",")).join(" ");
  const gap = [...arr(base, 1), ...arr(mine, 2).reverse()].map((p) => p.join(",")).join(" ");
  const grid = [0.1, 0.2, 0.3].map((v) => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="gl"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end" class="ax">${v.toFixed(1)}</text>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" class="chart" role="img" aria-label="Loss on the reference set during training. Without your data it ends at ${base.toFixed(3)}, with your data at ${mine.toFixed(3)}.">
    ${grid}<line x1="${L}" x2="${L}" y1="${T}" y2="${H - B}" class="axl"/><line x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}" class="axl"/>
    <text x="${(L + W - R) / 2}" y="${H - 6}" text-anchor="middle" class="ax">training steps →</text>
    <polygon points="${gap}" class="gapfill"/><polyline points="${pts(base, 1)}" class="ln base"/><polyline points="${pts(mine, 2)}" class="ln mine"/>
    <line x1="${W - R - 6}" x2="${W - R - 6}" y1="${y(base)}" y2="${y(mine)}" class="dlt"/>
    <text x="${W - R - 16}" y="${(y(base) + y(mine)) / 2 + 6}" text-anchor="end" class="dltt">Δ ${m.d.toFixed(3)}</text>
    <text x="${x(0.52)}" y="${y(base) - 10}" class="key kb">without your data</text><text x="${x(0.52)}" y="${y(mine) + 22}" class="key km">with your data</text></svg>`;
}

function resultHtml(m) {
  const lo = SCALING[0][1], hi = SCALING[2][1];
  const bars = SCALING.map(([p, v]) => `<div class="sc"><span>${p}% of your episodes</span><div class="sc-bar"><i style="width:${(0.26 - v) / 0.16 * 100}%"></i></div><b>${v.toFixed(3)}</b></div>`).join("");
  return `<section class="bt-result" aria-live="polite">
    <div class="bt-verdict"><div class="bt-mascot" id="btMascot"></div><div><div class="label">Model validation result · ${m.name} · sample data</div>
      <h2>Strong gain: the model got better with your data</h2>
      <p>Loss on the reference set fell by <b>${Math.abs(m.d).toFixed(3)}</b> (${m.base.toFixed(3)} → ${(m.base + m.d).toFixed(3)}), averaged over 3 random seeds. The reference set comes from other people's data, so your own data can't flatter the score.</p></div></div>
    <div class="bt-grid">
      <div class="card"><h3 class="big">Loss on the reference set <small>lower is better</small></h3>${lossChart(m)}</div>
      <div class="card"><h3 class="big">Would more of this data help?</h3><p class="mut">Same training, using only part of your episodes. Loss after training:</p>${bars}
        <p class="tip"><b>Still improving at 100%.</b> The curve hasn't flattened (${lo.toFixed(3)} → ${hi.toFixed(3)}), so recording more episodes like these should keep helping.</p></div>
    </div></section>`;
}

export function renderValidation({ app, shell, esc, mascot, toast }) {
  let sel = "smolvla", running = false;
  const model = () => BT_MODELS.find((m) => m.id === sel);
  const paint = () => {
    const m = model();
    app.innerHTML = shell(`
      <div class="page-head"><div><div class="label">Does your data help a model?</div><h1>Model Validation</h1>
        <p>Train an open model with and without your data, then measure the difference on data you didn't write.</p></div></div>
      ${banner}
      ${running ? `<div class="card bt-progress" role="status"><ol>${STAGES.map((s, i) => `<li class="${i < running - 1 ? "ok" : i === running - 1 ? "now" : ""}">${s}</li>`).join("")}</ol></div>` : ""}
      ${running ? "" : resultHtml(m)}
      <h2 class="bt-h2">Try it on your own dataset</h2>
      <form class="card bt-form" id="btForm" autocomplete="off">
        <label class="fld"><span class="label">Dataset</span>
          <input id="btData" value="lab-alpha/towel_fold" spellcheck="false" aria-describedby="btSmog"><small id="btSmog"><i class="dot good"></i>Smog check: pass. Ready to test.</small></label>
        <fieldset class="fld"><legend class="label">Model to train</legend><div class="models">${BT_MODELS.map((x) =>
          `<label class="mdl${x.id === sel ? " on" : ""}"><input type="radio" name="mdl" value="${x.id}" ${x.id === sel ? "checked" : ""}><b>${esc(x.name)}</b><small>${esc(x.by)}</small><em>~${x.gpuh} GPU-hours · ~$${x.usd}</em></label>`).join("")}</div></fieldset>
        <fieldset class="fld"><legend class="label">What to measure</legend>
          <label class="chk"><input type="checkbox" checked disabled> Loss with and without your data <small>on a held-out reference set</small></label>
          <label class="chk"><input type="checkbox" checked disabled> Data scaling <small>25%, 50% and 100% of your episodes</small></label>
          <label class="chk off"><input type="checkbox" disabled> Simulator success rate <small>coming later</small></label></fieldset>
        <div class="bt-act"><span>Estimated cost <b>~$${m.usd}</b> · queue: 3 ahead</span><button class="btn primary" type="submit" ${running ? "disabled" : ""}>${running ? "Running…" : "Request Model Validation"}</button></div>
      </form>
      <details class="card why"><summary>Why a with-and-without test instead of just showing validation loss?</summary>
        <p>Loss on your own held-out episodes only says how <em>consistent</em> your data is. A thousand copies of the same pick would score perfectly. So the test trains the same model twice, once without your data and once with it, for the same number of steps, then scores both on a fixed reference set that you never see or touch. The difference is the value of your data, and it comes with error bars from repeated seeds.</p>
        <p>Loss can still disagree with real-world success, so the next step is a simulator success rate.</p></details>`, "validation");
    const mm = $("#btMascot"); if (mm) mm.innerHTML = mascot("happy");
    app.querySelectorAll('input[name="mdl"]').forEach((r) => (r.onchange = () => { sel = r.value; paint(); }));
    $("#btForm").onsubmit = (e) => {
      e.preventDefault();
      if (running) return;
      running = 1; paint();
      const tick = setInterval(() => {
        if (++running > STAGES.length) { clearInterval(tick); running = false; toast("Sample result ready"); }
        paint();
      }, 1100);
    };
  };
  const $ = (s) => app.querySelector(s);
  paint();
}
