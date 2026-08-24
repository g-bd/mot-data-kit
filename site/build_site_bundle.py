#!/usr/bin/env python3
"""Assemble the publishing roots — same split as sensor-sal / validation-viewer:

    python site/build_site_bundle.py [--version 0.6.2]

    ../build/site-root/          what Cloudflare Pages serves (the real page):
        index.html               the Hebrew guide, full standalone document (doctype + meta charset)
        index_ascii.html         entity-encoded twin (only if RTL ever garbles through a paste route)
        .htaccess                kept so the same root also works on any Apache host
        downloads/*.zip          the release zips (current version only)

    ../build/wp-upload/          what the MINISTRY host gets — ONE ~2 KB file, uploaded ONCE:
        index.html               pure-ASCII iframe wrapper of the Cloudflare page, with a health
                                 probe and a visible fallback link. A new release changes NOTHING
                                 here — Cloudflare is updated and this file keeps pointing at it.

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
    """The ONE file on the ministry host (public_html/mot-metadata-kit/index.html): a full-viewport
    iframe of the Cloudflare page, with a health probe that reveals a direct link when the host is
    unreachable. Same pattern as /sensor-sal/ and /validation-viewer/. Uploaded ONCE — releases only
    update Cloudflare. Emitted entity-encoded (pure ASCII) so no paste route can garble the Hebrew."""
    t = "מדריך mot-metadata-kit"
    fb = "העמוד אינו נטען כרגע — לפתיחה ישירה: "
    return f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<style>
  html,body{{margin:0;height:100%;background:#0E1B22;color:#EEF3F1;font-family:Arial,sans-serif}}
  iframe{{position:fixed;inset:0;width:100%;height:100%;border:0}}
  #fb{{position:fixed;inset-inline-start:0;inset-inline-end:0;bottom:0;padding:10px 16px;font-size:14px;text-align:center;background:#0E1B22;display:none}}
  #fb a{{color:#5BC6C6}}
</style>
</head>
<body>
<iframe id="app" src="{CF_URL}" title="{t}" allow="fullscreen"></iframe>
<p id="fb">{fb}<a href="{CF_URL}">{CF_URL}</a></p>
<noscript><p style="display:block;position:fixed;bottom:0;inset-inline-start:0;inset-inline-end:0;padding:10px 16px;font-size:14px;text-align:center;background:#0E1B22;color:#EEF3F1">{fb}<a style="color:#5BC6C6" href="{CF_URL}">{CF_URL}</a></p></noscript>
<script>
(function () {{
  // Health probe: if the host does not answer within 6s, surface the direct link.
  var shown = false;
  function show() {{ if (!shown) {{ shown = true; document.getElementById("fb").style.display = "block"; }} }}
  var timer = setTimeout(show, 6000);
  fetch("{CF_URL}", {{ method: "HEAD", mode: "no-cors", cache: "no-store" }})
    .then(function () {{ clearTimeout(timer); }})
    .catch(show);
}})();
</script>
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
    ap.add_argument("--out", default=str(KIT.parent / "build" / "site-root"))
    ap.add_argument("--wp-out", default=str(KIT.parent / "build" / "wp-upload"))
    ap.add_argument("--version", default="0.6.2")
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

    wp = Path(a.wp_out)
    wp.mkdir(parents=True, exist_ok=True)
    (wp / "index.html").write_text(to_html_ascii(wrapper_page()), encoding="ascii", newline="\n")

    for root, label in ((out, "site-root (Cloudflare)"), (wp, "wp-upload (ministry, once)")):
        print(f"  {label}:")
        for f in sorted(root.rglob("*")):
            if f.is_file():
                print(f"    {f.relative_to(root).as_posix():40} {round(f.stat().st_size/1024):>6} KB")
    print(f"cloudflare root: {out}")
    print(f"ministry file:   {wp / 'index.html'}  — upload ONCE as public_html/mot-metadata-kit/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
