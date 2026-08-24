#!/usr/bin/env python3
"""Assemble the upload bundle for the ministry site (mot-roundtbl.org.il/mot-metadata-kit/).

    python site/build_site_bundle.py [--out ../build/wp-upload/metadata-kit] [--version 0.5.0]

Produces, ready to upload into `public_html/mot-metadata-kit/`:

    .htaccess              from site/htaccess.template (LF endings preserved)
    index.html             the Hebrew guide + download buttons for the two zips
    index_ascii.html       the same page with every non-ASCII codepoint as a decimal HTML entity —
                           paste THIS one when the editor/terminal garbles RTL Hebrew
    wrapper-index.html     ~1 KB alternative: an iframe of the Cloudflare Pages copy. Upload it ONCE as
                           index.html and the ministry page follows every later release by itself.
    downloads/*.zip        the release zips (built from the working tree if not found next to it)

Why a folder and not a WordPress page: the host force-redirects anything WordPress renders to
wp-login.php for anonymous visitors. A real file in a real directory is served by Apache, PHP never
boots, and the page is public. Verify anonymously (private window / curl), never while logged in.
"""
from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
ANCHOR = '<span class="chip"><b>mot-fix</b> · תיקונים מכניים</span></div>'
EXCLUDE_TOP = {".git", ".wrangler", "__pycache__", ".pytest_cache", ".claude-plugin", "DEPLOY-he.html", "build"}


CF_URL = "https://mot-metadata-kit.pages.dev/"


def wrapper_page() -> str:
    """The one file the ministry host needs when the real page lives on Cloudflare Pages:
    a full-viewport iframe of CF_URL. Uploaded ONCE — every later release updates Cloudflare and
    this file keeps pointing at it, so nothing is ever re-uploaded to the ministry host.
    Same pattern as /sensor-sal/ and /validation-viewer/ (which iframe their Netlify apps)."""
    t = "מדריך mot-metadata-kit"
    fallback = ("העמוד לא נטעןד - "
                "לפתיחה ישירה:")
    return f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<style>
  html,body{{margin:0;height:100%;background:#0E1B22;color:#EEF3F1;font-family:Arial,sans-serif}}
  iframe{{position:fixed;inset:0;width:100%;height:100%;border:0}}
  .fb{{position:fixed;inset-inline-start:0;inset-inline-end:0;bottom:0;padding:10px 16px;font-size:14px;text-align:center;background:#0E1B22}}
  .fb a{{color:#5BC6C6}}
</style>
</head>
<body>
<iframe src="{CF_URL}" title="{t}" allow="fullscreen"></iframe>
<noscript><p class="fb">{fallback} <a href="{CF_URL}">{CF_URL}</a></p></noscript>
</body>
</html>
"""


def standalone(page: str) -> str:
    """GUIDE-he.html is authored for the artifact host, which injects <!doctype>/<html>/<head>.
    Served raw by Apache (Content-Type: text/html with NO charset) the browser then guesses the
    encoding and Hebrew garbles — so the site copy must be a complete document carrying its own
    <meta charset>, and that charset must sit inside the first 1024 bytes."""
    title = "\u05de\u05d3\u05e8\u05d9\u05da mot-metadata-kit"
    if "<title>" in page:
        title = page.split("<title>", 1)[1].split("</title>", 1)[0]
        page = page.replace(f"<title>{title}</title>\n", "", 1).replace(f"<title>{title}</title>", "", 1)
    desc = ("\u05e2\u05e8\u05db\u05ea skills \u05dc\u05d4\u05e4\u05e6\u05ea \u05de\u05d9\u05d3\u05e2 "
            "\u05ea\u05d7\u05d1\u05d5\u05e8\u05ea\u05d9 \u05e9\u05dc \u05de\u05e9\u05e8\u05d3 "
            "\u05d4\u05ea\u05d7\u05d1\u05d5\u05e8\u05d4")
    return (
        "<!doctype html>\n"
        '<html lang="he" dir="rtl">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n"
        f'<meta name="description" content="{desc}">\n'
        "</head>\n<body>\n" + page + "\n</body>\n</html>\n"
    )


def to_html_ascii(html: str) -> str:
    """Every non-ASCII codepoint as a decimal HTML entity (&#1510;) — survives any paste route."""
    return "".join(ch if ord(ch) < 128 else f"&#{ord(ch)};" for ch in html)


def build_zip(out: Path, prefix: str, include: list[str] | None = None) -> None:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(KIT.rglob("*")):
            rel = p.relative_to(KIT)
            if p.is_dir() or rel.parts[0] in EXCLUDE_TOP or "__pycache__" in rel.parts or ".pytest_cache" in rel.parts:
                continue
            if include and not any(rel.as_posix().startswith(i) for i in include):
                continue
            z.write(p, f"{prefix}/{rel.as_posix()}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(KIT.parent / "build" / "wp-upload" / "mot-metadata-kit"))
    ap.add_argument("--version", default="0.5.0")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "downloads").mkdir(parents=True, exist_ok=True)
    shutil.rmtree(out / ".wrangler", ignore_errors=True)          # wrangler drops its account cache here on deploy
    for stale in (out / "downloads").glob("*.zip"):               # only the current version's zips may be published
        stale.unlink()

    # .htaccess — bytes, so the LF endings survive on Windows
    (out / ".htaccess").write_bytes((KIT / "site" / "htaccess.template").read_bytes())

    full = f"mot-metadata-kit-v{a.version}.zip"
    skill = f"mot-metadata-skill-v{a.version}.zip"
    build_zip(out / "downloads" / full, "mot-metadata-kit")
    build_zip(out / "downloads" / skill, "mot-metadata",
              include=["skills/mot-metadata/", "requirements.txt", "README.md"])

    guide = (KIT / "GUIDE-he.html").read_text(encoding="utf-8")
    if ANCHOR not in guide:
        raise SystemExit("GUIDE-he.html changed: download-strip anchor not found")
    page = guide.replace(ANCHOR, ANCHOR + f'''
    <div class="chips r" style="margin-top:14px">
      <a class="chip" style="text-decoration:none" href="downloads/{full}"><b>⬇ {full}</b> · הערכה המלאה</a>
      <a class="chip" style="text-decoration:none" href="downloads/{skill}"><b>⬇ mot-metadata-skill</b> · skill יחיד לצ'אט</a>
    </div>''', 1)
    doc = standalone(page)
    if "charset" not in doc[:1024]:
        raise SystemExit("charset must sit inside the first 1024 bytes")
    (out / "index.html").write_text(doc, encoding="utf-8", newline="\n")
    (out / "index_ascii.html").write_text(to_html_ascii(doc), encoding="ascii", newline="\n")
    (out / "wrapper-index.html").write_text(to_html_ascii(wrapper_page()), encoding="ascii", newline="\n")

    for f in sorted(out.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(out).as_posix():42} {round(f.stat().st_size/1024):>6} KB")
    print(f"bundle ready: {out}")
    print("upload into public_html/mot-metadata-kit/  —  .htaccess FIRST, on its own, then verify anonymously")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
