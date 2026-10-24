// Run the browser LeRobot/openpi/π0.5 logic (docs/app/models.js) on cases from a JSON file; print JSON.
// Used by test_js_parity.py. Input: { cases: [{checks, info, refNames}], selections: [[refName...]] }.
import { readFileSync } from "node:fs";
import { facts, lerobotVerdict, openpiVerdict, pi05Fit, parseVersions, selectRevision, LEROBOT_TARGET, OPENPI_TARGET } from "../docs/app/models.js";

const { cases, selections } = JSON.parse(readFileSync(process.argv[2], "utf8"));
const verdicts = cases.map((c) => {
  const f = facts(c.checks, c.info, c.refNames);
  return { lerobot: lerobotVerdict(f), openpi: openpiVerdict(f), pi05: pi05Fit(c.info) };
});
const sel = selections.map((names) => {
  const hub = parseVersions(names);
  return [selectRevision(hub, LEROBOT_TARGET), selectRevision(hub, OPENPI_TARGET)];
});
console.log(JSON.stringify({ verdicts, selections: sel }));
