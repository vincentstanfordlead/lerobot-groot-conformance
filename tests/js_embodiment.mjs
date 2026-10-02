// Classify every cached info.json with docs/app/embodiment.js; print {dataset: result}. Used by test_js_parity.py.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { classifyEmbodiment } from "../docs/app/embodiment.js";
const root = process.argv[2], out = {};
(function walk(d) {
  for (const n of readdirSync(d)) {
    const p = join(d, n);
    if (statSync(p).isDirectory()) walk(p);
    else if (p.endsWith(".json")) {
      const id = relative(root, p).slice(0, -5);
      out[id] = classifyEmbodiment(JSON.parse(readFileSync(p, "utf8")), id);
    }
  }
})(root);
console.log(JSON.stringify(out));
