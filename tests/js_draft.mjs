// Draft modality.json for every cached info.json with docs/app/draft.js; print {dataset: result}. Used by test_skill.py.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { draftModality, formatModality } from "../docs/app/draft.js";
const root = process.argv[2], out = {};
(function walk(d) {
  for (const n of readdirSync(d)) {
    const p = join(d, n);
    if (statSync(p).isDirectory()) walk(p);
    else if (p.endsWith(".json")) {
      const r = draftModality(JSON.parse(readFileSync(p, "utf8")));
      out[relative(root, p).slice(0, -5)] = { ...r, text: r.ok ? formatModality(r.draft) : null };
    }
  }
})(root);
console.log(JSON.stringify(out));
