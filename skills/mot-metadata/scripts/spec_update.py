#!/usr/bin/env python3
"""spec_update - compare a newly published spec document (PDF / DOCX / MD / TXT) with the bundled dictionary and
propose what to change. Nothing is modified: the output is a markdown diff for a human to approve, then the JSON
(references/spec.json or a profile.json) is edited by hand / by the agent.

  python spec_update.py <new-spec.pdf|docx|md> [--profile onboard|sensors] [--out spec-diff.md]

What it does
  1. extracts text + tables (pdfplumber / python-docx, optional) and finds the version/date strings;
  2. collects every "key-like" English token that appears in a table row together with a status word
     (required / optional / required*), and the row's type word (value / block / array);
  3. compares with the bundled keys: NEW keys (in the document, not in the JSON), MISSING keys (in the JSON, not found
     in the document - maybe renamed/removed), STATUS or KIND changes;
  4. for profiles: also compares expected file names (xxx.csv / xxx.zip) and field names listed in the document;
  5. writes a markdown report with a ready-to-paste JSON snippet for the new keys.

Hebrew PDFs extract with reversed letters; the comparison only relies on the Latin tokens, which survive.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from motmeta.spec import Spec  # noqa: E402
from motmeta.docs import read_doc_text  # noqa: E402

STATUS_RE = re.compile(r"\b(required\*|required|optional)\b", re.I)
KIND_RE = re.compile(r"\b(value|block|array)\b", re.I)
KEY_RE = re.compile(r"\b([A-Z][A-Za-z]+(?:\s+[A-Za-z][A-Za-z]+){0,3})\b")
FIELD_RE = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b")
FILE_RE = re.compile(r"\b([A-Za-z0-9_<>\-]+\.(?:csv|zip|shp|xlsx|pdf|json|txt))\b")
VERSION_RE = re.compile(r"(?:version|גרסה|הסרג)\s*:?\s*(\d+\.\d+)", re.I)
DATE_RE = re.compile(r"\b(\d{1,2}[./]\d{1,2}[./]\d{4})\b")
NOISE = {"Table", "Figure", "Excel", "Shapefile", "Polygon", "Point", "Polyline", "Text", "Integer", "Real", "Date", "Time", "DateTime", "Number", "String", "Null", "Parameter", "MB", "EPSG", "ITM", "WGS", "GRS", "File", "Value", "Block", "Array", "CSV", "JSON", "SHP", "UTF", "Windows", "URL", "GTFS"}
KINDWORDS = ("value", "block", "array")


def _out(m):
    try:
        print(m)
    except UnicodeEncodeError:
        print(m.encode("utf-8", "replace").decode("ascii", "replace"))


def extract_rows(text: str) -> list[dict]:
    rows = []
    for ln in text.splitlines():
        st = STATUS_RE.search(ln)
        if not st:
            continue
        kind = KIND_RE.search(ln)
        keys = []
        for k in KEY_RE.findall(ln):
            words = [w for w in k.split() if w.lower() not in KINDWORDS and w not in NOISE]
            k2 = " ".join(words).strip()
            if k2 and k2.lower() not in ("required", "optional") and k2 not in NOISE:
                keys.append(k2)
        for k in keys:
            rows.append({"key": k, "status": st.group(1).lower(), "kind": (kind.group(1).lower() if kind else None), "line": ln.strip()[:160]})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("document")
    ap.add_argument("--profile")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    doc = Path(a.document)
    text = read_doc_text(doc)
    if not text:
        _out("could not read the document (pdfplumber / python-docx installed?)")
        return 2
    spec = Spec(a.profile)
    bundled = {it["key"]: it for it in spec.header} | {it["key"]: it for it in spec.survey} | {it["key"]: it for it in spec.file} | {it["key"]: it for it in spec.field}
    bundled_version = (spec.profile.get("spec") or spec.base["spec"])["version"]
    versions = sorted(set(VERSION_RE.findall(text)))
    dates = DATE_RE.findall(text)[:5]
    rows = extract_rows(text)
    found: dict[str, dict] = {}
    for r in rows:
        found.setdefault(r["key"], r)
    norm = lambda s: re.sub(r"\s+", " ", s.lower()).strip()
    bn = {norm(k): k for k in bundled}
    fn = {norm(k): k for k in found}
    def match(nk: str):
        """exact, or the document token is a prefix/suffix of a bundled multi-word key (PDF line breaks)."""
        if nk in bn:
            return bn[nk]
        cands = [b for b in bn if b.startswith(nk + " ") or b.endswith(" " + nk) or nk.startswith(b + " ")]
        if len(cands) == 1:
            return bn[cands[0]]
        if cands:  # ambiguous prefix (PDF line break) - counts as covering all candidates, never as "new"
            return [bn[c] for c in cands]
        return None
    matched = {k: match(nk) for nk, k in fn.items()}
    new = [found[k] for k, m in matched.items() if m is None and len(k) > 2]
    covered = set()
    for m in matched.values():
        if isinstance(m, list):
            covered.update(m)
        elif m:
            covered.add(m)
    matched = {k: (m if not isinstance(m, list) else None) for k, m in matched.items()}
    missing = [bundled[k] for k in bundled if k not in covered]
    changed = []
    for k, m in matched.items():
        if m:
            nk = norm(k)
            b = bundled[m]
            r = found[k]
            if r["status"] != b.get("status") or (r["kind"] and b.get("kind") in ("value", "block", "array") and r["kind"] != b.get("kind")):
                changed.append({"key": bn[nk], "bundled": {"status": b.get("status"), "kind": b.get("kind")}, "document": {"status": r["status"], "kind": r["kind"]}, "line": r["line"]})
    # profile extras: files & fields
    files_doc = sorted(set(FILE_RE.findall(text)))
    fields_doc = sorted(set(FIELD_RE.findall(text)))
    exp_files = {e["name"] for e in spec.expected_files}
    exp_fields = {f["Name"] for e in spec.expected_files for f in (e.get("fields") or [])}
    new_files = [f for f in files_doc if f not in exp_files and not f.lower().startswith(("metadata", "xxx"))] if spec.profile else []
    new_fields = [f for f in fields_doc if f not in exp_fields] if spec.profile else []
    lines = [f"# spec-update: {doc.name} vs bundled {spec.profile_name} v{bundled_version}", "",
             f"- versions mentioned in the document: {', '.join(versions) or '—'}; dates: {', '.join(dates) or '—'}",
             f"- key rows detected: {len(rows)} (distinct keys {len(found)})", ""]
    lines.append("## NEW keys (in document, not bundled)")
    lines += [f"- **{r['key']}** — {r['status']} / {r['kind'] or '?'}  ←  `{r['line']}`" for r in new] or ["- none"]
    lines += ["", "## Bundled keys NOT found in the document (renamed? removed? check manually)"]
    lines += [f"- {b['key']} ({b.get('status')})" for b in missing] or ["- none"]
    lines += ["", "## Status / kind differences"]
    lines += [f"- **{c['key']}**: bundled {c['bundled']} → document {c['document']}  ←  `{c['line']}`" for c in changed] or ["- none"]
    if spec.profile:
        lines += ["", "## Profile: file names in document not in expected_files", *([f"- {f}" for f in new_files] or ["- none"]),
                  "", "## Profile: snake_case field names in document not in any expected file", *([f"- {f}" for f in new_fields[:80]] or ["- none"])]
    if new:
        snippet = [{"key": r["key"], "he": "", "kind": r["kind"] or "value", "status": r["status"], "desc": ""} for r in new]
        lines += ["", "## JSON snippet for the new keys (add to header / survey / file as appropriate, then fill `he`/`desc`)", "```json", json.dumps(snippet, ensure_ascii=False, indent=2), "```"]
    lines += ["", "After approving: update references/*.md, the JSON, and spec-sources.json (version + date)."]
    out = Path(a.out) if a.out else doc.with_name(doc.stem + "-spec-diff.md")
    out.write_text("\n".join(lines), encoding="utf-8")
    _out(f"new={len(new)} missing={len(missing)} changed={len(changed)} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
