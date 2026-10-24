// Browser port of conformance/inspect_hub.py: a metadata-only view of a Hugging Face dataset repo.
// Hugging Face's API sends CORS headers, so this runs entirely in the visitor's browser.
// Differences from the Python CLI (documented in the UI): the data/ + videos/ listing is capped at
// 20,000 entries per folder (the CLI uses 200,000), and the nested-container scan is shallower.
import { MAX_META_BYTES } from "./checks.js";

const HF = "https://huggingface.co";
const META_FILES = ["meta/info.json", "meta/episodes.jsonl", "meta/tasks.jsonl", "meta/modality.json", "meta/stats.json"];
export const LIST_CAP = 20_000;
const NESTED_SCAN_REQUESTS = 12;

export class FetchError extends Error {
  constructor(kind, detail) {
    super(detail);
    this.kind = kind;
  }
}

// Accepts "user/name", "https://huggingface.co/datasets/user/name[/tree/main/...]", "hf.co/datasets/...".
export function parseDatasetId(input) {
  const s = String(input || "").trim().replace(/\/+$/, "");
  const m = s.match(/^(?:https?:\/\/)?(?:www\.)?(?:huggingface\.co|hf\.co)\/datasets\/([^/\s?#]+)\/([^/\s?#]+)/i);
  if (m) return `${m[1]}/${m[2]}`;
  const m2 = s.match(/^([A-Za-z0-9][\w.-]*)\/([\w.-]+)$/);
  return m2 ? `${m2[1]}/${m2[2]}` : null;
}

async function getJSON(url, what, signal) {
  const r = await fetch(url, { signal });
  if (r.status === 401 || r.status === 404) throw new FetchError("not_found_or_private", `${what}: not found, or private/gated (HTTP ${r.status})`);
  if (r.status === 403) throw new FetchError("gated", `${what}: access is gated (HTTP 403)`);
  if (r.status === 429) throw new FetchError("rate_limited", "Hugging Face is rate-limiting this browser. Wait a few minutes and try again.");
  if (!r.ok) throw new FetchError("http_error", `${what}: HTTP ${r.status}`);
  return [await r.json(), r];
}

// Branches and tags of a dataset repo: [{name, commit}]. The LeRobot loaders pick the revision to download from
// these version-named refs, not from info.json (CONTRACT_lerobot_openpi.md §1).
export async function fetchRefs(repoId, signal) {
  const [j] = await getJSON(`${HF}/api/datasets/${repoId}/refs`, "refs", signal);
  return [...(j.branches ?? []), ...(j.tags ?? [])].map((r) => ({ name: r.name, commit: r.targetCommit }));
}

export class HubView {
  // `snapshot` (a commit sha) inspects that exact commit instead of the default branch.
  constructor(repoId, snapshot = null) {
    this.snapshot = snapshot;
    this.repoId = repoId;
    this.files = {};
    this.text = {};
    this.listingComplete = true;
    this.nRequests = 0;
    this.bytesDownloaded = 0;
    this.nestedRoots = [];
  }

  async _tree(path, { recursive, cap = Infinity, folders = false, signal }) {
    const enc = path ? "/" + path.split("/").map(encodeURIComponent).join("/") : "";
    let url = `${HF}/api/datasets/${this.repoId}/tree/${this.sha}${enc}?recursive=${recursive}`;
    const out = [];
    while (url) {
      this.nRequests++;
      let page, r;
      try {
        [page, r] = await getJSON(url, `tree ${path || "/"}`, signal);
      } catch (e) {
        if (e.kind === "not_found_or_private" && out.length === 0) return [];
        throw e;
      }
      for (const e of page) if (folders || e.type === "file") out.push(e);
      if (out.length > cap) break;
      const link = r.headers.get("link") || "";
      const m = link.match(/<([^>]+)>;\s*rel="next"/);
      url = m ? m[1] : null;
    }
    return out;
  }

  async _get(rel, signal) {
    const enc = rel.split("/").map(encodeURIComponent).join("/");
    const r = await fetch(`${HF}/datasets/${this.repoId}/resolve/${this.sha}/${enc}`, { signal });
    this.nRequests++;
    if (!r.ok) throw new FetchError("http_error", `${rel}: HTTP ${r.status} on a listed file`);
    const body = await r.text();
    if (body.length > MAX_META_BYTES) throw new FetchError("oversize_body", `${rel}: body exceeds the 2 MB cap`);
    this.bytesDownloaded += body.length;
    return body;
  }

  // progress(step, detail) is called as each stage completes, for the live log in the UI.
  async load(progress = () => {}, signal) {
    if (this.snapshot) {
      this.sha = this.snapshot;
      progress("repo", `Reading snapshot @${this.sha.slice(0, 7)}`);
    } else {
      this.nRequests++;
      const [info] = await getJSON(`${HF}/api/datasets/${this.repoId}?expand[]=sha&expand[]=gated&expand[]=private&expand[]=disabled&expand[]=lastModified&expand[]=usedStorage`, "dataset info", signal);
      if (info.disabled) throw new FetchError("disabled", "this repo is disabled on Hugging Face");
      this.sha = info.sha;
      this.lastModified = info.lastModified;
      this.usedStorage = info.usedStorage;
      this.gated = info.gated;
      progress("repo", `Found ${this.repoId} @ ${this.sha.slice(0, 7)}`);
    }

    const root = await this._tree(null, { recursive: false, folders: true, signal });
    if (!root.length) throw new FetchError("empty_repo", "the repo has no files");
    const top = new Set(root.map((e) => e.path));
    for (const e of root) if (e.type === "file") this.files[e.path] = e.size;
    if (top.has("meta")) for (const e of await this._tree("meta", { recursive: true, signal })) this.files[e.path] = e.size;
    progress("meta", `Listed meta/ (${Object.keys(this.files).filter((p) => p.startsWith("meta/")).length} files)`);

    let seen = 0;
    for (const d of ["data", "videos"]) {
      if (!top.has(d)) continue;
      const entries = await this._tree(d, { recursive: true, cap: LIST_CAP, signal });
      if (entries.length > LIST_CAP) this.listingComplete = false;
      for (const e of entries.slice(0, LIST_CAP)) this.files[e.path] = e.size;
      seen += Math.min(entries.length, LIST_CAP);
    }
    progress("listing", `Listed data/ and videos/ (${seen.toLocaleString("en-US")} files${this.listingComplete ? "" : ", capped"})`);

    if (!top.has("meta")) {
      // Is this a container of LeRobot datasets in subfolders? Breadth-first, small budget.
      const queue = root.filter((e) => e.type === "directory").map((e) => [e.path, 1]).sort();
      let budget = NESTED_SCAN_REQUESTS;
      while (queue.length && budget-- > 0) {
        const [folder, depth] = queue.shift();
        const kids = await this._tree(folder, { recursive: false, folders: true, signal });
        if (kids.some((k) => k.type === "directory" && k.path.endsWith("/meta"))) {
          this.nestedRoots.push(folder);
          continue;
        }
        if (depth < 4) for (const k of kids) if (k.type === "directory") queue.push([k.path, depth + 1]);
      }
    }

    for (const rel of META_FILES) {
      if (rel in this.files && this.files[rel] <= MAX_META_BYTES) {
        this.text[rel] = await this._get(rel, signal);
        progress("file", `Read ${rel} (${(this.files[rel] / 1024).toFixed(1)} KB)`);
      }
    }
    return this;
  }

  readText(rel) {
    if ((this.files[rel] ?? 0) > MAX_META_BYTES) return null;
    return this.text[rel] ?? null;
  }
}

// A copy of a view with one virtual file replaced, used to re-check with a drafted modality.json.
export function withFile(view, rel, text) {
  return {
    files: { ...view.files, [rel]: text.length },
    listingComplete: view.listingComplete,
    readText: (p) => (p === rel ? text : view.readText(p)),
  };
}
