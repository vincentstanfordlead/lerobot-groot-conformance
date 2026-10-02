// Run the browser checks (docs/app/checks.js) on a local dataset dir; print JSON. Used by test_js_parity.py.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { runAll, MAX_META_BYTES } from "../docs/app/checks.js";

const root = process.argv[2];
const files = {};
(function walk(d) {
  for (const n of readdirSync(d)) {
    const p = join(d, n);
    const s = statSync(p);
    if (s.isDirectory()) walk(p);
    else files[relative(root, p).split(sep).join("/")] = s.size;
  }
})(root);
const view = { files, readText: (rel) => (files[rel] > MAX_META_BYTES ? null : readFileSync(join(root, rel), "utf8")) };
const r = runAll(view);
delete r.info;
console.log(JSON.stringify(r));
