#!/usr/bin/env python3
"""mot_hook - the "generate MoT metadata for this export folder" step that other pipelines call.

Designed to be embedded in an existing export pipeline (google-agg-v2, counts-v2, ...):
it NEVER raises and NEVER fails the caller. Everything it can answer it answers from the folder
itself + a stored config; whatever it cannot it leaves as TODO and reports.

    python mot_hook.py <output_folder> [--profile onboard|sensors] [--config path.json]
                       [--name dataset_name] [--formats json,xlsx,pdf] [--deep values,temporal]
                       [--json]           # print a machine-readable result line

Config resolution (first hit wins):
    --config <path>
    <output_folder>/metadata-config.json
    $MOT_METADATA_CONFIG
    <output_folder>/../metadata-config.json ... up to 3 levels (a per-scope config next to the months)

Result JSON: {"status": "ok|todo|skipped|error", "folder", "metadata", "report", "errors",
              "warnings", "todo", "message"}
  ok      - metadata written, no errors
  todo    - metadata written but intake answers are missing (the report lists them)
  skipped - nothing to document (empty folder) or dependencies unavailable
  error   - the step failed; the caller should keep going regardless
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _find_config(folder: Path, explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    local = folder / "metadata-config.json"
    if local.exists():
        return local
    env = os.environ.get("MOT_METADATA_CONFIG")
    if env and Path(env).exists():
        return Path(env)
    up = folder
    for _ in range(3):
        up = up.parent
        cand = up / "metadata-config.json"
        if cand.exists():
            return cand
    return None


def run(folder: str | Path, profile: str | None = None, config: str | None = None, name: str | None = None,
        formats: str = "json,xlsx", deep: str = "") -> dict:
    folder = Path(folder).resolve()
    out = {"status": "error", "folder": str(folder), "metadata": None, "report": None,
           "errors": None, "warnings": None, "todo": None, "message": ""}
    try:
        if not folder.is_dir():
            out.update(status="skipped", message="folder does not exist")
            return out
        from motmeta.spec import Spec
        from motmeta.build import build_metadata, load_config, suggested_metadata_basename
        from motmeta.io import write_json, write_xlsx, metadata_html, html_to_pdf
        from motmeta.validate import validate
        from motmeta.report import render_report, write_findings_json

        cfg_path = _find_config(folder, config)
        cfg = {}
        if cfg_path:
            with open(cfg_path, encoding="utf-8-sig") as f:
                cfg = json.load(f)
            cfg.pop("_path", None)
        profile = profile or cfg.get("profile")
        spec = Spec(profile)
        if name:
            cfg["dataset_name"] = name
        meta, scan = build_metadata(folder, spec, cfg)
        if not meta.get("Files"):
            out.update(status="skipped", message="no data files to document")
            return out
        base = suggested_metadata_basename(meta, cfg, spec)
        include_survey = meta["_meta"]["survey_block"]
        written = {}
        for fmt in [f.strip() for f in formats.split(",") if f.strip()]:
            target = folder / f"{base}.{fmt}"
            if fmt == "json":
                write_json(meta, target)
            elif fmt == "xlsx":
                write_xlsx(meta, target, spec, include_survey)
            elif fmt == "pdf":
                ok, _msg = html_to_pdf(metadata_html(meta, spec, include_survey), target)
                if not ok:
                    target = folder / f"{base}.html"
                    target.write_text(metadata_html(meta, spec, include_survey), encoding="utf-8")
            elif fmt == "html":
                target.write_text(metadata_html(meta, spec, include_survey), encoding="utf-8")
            else:
                continue
            written[fmt] = str(target)
        deep_set = {x.strip() for x in deep.split(",") if x.strip()}
        fx, summary = validate(meta, spec, folder, scan, deep=deep_set)
        report = folder / "metadata-report.html"
        report.write_text(render_report(fx, summary, meta, scan, spec.describe()), encoding="utf-8")
        write_findings_json(fx, summary, folder / "findings.json")
        todo = meta["_meta"]["todo"]
        out.update(status="todo" if (todo or summary["counts"]["error"]) else "ok",
                   metadata=written.get("xlsx") or written.get("json"), report=str(report),
                   errors=summary["counts"]["error"], warnings=summary["counts"]["warning"], todo=len(todo),
                   message=(f"{len(todo)} intake answers missing" if todo else
                            (f"{summary['counts']['error']} errors" if summary["counts"]["error"] else "clean")))
        if not cfg_path:
            out["message"] += "; no metadata-config.json found - header values are TODO"
        return out
    except Exception as e:                      # never fail the caller
        out["message"] = f"{type(e).__name__}: {e}"
        return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--profile")
    ap.add_argument("--config")
    ap.add_argument("--name")
    ap.add_argument("--formats", default="json,xlsx")
    ap.add_argument("--deep", default="")
    ap.add_argument("--json", action="store_true", help="print the result as one JSON line")
    a = ap.parse_args(argv)
    res = run(a.folder, a.profile, a.config, a.name, a.formats, a.deep)
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        try:
            print(f"mot metadata: {res['status']} - {res['message']} ({res.get('metadata')})")
        except UnicodeEncodeError:
            print(f"mot metadata: {res['status']}")
    return 0                                    # always 0: a metadata step must not break an export


if __name__ == "__main__":
    sys.exit(main())
