"""Package skills/robot-data-smog-check as a standalone Agent Skill: dist/robot-data-smog-check/ and a .zip.

The skill in the repo runs against the repo's conformance/ package. The packaged copy bundles the
stdlib-only modules it needs plus the four vendored GR00T files the contract cites, so it runs
anywhere with Python 3.9+ and no install. Upload the zip as a skill, or copy the folder into
~/.claude/skills/. The zip is also copied to docs/download/, where the README and the web app link it
(GitHub Pages serves it), so commit that copy whenever the skill changes.

    python3 scripts/build_skill.py
"""
from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from conformance import contract as C  # noqa: E402

NAME = "robot-data-smog-check"
SRC = ROOT / "skills" / NAME
DIST = ROOT / "dist"
PUBLISHED = ROOT / "docs" / "download"
MODULES = ["__init__.py", "checks.py", "contract.py", "embodiment.py", "draft.py", "explain.py",
           "manifest.py", "inspect_local.py", "inspect_hub.py", "models.py", "pi05.py"]


def bundle_packaging(dest: Path) -> None:
    """models.py parses versions with `packaging`, as openpi's LeRobot does. Bundle the pure-Python
    package (Apache-2.0 OR BSD-2-Clause) so the packaged skill needs no install."""
    import importlib.metadata as md

    import packaging
    src = Path(packaging.__file__).resolve().parent
    shutil.copytree(src, dest / "packaging", ignore=shutil.ignore_patterns("__pycache__"))
    for f in md.distribution("packaging").files or []:
        if Path(str(f)).name.startswith("LICENSE"):
            shutil.copy2(f.locate(), dest / "packaging" / Path(str(f)).name)
VENDOR = list(C.FILES.values()) + ["LICENSE", "README.md"]


def build() -> Path:
    out = DIST / NAME
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SRC, out, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
    pkg = out / "scripts" / "conformance"
    pkg.mkdir(parents=True)
    for m in MODULES:
        shutil.copy2(ROOT / "conformance" / m, pkg / m)
    vend = out / "scripts" / "vendor" / C.VENDOR_DIR.name
    vend.mkdir(parents=True)
    for f in VENDOR:
        shutil.copy2(C.VENDOR_DIR / f, vend / f)
    bundle_packaging(out / "scripts")
    shutil.copy2(ROOT / "LICENSE", out / "LICENSE")
    (out / "NOTICE").write_text(
        "scripts/conformance/ is MIT (LICENSE), from github.com/vincentstanfordlead/lerobot-groot-conformance.\n"
        f"scripts/vendor/{C.VENDOR_DIR.name}/ holds unmodified files from NVIDIA Isaac-GR00T @{C.GROOT_SHA[:7]} "
        "(Apache-2.0, see the LICENSE there), read only to cite the line each check comes from.\n"
        "scripts/packaging/ is the unmodified `packaging` library (Apache-2.0 OR BSD-2-Clause, licenses inside).\n"
        "The openpi and pi0.5 rules follow openpi @215abfb and LeRobot @0cf8648 (CONTRACT_lerobot_openpi.md in the repo).\n"
        "Independent project, not affiliated with NVIDIA or Hugging Face.\n")
    zpath = DIST / f"{NAME}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(DIST).as_posix())
    PUBLISHED.mkdir(exist_ok=True)
    shutil.copy2(zpath, PUBLISHED / zpath.name)
    return zpath


if __name__ == "__main__":
    z = build()
    print(f"built {z.relative_to(ROOT)} ({z.stat().st_size / 1024:.0f} KB) and {(DIST / NAME).relative_to(ROOT)}/; "
          f"published {(PUBLISHED / z.name).relative_to(ROOT)}")
