#!/usr/bin/env python3
"""One command to cut a release of mot-metadata-kit: test → version → zips → GitHub → site bundle
→ (optional) Cloudflare Pages.

    python site/release.py --version 0.6.0                 # dry run: shows every step, changes nothing remote
    python site/release.py --version 0.6.0 --publish       # really tag, push, create the GitHub release
    python site/release.py --version 0.6.0 --publish --cloudflare   # ...and deploy the page to Cloudflare Pages

Steps
  1. pytest must pass (skip with --skip-tests, and say why in the release notes).
  2. version stamped into .claude-plugin/plugin.json + marketplace.json, and into the guide's version chip.
  3. zips built from the working tree, excluding .git, __pycache__, .claude-plugin and internal pages.
  4. git commit (if the tree is dirty), tag vX.Y.Z, push both — then a GitHub release with the two zips.
     Uses `gh` when it is authenticated; otherwise the REST API with the token from `git credential fill`.
  5. site bundle rebuilt into ../build/wp-upload/mot-metadata-kit/ (upload it to the ministry host).
  6. --cloudflare: `wrangler pages deploy` of that bundle to the project named by --cf-project
     (default `mot-metadata-kit`). Requires wrangler + a Cloudflare login; nothing is created for you.

Never force-pushes, never deletes a release, and refuses to publish a version that already has a tag.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
REPO = "g-bd/mot-metadata-kit"
GH_EXE = r"C:\Program Files\GitHub CLI\gh.exe"


def run(cmd: list[str], cwd: Path | None = None, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    print("   $", " ".join(str(c) for c in cmd))
    r = subprocess.run(cmd, cwd=cwd or KIT, capture_output=capture, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        print((r.stdout or "") + (r.stderr or ""))
        raise SystemExit(f"failed: {' '.join(str(c) for c in cmd)}")
    return r


def github_token() -> str:
    r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                       capture_output=True, text=True)
    for line in (r.stdout or "").splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise SystemExit("no GitHub token in the credential store — run `gh auth login` once")


def stamp_version(version: str) -> None:
    for rel in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
        p = KIT / rel
        d = json.loads(p.read_text(encoding="utf-8"))
        if "version" in d:
            d["version"] = version
        if "metadata" in d and isinstance(d["metadata"], dict):
            d["metadata"]["version"] = version
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    guide = KIT / "GUIDE-he.html"
    s = guide.read_text(encoding="utf-8")
    s = re.sub(r"(<span>v)\d+\.\d+(?:\.\d+)?(</span>)", rf"\g<1>{'.'.join(version.split('.')[:2])}\g<2>", s, count=1)
    s = re.sub(r"mot-metadata-kit-v\d+\.\d+\.\d+\.zip", f"mot-metadata-kit-v{version}.zip", s)
    s = re.sub(r"mot-metadata-skill-v\d+\.\d+\.\d+\.zip", f"mot-metadata-skill-v{version}.zip", s)
    guide.write_text(s, encoding="utf-8")
    print(f"   stamped v{version} into the manifests and the guide")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", required=True)
    ap.add_argument("--notes", default="", help="extra release notes (markdown)")
    ap.add_argument("--publish", action="store_true", help="actually tag, push and create the GitHub release")
    ap.add_argument("--cloudflare", action="store_true", help="also deploy the site bundle to Cloudflare Pages")
    ap.add_argument("--cf-project", default="mot-metadata-kit")
    ap.add_argument("--skip-tests", action="store_true")
    a = ap.parse_args()
    version, tag = a.version.lstrip("v"), f"v{a.version.lstrip('v')}"
    print(f"== release {tag} {'(publishing)' if a.publish else '(dry run)'}")

    print("[1/6] tests")
    if a.skip_tests:
        print("   skipped")
    else:
        run([sys.executable, "-m", "pytest", "tests", "-q"], capture=False)

    print("[2/6] version")
    if run(["git", "tag", "-l", tag]).stdout.strip() and a.publish:
        raise SystemExit(f"tag {tag} already exists — bump the version")
    stamp_version(version)

    print("[3/6] site bundle + zips")
    run([sys.executable, str(KIT / "site" / "build_site_bundle.py"), "--version", version], capture=False)
    bundle = KIT.parent / "build" / "wp-upload" / "mot-metadata-kit"
    zips = [bundle / "downloads" / f"mot-metadata-kit-v{version}.zip",
            bundle / "downloads" / f"mot-metadata-skill-v{version}.zip"]
    for z in zips:
        if not z.exists():
            raise SystemExit(f"missing {z}")

    print("[4/6] git")
    dirty = bool(run(["git", "status", "--porcelain"]).stdout.strip())
    if not a.publish:
        print("   dry run — would commit" if dirty else "   dry run — tree clean")
    else:
        if dirty:
            run(["git", "add", "-A"])
            run(["git", "commit", "-m", f"release {tag}"])
        run(["git", "tag", "-a", tag, "-m", tag])
        run(["git", "push", "origin", "main"])
        run(["git", "push", "origin", tag])

    print("[5/6] GitHub release")
    notes = (f"Bundled specs: data-distribution guideline v1.3, on-board survey format v1.0, "
             f"traffic-sensor format v1.02.\n\n- `{zips[0].name}` — the full kit\n- `{zips[1].name}` — the generic skill only"
             + (f"\n\n{a.notes}" if a.notes else ""))
    if not a.publish:
        print("   dry run — would create the release with:", ", ".join(z.name for z in zips))
    elif Path(GH_EXE).exists():
        env_token = github_token()
        cmd = [GH_EXE, "release", "create", tag, "-R", REPO, "--title", f"mot-metadata-kit {tag}", "--notes", notes, *[str(z) for z in zips]]
        print("   $ gh release create", tag)
        r = subprocess.run(cmd, capture_output=True, text=True, env={**__import__("os").environ, "GH_TOKEN": env_token})
        print("  ", (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr).strip() else "")
        if r.returncode != 0:
            raise SystemExit("gh release failed")
    else:
        raise SystemExit("gh not found — install it or create the release manually")

    print("[6/6] Cloudflare Pages")
    if not a.cloudflare:
        print("   skipped (no Cloudflare host is set up for this kit; use --cloudflare once you create the project)")
    else:
        r = subprocess.run(["npx", "wrangler", "pages", "deploy", str(bundle), "--project-name", a.cf_project],
                           capture_output=True, text=True, shell=True)
        print("  ", (r.stdout or r.stderr).strip()[-400:])
        if r.returncode != 0:
            print("   Cloudflare deploy failed — the GitHub release above is unaffected")

    print(f"\ndone. Ministry host: upload {bundle} into public_html/mot-metadata-kit/ "
          f"(index.html + downloads/, .htaccess only if it is not there yet), then verify anonymously:")
    print("   curl -sIL https://mot-roundtbl.org.il/mot-metadata-kit/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
