"""Build a metadata document from a folder scan + intake config (+ optional profile)."""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Any, Optional

from .scan import scan_folder
from .spec import Spec
from .io import split_keywords

TODAY = _dt.date.today().strftime("%d/%m/%Y")
TODO = "TODO"
CONFIG_NAME = "metadata-config.json"

FORMAT_BY_EXT = {".csv": "CSV", ".txt": "TXT", ".tsv": "TSV", ".xlsx": "XLSX", ".xls": "XLS", ".json": "JSON",
                 ".geojson": "GeoJSON", ".shp": "SHP", ".gpkg": "GPKG", ".zip": "ZIP", ".gz": "CSV (gzip)", ".parquet": "Parquet", ".dbf": "DBF"}


def default_config(profile: Optional[str] = None) -> dict:
    """Template for metadata-config.json (the intake answers)."""
    return {
        "profile": profile or None,
        "dataset_kind": "survey | monitoring | administrative | gis | model | other",
        "dataset_name": "short_latin_name_used_for_the_zip",
        "recursive": True,
        "exclude": ["metadata-config.json", "metadata-report.html", "findings.json"],
        "header": {
            "Publisher": "", "Contact": "", "Contact Email": "", "Author": "", "Author Email": "",
            "Title": "", "Description": [""], "Keywords": [], "Created": "", "Frequency of update": "",
            "Version": "1.0", "Last updated": "", "Temporal coverage": "", "Spatial coverage": "",
            "Language": "", "Related documents": [], "References": [], "Legal constrains": [], "License": "",
            "Data quality": "", "Metadata creator": "", "Comments": [], "URL": ""
        },
        "survey": {},
        "files": {"<file name>": {"File description": "", "fields": {"<field>": {"Description": "", "Type": "", "Comments": "", "Values": [{"value": "", "label": ""}]}}}},
        "keys": []
    }


def config_from_metadata(meta: dict, spec: Spec) -> dict:
    """Turn an existing (possibly flawed) metadata document into an intake config, so that
    `build --from old-metadata.xlsx` regenerates a corrected document from the real files."""
    import re as _re
    strip = lambda x: _re.sub(r"[​-‏‪-‮﻿]", "", str(x)).strip()
    header: dict[str, Any] = {}
    skip = {"Files", "Files list", "Dataset file", "Size", "Metadata creation date", "Metadata version", "_meta"}
    for k, v in meta.items():
        if k in skip or k.startswith("_"):
            continue
        if isinstance(v, list):
            header[k] = [strip(x) for x in v if strip(x)]
        else:
            header[k] = strip(v)
    if "Keywords" in header:
        header["Keywords"] = split_keywords(header["Keywords"])
    files: dict[str, Any] = {}
    for fl in meta.get("Files", []):
        name = strip(fl.get("File name", ""))
        if not name:
            continue
        fc: dict[str, Any] = {"fields": {}}
        for k, v in fl.items():
            if k in ("File name", "File fields", "File size", "File date") or k.startswith("_"):
                continue
            if v not in ("", None, []):
                fc[k] = v
        for fd in fl.get("File fields", []):
            fname = strip(fd.get("Name", ""))
            if not fname:
                continue
            entry = {k: fd[k] for k in ("Type", "Description", "Comments") if fd.get(k)}
            if fd.get("Values"):
                entry["Values"] = fd["Values"]
            fc["fields"][fname] = entry
        files[name] = fc
    keys = []
    for k in meta.get("Key list", []) or []:
        k = strip(k)
        if k and k not in keys:
            keys.append(k)
    ds = strip(meta.get("Dataset file", ""))
    return {"header": header, "files": files, "keys": keys, "dataset_name": Path(ds).stem if ds else None}


def load_config(folder: Path, explicit: Optional[Path] = None) -> dict:
    p = explicit or (folder / CONFIG_NAME)
    if p and p.exists():
        with open(p, encoding="utf-8-sig") as f:
            cfg = json.load(f)
        cfg["_path"] = str(p)
        return cfg
    return {}


# --------------------------------------------------------------------------- helpers
def _fmt_of(entry: dict) -> str:
    if entry.get("gtfs"):
        return "GTFS (ZIP)"
    if entry.get("format") == "ZIP" and entry.get("inner") and all(k.lower().endswith(".shp") for k in entry["inner"]):
        return "SHP (ZIP)"
    return entry.get("format") or FORMAT_BY_EXT.get(entry.get("ext", ""), entry.get("ext", "").lstrip(".").upper())


def _bbox_text(bbox: Optional[list]) -> str:
    if not bbox or len(bbox) < 4:
        return ""
    x0, y0, x1, y1 = bbox[:4]
    return f"{x0}, {y0}, {x1}, {y1}"


def _match_expected(name: str, spec: Spec) -> Optional[dict]:
    base = re.sub(r"[​-‏‪-‮﻿]", "", Path(name).name)
    for ef in spec.expected_files:
        pat = ef.get("pattern")
        if pat and re.search(pat, base, re.I):
            return ef
        tmpl = ef["name"]
        rx = "^" + re.escape(tmpl).replace(r"<from>", r"\d{6}").replace(r"<to>", r"\d{6}").replace(r"<survey>", r".+").replace(r"<year>", r"\d{4}") + "$"
        if re.match(rx, base, re.I):
            return ef
    return None


def _expected_fields(ef: Optional[dict], spec: Spec) -> dict[str, dict]:
    if not ef:
        return {}
    flds = ef.get("fields")
    if not flds and ef.get("fields_like"):
        like = next((x for x in spec.expected_files if x["name"] == ef["fields_like"]), None)
        flds = like.get("fields") if like else None
    if not flds:
        flds = ef.get("fields_example_stat_2022", [])
    return {f["Name"].lower(): f for f in flds}


def _field_entry(col: dict, cfg_field: dict, exp: Optional[dict], hint: Optional[dict] = None) -> dict:
    name = col["name"]
    ftype = cfg_field.get("Type") or (exp or {}).get("Type") or col.get("inferred_type") or "Text"
    if col.get("unique_in_sample") and not exp and not cfg_field.get("Type") and re.search(r"(^|_)(id|index|key)$|ID$", name, re.I):
        ftype = f"{ftype}(key)" if "(key)" not in ftype and ftype in ("Integer", "Text") else ftype
    desc = cfg_field.get("Description") or (exp or {}).get("Description")
    auto_doc = None
    if not desc and hint and hint.get("auto"):
        desc, auto_doc = hint["auto"]["text"], hint["auto"]["doc"]
    desc = desc or TODO
    comments = cfg_field.get("Comments") or (exp or {}).get("Comments") or ""
    if not comments and col.get("format_hint") and ftype in ("Date", "Time", "DateTime"):
        comments = col["format_hint"]
    if col.get("n_null", 0) > 0 and "NA" not in comments and "null" not in comments.lower():
        comments = (comments + "; " if comments else "") + f"{col['n_null']}/{col['n_sampled']} ערכים חסרים במדגם"
    fld = {"Name": name, "Type": ftype, "Description": desc, "Comments": comments, "_unique": bool(col.get("unique_in_sample"))}
    if auto_doc:
        fld["_auto_doc"] = auto_doc
    values = cfg_field.get("Values") or (exp or {}).get("Values")
    if values:
        fld["Values"] = [{"value": str(v.get("value", "")), "label": v.get("label", ""), "comment": v.get("comment", "")} for v in values]
    elif col.get("candidate_values") and ftype not in ("Date", "Time", "DateTime", "Real") and not cfg_field and not exp             and (len(col["candidate_values"]) <= 8 or re.search(r"type|code|kind|status|flag|class|categ|mode|dir", name, re.I)):
        # unknown field with few distinct values -> probably coded: list the values, labels left for the user
        fld["Values"] = [{"value": str(v), "label": TODO, "comment": ""} for v in col["candidate_values"]]
        fld["_auto_values"] = True
    return fld


# --------------------------------------------------------------------------- main
def build_metadata(folder: str | Path, spec: Spec, config: Optional[dict] = None, scan: Optional[dict] = None) -> tuple[dict, dict]:
    """Return (metadata, scan). Missing required values are filled with 'TODO' and listed in _meta.todo."""
    folder = Path(folder).resolve()
    cfg = config or {}
    exclude = set(cfg.get("exclude", [])) | {CONFIG_NAME, "metadata-report.html", "findings.json", "scan.json"}
    scan = scan or scan_folder(folder, recursive=bool(cfg.get("recursive", True)), exclude=exclude)
    hdr_cfg = cfg.get("header", {})
    kind = cfg.get("dataset_kind") or spec.dataset_kind or "other"
    include_survey = (kind == "survey") or bool(spec.profile.get("survey_block"))
    todo: list[str] = []
    auto_docs: list[str] = []
    meta: dict[str, Any] = {}

    # ---- logical files (top-level data + documented members of archives)
    logical: list[tuple[str, dict, Optional[dict]]] = []   # (name, entry, parent)
    for e in scan["files"]:
        if e["role"] != "data":
            continue
        logical.append((e["name"], e, None))
        if e.get("format") == "ZIP" and not e.get("gtfs") and not spec.is_delivery_file(e["name"]):
            # a DELIVERY zip (GTFS / licensing container) is carried through unchanged:
            # format Table 5 asks for its name and format, not for a field dictionary of
            # every member a third party wrote (KP-24).
            inner = e.get("inner") or {}
            shp_inner = [k for k in inner if k.lower().endswith(".shp")]
            if len(shp_inner) == 1 and len(inner) == 1:
                continue  # the zip *is* the layer; documented on the zip entry itself
            for member, ie in inner.items():
                logical.append((f"{e['name']}/{member}", ie, e))
    dataset_name = cfg.get("dataset_name") or re.sub(r"[^A-Za-z0-9_]+", "_", folder.name).strip("_") or "dataset"

    # ---- header
    defaults = {
        "Created": TODAY, "Last updated": TODAY, "Metadata creation date": TODAY, "Metadata version": spec.base["spec"]["metadata_version"],
        "Version": "1.0", "Dataset file": f"{dataset_name}.zip", "Size": scan["total_size_mb"],
        "Related documents": list(scan["documents"]),
        "Files list": [n for n, _, _ in logical],
        "Frequency of update": spec.profile.get("default_header", {}).get("Frequency of update"),
        "Language": spec.profile.get("default_header", {}).get("Language"),
        "Spatial coverage": spec.profile.get("default_header", {}).get("Spatial coverage"),
    }
    # sensors: temporal coverage from the package name
    if spec.profile.get("package_pattern"):
        for n, e, _ in logical:
            m = re.match(spec.profile["package_pattern"], Path(n).name)
            if m:
                a, b = m.group(1), m.group(2)
                defaults["Temporal coverage"] = f"{a[4:6]}/{a[2:4]}/20{a[0:2]} - {b[4:6]}/{b[2:4]}/20{b[0:2]}"
                defaults["Title"] = f"נתוני גלאי תנועה בפורמט אחוד – {a[2:4]}/20{a[0:2]}"
                defaults["Dataset file"] = Path(n).name
                break
    kw_default = list(spec.profile.get("default_keywords", []))

    for item in spec.header_keys(include_survey):
        key, kindk = item["key"], item.get("kind")
        if key == "Files":
            continue
        src = hdr_cfg.get(key, cfg.get("survey", {}).get(key))
        val: Any = src if src not in (None, "", [], [""]) else defaults.get(key)
        if key == "Keywords":
            val = split_keywords(src) if src else kw_default
        if val in (None, "", [], [""]):
            if item["status"] == "required" or (item["status"] == "required*" and key in ("Files list", "Key list", "Version")):
                if key == "Key list":
                    val = []
                else:
                    val = [TODO] if kindk in ("block",) else ([TODO] if kindk == "array" else TODO)
                    todo.append(key)
            else:
                continue
        if kindk in ("block", "array", "files") and not isinstance(val, list):
            val = [str(val)]
        meta[key] = val

    # ---- files
    _clean = lambda x: re.sub(r"[​-‏‪-‮﻿]", "", str(x)).strip().lower()
    files_cfg = {_clean(k): v for k, v in cfg.get("files", {}).items()}
    files_out: list[dict] = []
    for name, e, parent in logical:
        fcfg = files_cfg.get(_clean(name)) or files_cfg.get(_clean(Path(name).name)) or {}
        ef = _match_expected(name, spec)
        exp_fields = _expected_fields(ef, spec)
        fl: dict[str, Any] = {"File name": name, "File format": fcfg.get("File format") or _fmt_of(e)}
        desc = fcfg.get("File description") or (ef or {}).get("desc")
        dh = e.get("doc_hints") or {}
        if not desc and dh.get("file", {}).get("auto"):
            desc = dh["file"]["auto"]["text"]
            auto_docs.append(f"{name}: File description ← {dh['file']['auto']['doc']}")
        if not desc and e.get("format") == "ZIP" and spec.profile.get("package_pattern") and re.match(spec.profile["package_pattern"], Path(name).name):
            desc = spec.profile.get("package_desc") or "קובץ אצווה חודשי (ZIP) המכיל את שלוש טבלאות הפורמט"
        if parent is not None:
            fl["File comments"] = f"בתוך הארכיון {parent['name']}"
        if not desc:
            desc = TODO
            todo.append(f"{name}: File description")
        fl["File description"] = desc
        if e.get("size_mb") is not None:
            fl["File size"] = e.get("size_mb_all", e["size_mb"])
        if e.get("modified"):
            fl["File date"] = e["modified"]
        if e.get("encoding"):
            fl["Data encoding"] = {"utf-8-sig": "UTF-8 (BOM)", "utf-8": "UTF-8", "cp1255": "Windows-1255"}.get(e["encoding"], e["encoding"])
        # GIS keys
        gis = e if e.get("kind") == "gis" else None
        if not gis and e.get("format") == "ZIP" and e.get("inner"):
            shp_inner = [v for k, v in e["inner"].items() if k.lower().endswith(".shp")]
            if len(shp_inner) == 1 and len(e["inner"]) == 1:
                gis = shp_inner[0]
        if gis:
            crs = (gis.get("crs") or {}).get("mot_value")
            fl["Spatial reference system"] = fcfg.get("Spatial reference system") or crs or TODO
            fl["Geographic bounding"] = fcfg.get("Geographic bounding") or _bbox_text(gis.get("bbox")) or TODO
            fl["Geographic type"] = fcfg.get("Geographic type") or gis.get("geometry_type") or TODO
            if ef and ef.get("gis") and spec.profile_name == "onboard":
                fl["Zones type"] = fcfg.get("Zones type") or TODO
            for k in ("Spatial reference system", "Geographic bounding", "Geographic type", "Zones type"):
                if fl.get(k) == TODO:
                    todo.append(f"{name}: {k}")
        for k, v in fcfg.items():
            if k not in fl and k not in ("fields", "File description") and not k.startswith("_"):
                fl[k] = v
        # fields
        cols = (gis or e).get("fields") or []
        if e.get("gtfs"):
            cols = []
            fl["File comments"] = (fl.get("File comments", "") + "; " if fl.get("File comments") else "") + "פורמט GTFS סטנדרטי – אין צורך בתיעוד השדות"
        elif not gis and spec.is_delivery_file(name):
            cols = []
            n_members = e.get("n_members") or len(e.get("members") or [])
            fl["File comments"] = (fl.get("File comments", "") + "; " if fl.get("File comments") else "") \
                + f"קובץ הפצה המועבר כפי שהוא ({n_members} קבצים בארכיון) – לפי טבלה 5 אין חובה לתעד את שדותיו"
        fields_cfg = {k.lower(): v for k, v in (fcfg.get("fields") or {}).items()}
        field_hints = (dh.get("fields") or {}) if not gis else ((gis.get("doc_hints") or {}).get("fields") or dh.get("fields") or {})
        fl["File fields"] = []
        for col in cols:
            fe = _field_entry(col, fields_cfg.get(col["name"].lower(), {}), exp_fields.get(col["name"].lower()), field_hints.get(col["name"]))
            if fe["Description"] == TODO:
                todo.append(f"{name}.{col['name']}: Description")
            if fe.pop("_auto_doc", None):
                auto_docs.append(f"{name}.{col['name']}: Description ← {field_hints[col['name']]['auto']['doc']}")
            fl["File fields"].append(fe)
        files_out.append(fl)
    meta["Files"] = files_out

    # ---- key list
    keys = list(cfg.get("keys") or [])
    auto_keys: list[str] = []
    if not keys:
        # profile expected keys, instantiated with real file names
        names = [f["File name"] for f in files_out]
        for k in spec.expected_keys:
            m = re.match(r"^(.+?)\.([^.>]+?)\s*->\s*(.+?)\.([^.]+?)$", k.strip())
            if not m:
                continue
            fa, ca, fb, cb = m.groups()
            ra = next((n for n in names if _match_expected(n, spec) and _match_expected(n, spec)["name"] == fa), None)
            rb = next((n for n in names if _match_expected(n, spec) and _match_expected(n, spec)["name"] == fb), None)
            if ra and rb:
                keys.append(f"{ra}.{ca} -> {rb}.{cb}")
        if not keys:
            # heuristic: identical id-like field names shared by two files, unique in one of them
            by_name: dict[str, list[tuple[str, dict]]] = {}
            for fl in files_out:
                for fe in fl["File fields"]:
                    if re.search(r"(^|_)(id|index|key|code)$|ID$|_id_", fe["Name"], re.I):
                        by_name.setdefault(fe["Name"].lower(), []).append((fl["File name"], fe))
            for fname, occ in by_name.items():
                if len(occ) < 2:
                    continue
                keyed = [o for o in occ if o[1].get("_unique")]
                if not keyed:
                    continue
                parent = keyed[0]
                for o in occ:
                    if o is parent:
                        continue
                    auto_keys.append(f"{parent[0]}.{parent[1]['Name']} -> {o[0]}.{o[1]['Name']}")
            keys = auto_keys
    if keys or "Key list" in meta:
        meta["Key list"] = keys
    for fl in files_out:
        for fe in fl["File fields"]:
            fe.pop("_unique", None)
    meta["_meta"] = {
        "guideline_version": spec.base["spec"]["version"], "metadata_version": spec.base["spec"]["metadata_version"],
        "profile": spec.profile_name, "profile_version": (spec.profile.get("spec") or {}).get("version"),
        "dataset_kind": kind, "survey_block": include_survey, "generated": _dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "folder": str(folder), "todo": todo, "auto_keys": auto_keys, "auto_from_docs": auto_docs,
    }
    return meta, scan


def suggested_metadata_basename(meta: dict, cfg: dict, spec: Optional[Spec] = None) -> str:
    ds = cfg.get("dataset_name") or Path(str(meta.get("Dataset file", "dataset.zip"))).stem
    pattern = (spec.profile.get("metadata_basename") if spec else None) or "{name}-metadata"
    return pattern.format(name=ds)
