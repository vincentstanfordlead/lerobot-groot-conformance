// Tier every cached info.json with docs/app/draft.js; print {dataset: worst tier}. Used by test_js_parity.py.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { featureTier } from "../docs/app/draft.js";
const TIERS = ["no_state_or_action_feature", "no_names", "names_unusable", "opaque_names", "fragmented_groups", "looks_inferable"];
const root = process.argv[2], out = {};
(function walk(d) {
  for (const n of readdirSync(d)) {
    const p = join(d, n);
    if (statSync(p).isDirectory()) walk(p);
    else if (p.endsWith(".json")) {
      const info = JSON.parse(readFileSync(p, "utf8"));
      const feats = info && typeof info.features === "object" && info.features ? info.features : {};
      const tiers = ["observation.state", "action"].map((k) => featureTier(feats, k).tier);
      out[relative(root, p).slice(0, -5)] = tiers.reduce((a, b) => (TIERS.indexOf(a) <= TIERS.indexOf(b) ? a : b));
    }
  }
})(root);
console.log(JSON.stringify(out));
