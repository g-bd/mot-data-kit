"""Validate a metadata document against the נוהל dictionary, a profile, and the folder it describes.

Only structure / completeness / consistency is checked - never the correctness of the data itself.
Each finding: {severity, section, where, code, msg, detail, fix, bucket?}
  severity: error (the נוהל is violated) | warning (probably wrong / incomplete) | info (suggestion)
  bucket:   optional label. `kit_format_exempt` = the FORMAT itself does not ask for this (a GTFS /
            delivery zip's fields, Table 5; a counts-only package's obod/zones), so the finding is
            recorded and counted but must never be read as "this package is incomplete".
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from .scan import check_name, name_style, read_column_values, scan_folder
from .spec import Spec
from .io import as_lines, split_keywords, to_text

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
URL_RE = re.compile(r"^https?://", re.I)
KEY_RE = re.compile(r"^\s*(.+?)\.([^.>]+?)\s*->\s*(.+?)\.([^.]+?)\s*$")
TODO_RE = re.compile(r"\bTODO\b", re.I)


FORMAT_EXEMPT = "kit_format_exempt"      # the format does not ask for this - recorded, never blocking


class Findings(list):
    def add(self, severity: str, section: str, where: str, code: str, msg: str, detail: str = "", fix: str = "", bucket: str = ""):
        f = {"severity": severity, "section": section, "where": where, "code": code, "msg": msg, "detail": detail, "fix": fix}
        if bucket:
            f["bucket"] = bucket
        self.append(f)

    def counts(self) -> dict:
        c = Counter(f["severity"] for f in self)
        return {"error": c.get("error", 0), "warning": c.get("warning", 0), "info": c.get("info", 0)}

    def buckets(self) -> dict:
        return dict(Counter(f["bucket"] for f in self if f.get("bucket")))


def _empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, list):
        return all(_empty(x) for x in v)
    return to_text(v) == ""


def _is_todo(v: Any) -> bool:
    return any(TODO_RE.search(x) for x in as_lines(v))


def _norm_file(n: str) -> str:
    return re.sub(r"[​-‏‪-‮﻿]", "", n.replace("\\", "/")).strip().lower()


# --------------------------------------------------------------------------- header
def check_header(meta: dict, spec: Spec, include_survey: bool, fx: Findings, n_files: int) -> None:
    items = spec.header_keys(include_survey)
    present = set(meta)
    complex_ds = n_files > 1
    raw_keys = meta.get("_meta", {}).get("raw_keys", {})
    for k, raw in raw_keys.items():
        fx.add("warning", "header", k, "key_case", f"מילת המפתח נכתבה '{raw}' במקום '{k}'", "הנוהל מגדיר מילות מפתח באנגלית ללא שינוי תווים", f"שנה ל-'{k}'")
    for k in meta.get("_meta", {}).get("unknown_keys", []):
        fx.add("info", "header", k, "unknown_key", f"מילת מפתח לא מוכרת בנוהל: '{k}'", "מותר להוסיף פרמטרים, אך יש לוודא שלא מדובר בשגיאת כתיב של מפתח קיים")
    survey_keys = {it["key"] for it in spec.survey}
    for it in items:
        key, st, kind = it["key"], it["status"], it.get("kind")
        if key in survey_keys:
            continue
        val = meta.get(key)
        missing = key not in present or _empty(val)
        required = st == "required" or (st == "required*" and key in ("Files list", "Files", "Key list") and complex_ds) or (st == "required*" and key == "Version")
        if key == "Files":
            if complex_ds and not meta.get("Files"):
                fx.add("error", "header", key, "missing_required", "חסר תיאור הקבצים (Files) – חובה לסט נתונים מורכב")
            continue
        if missing:
            if required:
                if key == "Key list" and complex_ds:
                    fx.add("warning", "header", key, "missing_keys", "רשימת המפתחות (Key list) ריקה", "חובה כאשר קיימים קשרים בין קבצי סט הנתונים; אם אין קשרים – ציין זאת ב-Comments")
                elif key == "Author":
                    fx.add("warning", "header", key, "missing_author", "חסר Author", "חובה כאשר המחבר שונה מהמפרסם")
                else:
                    fx.add("error", "header", key, "missing_required", f"חסר פרמטר חובה: {key} ({it.get('he','')})", it.get("desc", ""), f"הוסף את {key}")
            continue
        if _is_todo(val):
            fx.add("error", "header", key, "todo", f"{key} עדיין מסומן TODO", "", "השלם את הערך")
            continue
        fmt = it.get("format")
        txt = to_text(val if not isinstance(val, list) else (val[0] if val else ""))
        if fmt == "date" and not DATE_RE.match(txt):
            fx.add("error", "header", key, "date_format", f"{key}: '{txt}' אינו בפורמט dd/mm/yyyy", "בקובץ Excel יש לשמור את התאריך כטקסט ולא כתא תאריך", "כתוב למשל 15/05/2024")
        if fmt == "email" and not EMAIL_RE.match(txt):
            fx.add("warning", "header", key, "email_format", f"{key}: '{txt}' אינה כתובת מייל תקינה")
        if fmt == "url" and not URL_RE.match(txt):
            fx.add("warning", "header", key, "url_format", f"{key}: '{txt}' אינה כתובת URL")
        if fmt == "zipname" and not txt.lower().endswith(".zip"):
            fx.add("warning", "header", key, "dataset_zip", f"Dataset file '{txt}' – הנוהל דורש שם קובץ ארכיון עם סיומת .zip", "", f"כתוב '{txt}.zip'")
        if it.get("allowed"):
            allowed = spec.allowed(it["allowed"])
            if txt not in allowed:
                fx.add("warning", "header", key, "not_allowed", f"{key}: '{txt}' אינו אחד מהערכים המותרים", ", ".join(allowed))
        if it.get("allowed_values") and txt not in it["allowed_values"]:
            fx.add("warning", "header", key, "not_allowed", f"{key}: '{txt}' אינו אחד מהערכים המותרים", ", ".join(it["allowed_values"]))
        if it.get("expected") and txt != it["expected"]:
            fx.add("warning", "header", key, "unexpected_value", f"{key} = '{txt}' – לפי נוהל {spec.base['spec']['version']} הערך הצפוי הוא '{it['expected']}'")
        if kind == "block" and isinstance(val, str) and len(val) > 300:
            fx.add("info", "header", key, "block_single_line", f"{key} נכתב כשורה אחת ארוכה – בנוהל זהו בלוק; רצוי לפצל לכמה שורות")
    # keywords
    kws = split_keywords(meta.get("Keywords"))
    if kws:
        dictionary = {k.lower() for k in spec.keywords}
        known = [k for k in kws if k.lower() in dictionary]
        if not known:
            fx.add("info", "header", "Keywords", "keywords_dictionary", "אף מילת מפתח אינה מנספח א' של הנוהל", "רצוי להוסיף מילות מפתח סטנדרטיות באנגלית (למשל: " + ", ".join(spec.keywords[:6]) + " ...)")
        if len(kws) < 3:
            fx.add("info", "header", "Keywords", "keywords_few", f"רק {len(kws)} מילות מפתח – רצוי 3 ומעלה")
    if "Version" in meta and "Comments" in meta and not _empty(meta["Comments"]):
        pass
    if "Metadata version" not in meta:
        fx.add("info", "header", "Metadata version", "metadata_version", "לא צוינה גרסת מטא-דאטה (Metadata version) – לפי הנוהל יש לכתוב 1.1")


# --------------------------------------------------------------------------- survey block
def check_survey(meta: dict, spec: Spec, fx: Findings) -> None:
    for it in spec.survey:
        key = it["key"]
        if it["status"] != "required":
            continue
        if _empty(meta.get(key)):
            fx.add("error", "survey", key, "missing_survey", f"חסר פרמטר חובה לסקר סטטיסטי: {key} ({it.get('he','')})", it.get("desc", "טבלה 2 בנוהל – השלמה לכותרת עבור סקרים"))
        elif _is_todo(meta.get(key)):
            fx.add("error", "survey", key, "todo", f"{key} מסומן TODO")


# --------------------------------------------------------------------------- files vs folder
def _scan_index(scan: Optional[dict]) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    if not scan:
        return idx
    for e in scan["files"]:
        if e["role"] != "data":
            continue
        idx[_norm_file(e["name"])] = e
        if e.get("format") == "ZIP":
            for member, ie in (e.get("inner") or {}).items():
                idx[_norm_file(f"{e['name']}/{member}")] = ie
                idx[_norm_file(member)] = ie
    return idx


def check_files(meta: dict, spec: Spec, scan: Optional[dict], fx: Findings) -> None:
    files = meta.get("Files", [])
    listed = [to_text(x) for x in as_lines(meta.get("Files list"))]
    described = [to_text(f.get("File name")) for f in files]
    nl, nd = [_norm_file(x) for x in listed], [_norm_file(x) for x in described]
    for n in listed:
        if _norm_file(n) not in nd:
            fx.add("error", "files", n, "listed_not_described", f"'{n}' מופיע ב-Files list אך אין לו בלוק תיאור ב-Files")
    for n in described:
        if _norm_file(n) not in nl:
            fx.add("error", "files", n, "described_not_listed", f"'{n}' מתואר ב-Files אך חסר ב-Files list")
    dup = [n for n, c in Counter(nd).items() if c > 1]
    for n in dup:
        fx.add("error", "files", n, "duplicate_file_block", f"'{n}' מתואר יותר מפעם אחת")
    idx = _scan_index(scan)
    if scan:
        folder_names = {_norm_file(e["name"]) for e in scan["files"] if e["role"] == "data"}
        for n in listed:
            nn = _norm_file(n)
            if nn not in idx and Path(nn).name not in {Path(k).name for k in idx}:
                strip = lambda x: re.sub(r"[​-‏‪-‮﻿]", "", x)
                twin = next((k for k in idx if strip(Path(k).name) == strip(Path(nn).name)), None)
                if twin:
                    fx.add("error", "folder", n, "file_name_invisible_chars", f"'{n}' נמצא בתיקייה רק בשם המכיל תווים בלתי נראים (RLM/ZWSP): '{twin}'", "", "שנה את שם הקובץ בתיקייה לשם נקי")
                else:
                    fx.add("error", "folder", n, "file_not_found", f"'{n}' מופיע במטא-דאטה אך לא נמצא בתיקייה", scan["folder"])
        for fn in sorted(folder_names):
            base = Path(fn).name
            if fn not in nl and base not in {Path(x).name for x in nl}:
                e = idx[fn]
                if e.get("format") == "ZIP" and any(_norm_file(f"{fn}/{m}") in nl or _norm_file(m) in nl for m in (e.get("inner") or {})):
                    continue
                fx.add("warning", "folder", fn, "file_not_in_metadata", f"הקובץ '{fn}' נמצא בתיקייה אך אינו מופיע במטא-דאטה", "אם הקובץ אינו חלק מסט הנתונים – הסר אותו מתיקיית ההפצה")
        # related documents exist?
        docs = {_norm_file(d) for d in scan.get("documents", [])} | {_norm_file(m) for m in scan.get("metadata_files", [])}
        for d in as_lines(meta.get("Related documents")):
            if _norm_file(d) not in docs and not URL_RE.match(d) and not (Path(scan["folder"]) / d).exists():
                fx.add("warning", "folder", d, "related_doc_missing", f"המסמך הנלווה '{d}' לא נמצא בתיקייה")
        if scan.get("documents"):
            rel = {_norm_file(d) for d in as_lines(meta.get("Related documents"))}
            for d in scan["documents"]:
                if _norm_file(d) not in rel:
                    fx.add("info", "folder", d, "doc_not_related", f"המסמך '{d}' נמצא בתיקייה אך אינו רשום ב-Related documents")

    # per-file checks
    single = len(files) == 1
    file_items = {it["key"]: it for it in spec.file}
    for fl in files:
        name = to_text(fl.get("File name"))
        where = name or "(file)"
        if _is_todo(fl.get("File description")):
            fx.add("error", "files", where, "todo", "File description מסומן TODO")
        for it in spec.file:
            key, st = it["key"], it["status"]
            if key == "File fields":
                continue
            val = fl.get(key)
            if st == "required" and _empty(val):
                if key == "File description" and single:
                    continue
                fx.add("error", "files", where, "missing_file_key", f"חסר {key} ({it.get('he','')})")
            if key == "File date" and not _empty(val) and not DATE_RE.match(to_text(val)):
                fx.add("warning", "files", where, "date_format", f"File date '{to_text(val)}' אינו dd/mm/yyyy")
            if it.get("allowed") and not _empty(val):
                allowed = spec.allowed(it["allowed"])
                tv = to_text(val)
                if tv not in allowed:
                    contained = [a for a in allowed if a.lower() in tv.lower()]
                    if contained:
                        fx.add("warning", "files", where, "allowed_loose", f"{key} = '{tv}' – רצוי לכתוב בדיוק את הערך המותר '{contained[0]}'", ", ".join(allowed))
                    else:
                        fx.add("error", "files", where, "not_allowed", f"{key} = '{tv}' אינו מהערכים המותרים", ", ".join(allowed))
        fmt = to_text(fl.get("File format")).upper()
        ext = Path(name).suffix.lower()
        fmt_ok = ext.lstrip(".").upper() in fmt or (ext == ".gz" and "CSV" in fmt) or (ext == ".zip" and ("GTFS" in fmt or "SHP" in fmt or "SHAPE" in fmt))             or (ext == ".shp" and "SHAPE" in fmt) or (ext in (".xlsx", ".xls") and "EXCEL" in fmt) or (ext == ".txt" and ("TEXT" in fmt or "CSV" in fmt))
        if fmt and ext and not fmt_ok:
            fx.add("warning", "files", where, "format_ext_mismatch", f"File format '{fmt}' אינו תואם לסיומת '{ext}'")
        e = idx.get(_norm_file(name)) or idx.get(_norm_file(Path(name).name))
        is_gis = (e and e.get("kind") == "gis") or ext in (".shp", ".geojson", ".gpkg") or fmt in ("SHP", "SHAPEFILE", "GEOJSON", "SHP (ZIP)")
        if e and e.get("format") == "ZIP" and e.get("inner"):
            shp_inner = [v for k, v in e["inner"].items() if k.lower().endswith(".shp")]
            if len(shp_inner) == 1 and len(e["inner"]) == 1:
                e, is_gis = shp_inner[0], True
        if is_gis:
            for key in ("Spatial reference system", "Geographic bounding", "Geographic type"):
                if _empty(fl.get(key)):
                    fx.add("error", "files", where, "missing_gis_key", f"שכבה גאוגרפית ללא {key} ({file_items[key]['he']})", "חובה לשכבות גאוגרפיות (טבלה 3)")
            if e and (e.get("crs") or {}).get("mot_value") and not _empty(fl.get("Spatial reference system")):
                want = e["crs"]["mot_value"]
                got = to_text(fl["Spatial reference system"]).upper()
                if (want == "EPSG:2039" and not ("2039" in got or "ITM" in got)) or (want == "WGS_1984" and "WGS" not in got):
                    fx.add("warning", "files", where, "crs_mismatch", f"Spatial reference system = '{got}' אך קובץ ה-.prj מצביע על {want}")
            if e and e.get("geometry_type") and not _empty(fl.get("Geographic type")) and to_text(fl["Geographic type"]).lower() != str(e["geometry_type"]).lower():
                fx.add("warning", "files", where, "geom_mismatch", f"Geographic type = '{fl['Geographic type']}' אך השכבה היא {e['geometry_type']}")
            if e and e.get("dbf_hebrew_suspect"):
                fx.add("warning", "files", where, "dbf_encoding", "ייתכן שקידוד העברית ב-.dbf אינו נקרא כראוי (חסר .cpg?)", "", "הוסף קובץ .cpg עם הקידוד (UTF-8 / 1255)")
        check_fields(fl, e, spec, fx, where, is_gis=bool(is_gis))


# --------------------------------------------------------------------------- fields
def check_fields(fl: dict, e: Optional[dict], spec: Spec, fx: Findings, where: str, is_gis: bool) -> None:
    fields = fl.get("File fields") or []
    fmt = to_text(fl.get("File format")).upper()
    if not fields:
        if "GTFS" in fmt or (e and e.get("gtfs")):
            return
        if e and e.get("format") == "ZIP":
            if not e.get("inner"):
                fx.add("info", "fields", where, "zip_no_fields", "ארכיון ללא תיאור שדות – ודא שהתוכן מתועד (או שהוא פורמט סטנדרטי כמו GTFS)")
            return
        fx.add("error", "fields", where, "no_fields", "אין תיאור שדות (File fields)")
        return
    allowed_types = {t.lower() for t in spec.field_types}
    names = [to_text(f.get("Name")) for f in fields]
    hebrew_names: list[str] = []
    dups = [n for n, c in Counter(n.lower() for n in names).items() if c > 1]
    for d in dups:
        fx.add("error", "fields", f"{where}.{d}", "duplicate_field", f"השדה '{d}' מופיע פעמיים")
    for f in fields:
        n = to_text(f.get("Name"))
        w = f"{where}.{n}"
        if not n:
            fx.add("error", "fields", where, "field_no_name", "שדה ללא שם")
            continue
        t = to_text(f.get("Type"))
        if not t:
            fx.add("error", "fields", w, "field_no_type", f"לשדה '{n}' אין Type")
        elif t.lower() not in allowed_types:
            fx.add("warning", "fields", w, "field_type_unknown", f"Type '{t}' אינו מהסוגים שבנוהל", ", ".join(spec.field_types))
        if _empty(f.get("Description")):
            fx.add("error", "fields", w, "field_no_description", f"לשדה '{n}' אין Description")
        elif _is_todo(f.get("Description")):
            fx.add("error", "fields", w, "todo", f"Description של '{n}' מסומן TODO")
        if t.lower() in ("date", "time", "datetime") and _empty(f.get("Comments")):
            fx.add("info", "fields", w, "time_format_missing", f"'{n}' הוא {t} – רצוי לציין את פורמט הזמן/תאריך ב-Comments (hh:mm:ss / dd/mm/yyyy)")
        vals = f.get("Values") or []
        for v in vals:
            if _is_todo(v.get("label")) or _empty(v.get("label")):
                fx.add("warning", "fields", w, "value_label_missing", f"לערך '{v.get('value')}' של '{n}' אין label", "", "הוסף תיאור לכל ערך מקודד או הסר את רשימת הערכים אם השדה אינו מקודד")
                break
        probs = check_name(n)
        if "hebrew_letters" in probs and spec.profile.get("field_name_style") == "hebrew":
            hebrew_names.append(n)
        elif probs:
            fx.add("warning", "naming", w, "field_name", f"שם השדה '{n}' מפר את כללי השמות: {', '.join(probs)}", "נוהל 5.7 – אותיות לטיניות, ללא רווחים ותווים מיוחדים")
        if re.match(r"^(var|col|field|column)\d+$", n, re.I):
            fx.add("warning", "naming", w, "generic_name", f"שם שדה גנרי: '{n}'", "", "השתמש בשם משמעותי (weight במקום VAR1)")
    if is_gis:
        long_names = [n for n in names if len(inv(n) if "inv" in dir() else n) > 10]
        for n in long_names:
            fx.add("info", "naming", f"{where}.{n}", "dbf_name_length", f"שם השדה '{n}' ארוך מ-10 תווים – בפורמט DBF (shapefile) הוא ייקצץ", "נוהל 5.7 – מגבלת תווים לפי סוג הקובץ")
    if hebrew_names:
        fx.add("warning", "naming", where, "field_names_hebrew_profile", f"{len(hebrew_names)} שמות שדות בעברית (לפי הפורמט הייעודי)", spec.profile.get("field_name_note", ""))
    # style consistency
    styles = name_style(names)
    if len([s for s in styles if s not in ("single_word", "UPPER")]) > 1:
        fx.add("info", "naming", where, "mixed_style", "שמות השדות מערבבים סגנונות (snake_case / camelCase / CamelCase)", str(styles), "אמץ סגנון אחיד לכל סט הנתונים")
    want_style = spec.profile.get("field_name_style")
    if want_style == "snake_case":
        bad = [n for n in names if re.search(r"[A-Z]", n) or " " in n]
        if bad:
            fx.add("warning", "naming", where, "style_profile", f"הפרופיל דורש snake_case באותיות קטנות; שדות חורגים: {', '.join(bad[:8])}{' ...' if len(bad) > 8 else ''}")
    # compare with the actual file
    if e and e.get("fields") is not None and e.get("fields") != [] or (e and e.get("kind") == "table"):
        actual = [c["name"] for c in (e.get("fields") or [])]
        if not actual and e.get("error"):
            fx.add("info", "fields", where, "scan_error", f"לא ניתן לקרוא את הקובץ לצורך השוואה: {e['error']}")
            return
        inv = lambda x: re.sub(r"[​-‏‪-‮﻿]", "", x)
        key = lambda x: inv(x).lower().strip()
        al, ml = {key(a): a for a in actual}, {key(n): n for n in names}
        for a in actual:
            if key(a) not in ml:
                fx.add("error", "fields", f"{where}.{a}", "field_in_file_not_meta", f"השדה '{a}' קיים בקובץ אך אינו מתועד במטא-דאטה")
        for n in names:
            if key(n) not in al:
                close = [a for a in actual if re.sub(r"\W", "", a.lower()) == re.sub(r"\W", "", inv(n).lower())]
                trunc = [a for a in actual if key(a) == key(inv(n))[:10]] if is_gis else []
                if trunc:
                    fx.add("error", "fields", f"{where}.{n}", "dbf_truncated_name",
                           f"השדה '{n}' אינו קיים בקובץ; בשכבה קיים '{trunc[0]}' – פורמט DBF קוצץ שמות ל-10 תווים",
                           "נוהל 5.7: יש להתאים את שם השדה למגבלת התווים של סוג הקובץ",
                           f"תעד את השם כפי שהוא בקובץ ('{trunc[0]}') או שנה את שם השדה בשכבה")
                else:
                    fx.add("error", "fields", f"{where}.{n}", "field_in_meta_not_file", f"השדה '{n}' מתועד במטא-דאטה אך אינו קיים בקובץ", f"אולי התכוונת ל-'{close[0]}'" if close else "")
            elif inv(n) != n:
                fx.add("warning", "fields", f"{where}.{inv(n)}", "field_name_invisible", f"שם השדה '{inv(n)}' במטא-דאטה מכיל תווים בלתי נראים (ZWSP/RLM)", "", "הקלד את השם מחדש בתא")
            elif al[key(n)] != n:
                fx.add("warning", "fields", f"{where}.{n}", "field_case", f"שם השדה במטא-דאטה '{n}' שונה באותיות/רווחים מהקובץ '{al[key(n)]}'")
        # type plausibility
        by = {key(c["name"]): c for c in (e.get("fields") or [])}
        for f in fields:
            n = key(to_text(f.get("Name")))
            c = by.get(n)
            if not c:
                continue
            t = to_text(f.get("Type")).lower().replace("(key)", "")
            inf = (c.get("inferred_type") or "").lower()
            if t in ("integer", "real", "number") and inf == "text":
                fx.add("warning", "fields", f"{where}.{f.get('Name')}", "type_implausible", f"'{f.get('Name')}' מוגדר {f.get('Type')} אך בקובץ יש ערכים לא מספריים (דוגמה: {c.get('text_example') or c.get('example')})")
            elif t in ("date", "time", "datetime") and inf in ("integer", "real"):
                fx.add("warning", "fields", f"{where}.{f.get('Name')}", "type_implausible", f"'{f.get('Name')}' מוגדר {f.get('Type')} אך הערכים בקובץ מספריים (דוגמה: {c.get('example')})")
            elif t == "text" and inf in ("integer", "real") and c.get("candidate_values") and not f.get("Values"):
                fx.add("info", "fields", f"{where}.{f.get('Name')}", "coded_candidate", f"'{f.get('Name')}' נראה כשדה מקודד ({c['n_distinct']} ערכים: {', '.join(map(str, c['candidate_values'][:6]))}) – שקול להוסיף Values")
            elif c.get("candidate_values") and len(c["candidate_values"]) > 1 and not f.get("Values") and t not in ("date", "time", "datetime", "real")                     and (len(c["candidate_values"]) <= 8 or re.search(r"type|code|kind|status|flag|class|categ|mode|dir", n, re.I))                     and not re.search(r"^(n_|num_|count|total|expected|actual|hours|days)|_count$|_hours$|_days$", n, re.I):
                fx.add("info", "fields", f"{where}.{f.get('Name')}", "coded_candidate", f"'{f.get('Name')}' בעל {c['n_distinct']} ערכים בלבד ({', '.join(map(str, c['candidate_values'][:6]))}) – אם זהו קוד, הוסף רשימת Values")
            if "(key)" in to_text(f.get("Type")).lower() and c.get("unique_in_sample") is False and c.get("n_sampled", 0) > 1:
                fx.add("info", "fields", f"{where}.{f.get('Name')}", "key_not_unique", f"'{f.get('Name')}' מוגדר מפתח אך אינו חד-ערכי בקובץ זה (מפתח זר?)")
        if e.get("duplicate_headers"):
            fx.add("error", "fields", where, "duplicate_headers_in_file", f"כותרות כפולות בקובץ: {', '.join(e['duplicate_headers'])}")
        if e.get("encoding") == "cp1255" and not _empty(fl.get("Data encoding")) is False:
            fx.add("info", "files", where, "encoding_note", "הקובץ בקידוד Windows-1255 – רצוי לציין זאת (Data encoding / File comments) או להמיר ל-UTF-8")


# --------------------------------------------------------------------------- deep (opt-in) checks
def check_values_vs_data(meta: dict, scan: Optional[dict], fx: Findings) -> None:
    """Documented Values lists vs the codes actually present in the column."""
    idx = _scan_index(scan)
    for fl in meta.get("Files", []):
        name = to_text(fl.get("File name"))
        e = idx.get(_norm_file(name)) or idx.get(_norm_file(Path(name).name))
        if not e:
            continue
        cols = {c["name"].lower().strip(): c for c in (e.get("fields") or [])}
        for fd in fl.get("File fields", []):
            vals = fd.get("Values") or []
            if not vals:
                continue
            fname = to_text(fd.get("Name"))
            c = cols.get(fname.lower().strip())
            if not c:
                continue
            actual = c.get("distinct_values")
            if actual is None:
                fx.add("info", "fields", f"{name}.{fname}", "values_not_verifiable",
                       f"ל-'{fname}' יש רשימת ערכים במטא-דאטה, אך בקובץ יותר מדי ערכים שונים מכדי לאמת אותה")
                continue
            documented = {to_text(v.get("value")) for v in vals if to_text(v.get("value")) != ""}
            actual_set = {str(a) for a in actual}
            undocumented = sorted(actual_set - documented)
            unused = sorted(documented - actual_set)
            if undocumented:
                fx.add("error", "fields", f"{name}.{fname}", "value_undocumented",
                       f"בקובץ קיימים ערכים שאינם ברשימת הערכים של '{fname}': {', '.join(undocumented[:8])}" + (" ..." if len(undocumented) > 8 else ""),
                       "כל ערך מקודד חייב להופיע ברשימת ה-Values (טבלה 4)", "הוסף את הערכים החסרים או תקן את הנתונים")
            if unused:
                fx.add("info", "fields", f"{name}.{fname}", "value_unused",
                       f"ערכים שמתועדים אך אינם מופיעים בקובץ: {', '.join(unused[:8])}" + (" ..." if len(unused) > 8 else ""),
                       "תקין כשהקוד פשוט לא הופיע החודש; ודא שאינו שריד מגרסה קודמת")


_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _year_span(text: str) -> Optional[tuple[int, int]]:
    years = [int(y) for y in re.findall(r"(?:19|20)\d{2}", text)]
    return (min(years), max(years)) if years else None


def _value_year(v: str) -> Optional[int]:
    m = re.search(r"(?:19|20)\d{2}", v)
    return int(m.group(0)) if m else None


def check_temporal_vs_data(meta: dict, scan: Optional[dict], fx: Findings) -> None:
    """The header's Temporal coverage vs the real date range found in the data."""
    stated = to_text(meta.get("Temporal coverage"))
    span = _year_span(stated) if stated else None
    idx = _scan_index(scan)
    found: list[tuple[str, str, str, str]] = []
    for fl in meta.get("Files", []):
        name = to_text(fl.get("File name"))
        e = idx.get(_norm_file(name)) or idx.get(_norm_file(Path(name).name))
        if not e:
            continue
        for c in (e.get("fields") or []):
            if c.get("inferred_type") in ("Date", "DateTime") and c.get("min_value"):
                found.append((name, c["name"], c["min_value"], c["max_value"]))
    if not found:
        return
    years = [y for _, _, lo, hi in found for y in (_value_year(lo), _value_year(hi)) if y]
    if not years:
        return
    data_span = (min(years), max(years))
    detail = "; ".join(f"{f}.{c}: {lo} – {hi}" for f, c, lo, hi in found[:6])
    if not span:
        fx.add("info", "header", "Temporal coverage", "temporal_no_years",
               f"טווח הזמן שבמטא-דאטה ('{stated}') אינו כולל שנים שניתן להשוות; בנתונים נמצא {data_span[0]}–{data_span[1]}", detail)
        return
    if data_span[0] < span[0] or data_span[1] > span[1]:
        fx.add("warning", "header", "Temporal coverage", "temporal_mismatch",
               f"טווח הזמן שבמטא-דאטה הוא {span[0]}–{span[1]}, אך בנתונים קיימים תאריכים מ-{data_span[0]} עד {data_span[1]}",
               detail, "עדכן את Temporal coverage או בדוק אם נכללו נתונים מחוץ לתקופה")
    else:
        fx.add("info", "header", "Temporal coverage", "temporal_ok",
               f"טווח הזמן תואם לנתונים ({data_span[0]}–{data_span[1]})", detail)


def check_key_joins(meta: dict, folder: Optional[Path], fx: Findings, scan: Optional[dict] = None, limit: int = 200000) -> None:
    """Sample both sides of every declared key and report values that do not join."""
    if folder is None:
        return
    for raw in as_lines(meta.get("Key list")):
        m = KEY_RE.match(to_text(raw).replace("\u200b", ""))
        if not m:
            continue
        fa, ca, fb, cb = (x.strip() for x in m.groups())
        va = read_column_values(folder, fa, ca, limit)
        vb = read_column_values(folder, fb, cb, limit)
        if va is None or vb is None:
            idx = _scan_index(scan)
            missing = []
            for side, (f_, c_) in (("va", (fa, ca)), ("vb", (fb, cb))):
                if (va is None) if side == "va" else (vb is None):
                    e = idx.get(_norm_file(f_)) or idx.get(_norm_file(Path(f_).name))
                    if e is None:
                        missing.append(f"הקובץ '{f_}' לא נסרק")
                    elif not any(x["name"].strip().lower() == c_.strip().lower() for x in (e.get("fields") or [])):
                        missing.append(f"השדה '{c_}' לא קיים בקובץ '{f_}'")
                    else:
                        missing.append(f"לא ניתן לקרוא את '{f_}' (פורמט לא נתמך לקריאת ערכים)")
            fx.add("info", "keys", f"{fa}.{ca} -> {fb}.{cb}", "join_unreadable",
                   "לא ניתן לבדוק את הקישור: " + "; ".join(missing))
            continue
        if not va or not vb:
            continue
        orphans = sorted(vb - va)
        if orphans:
            pct = round(100 * len(orphans) / max(len(vb), 1), 1)
            lookup_like = len(va) < 0.5 * len(vb) and pct > 50
            if lookup_like:
                fx.add("info", "keys", f"{fa}.{ca} -> {fb}.{cb}", "join_lookup_like",
                       f"רק {len(va)} ערכים ב-{fa}.{ca} מול {len(vb)} ב-{fb}.{cb} – נראה כטבלת הערות/לוקאפ ולא כמפתח מלא",
                       "דוגמאות שאינן מקושרות: " + ", ".join(orphans[:6]),
                       "אם זו טבלת הערות (כמו ימים מיוחדים) – הסר אותה מרשימת המפתחות או תאר את הקשר ב-Comments")
                continue
            sev = "error" if pct > 5 else "warning"
            fx.add(sev, "keys", f"{fa}.{ca} -> {fb}.{cb}", "join_orphans",
                   f"{len(orphans)} ערכים ({pct}%) ב-{fb}.{cb} אינם קיימים ב-{fa}.{ca}",
                   "דוגמאות: " + ", ".join(orphans[:6]), "בדוק את הקישור בין הקבצים או את הגדרת המפתח")
        else:
            fx.add("info", "keys", f"{fa}.{ca} -> {fb}.{cb}", "join_ok", f"הקישור תקין ({len(vb)} ערכים נבדקו)")


# --------------------------------------------------------------------------- keys
def check_keys(meta: dict, fx: Findings) -> None:
    files = {_norm_file(to_text(f.get("File name"))): f for f in meta.get("Files", [])}
    base = {Path(k).name: v for k, v in files.items()}
    seen = set()
    for raw in as_lines(meta.get("Key list")):
        k = to_text(raw).replace("​", "")
        m = KEY_RE.match(k)
        if not m:
            fx.add("error", "keys", k, "key_syntax", f"שורת מפתח לא תקינה: '{k}'", "", "פורמט: file.field -> file.field")
            continue
        if k.lower() in seen:
            fx.add("warning", "keys", k, "key_duplicate", f"שורת מפתח כפולה: '{k}'")
        seen.add(k.lower())
        for fname, field in ((m.group(1), m.group(2)), (m.group(3), m.group(4))):
            fl = files.get(_norm_file(fname)) or base.get(fname.strip())
            if not fl:
                fx.add("error", "keys", k, "key_file_missing", f"המפתח מפנה לקובץ '{fname}' שאינו מתואר ב-Files")
                continue
            names = {to_text(f.get("Name")).lower(): to_text(f.get("Name")) for f in fl.get("File fields", [])}
            fs = field.strip()
            if fs.lower() not in names:
                if fs.replace(" ", "").lower() in {n.replace(" ", "") for n in names}:
                    fx.add("error", "keys", k, "key_field_spaces", f"שם השדה במפתח '{fs}' מכיל רווח/תו מיותר")
                elif fl.get("File fields"):
                    fx.add("error", "keys", k, "key_field_missing", f"המפתח מפנה לשדה '{fs}' שאינו מתועד בקובץ '{fname}'")
            if "​" in raw or "‏" in raw:
                fx.add("warning", "keys", k, "invisible_chars", "שורת המפתח מכילה תווים בלתי נראים (zero-width)")


# --------------------------------------------------------------------------- profile
def check_profile(meta: dict, spec: Spec, scan: Optional[dict], fx: Findings) -> None:
    if not spec.profile:
        return
    names = [to_text(f.get("File name")) for f in meta.get("Files", [])]
    present = {}
    from .build import _match_expected, _expected_fields
    for n in names:
        ef = _match_expected(n, spec)
        if ef:
            present.setdefault(ef["name"], []).append(n)
    for ef in spec.expected_files:
        if ef.get("metadata"):
            continue
        if ef.get("related_doc"):
            if not as_lines(meta.get("Related documents")) and not (scan and scan.get("documents")):
                fx.add("warning", "profile", ef["name"], "report_missing", f"הפרופיל דורש {ef['he']} ({ef['name']}) ב-Related documents")
            continue
        if ef["name"] not in present:
            sev = "error" if ef["status"] == "required" else ("warning" if ef["status"] == "required*" else "info")
            fx.add(sev, "profile", ef["name"], "expected_file_missing", f"קובץ {'חובה' if sev == 'error' else 'צפוי'} בפורמט {spec.profile.get('spec', {}).get('name', spec.profile_name)}: {ef['name']} ({ef['he']}) לא נמצא", ef.get("desc", ""))
            continue
        exp = _expected_fields(ef, spec)
        if not exp or ef.get("fields_example_stat_2022"):
            continue
        for fname in present[ef["name"]]:
            fl = next(f for f in meta["Files"] if to_text(f.get("File name")) == fname)
            have = {to_text(f.get("Name")).lower(): f for f in fl.get("File fields", [])}
            for key, xf in exp.items():
                if key not in have:
                    sev = "error" if xf["status"] == "required" else ("warning" if xf["status"] == "required*" else "info")
                    fx.add(sev, "profile", f"{fname}.{xf['Name']}", "expected_field_missing", f"שדה {'חובה' if sev == 'error' else 'צפוי'} '{xf['Name']}' חסר ב-{fname}", xf.get("Description", ""))
                else:
                    t = to_text(have[key].get("Type")).lower()
                    if t and xf.get("Type") and t != xf["Type"].lower():
                        fx.add("info", "profile", f"{fname}.{xf['Name']}", "expected_type_differs", f"'{xf['Name']}' מוגדר {have[key].get('Type')} ואילו הפורמט מגדיר {xf['Type']}")
            extra = [have[k]["Name"] for k in have if k not in exp]
            if extra:
                fx.add("info", "profile", fname, "extra_fields", f"שדות נוספים מעבר לפורמט (מותר, ובלבד שמתועדים): {', '.join(extra[:10])}{' ...' if len(extra) > 10 else ''}")
    # expected keys
    have_keys = {re.sub(r"\s+", "", to_text(k).lower()) for k in as_lines(meta.get("Key list"))}
    for k in spec.expected_keys:
        if "<" in k:
            continue
        if re.sub(r"\s+", "", k.lower()) not in have_keys:
            fx.add("warning", "profile", k, "expected_key_missing", f"מפתח קישור צפוי לפי הפורמט חסר: {k}")
    # header extras required by profile already covered by check_header (merged dictionary)
    pass


# --------------------------------------------------------------------------- naming of files
def check_file_names(meta: dict, fx: Findings) -> None:
    for fl in meta.get("Files", []):
        n = to_text(fl.get("File name"))
        probs = check_name(Path(n).name)
        if probs:
            fx.add("warning", "naming", n, "file_name", f"שם הקובץ '{n}' מפר את כללי השמות: {', '.join(probs)}", "נוהל 5.7 – אותיות לטיניות, ללא רווחים ותווים מיוחדים")
    ds = to_text(meta.get("Dataset file"))
    if ds and check_name(ds):
        fx.add("warning", "naming", ds, "dataset_name", f"שם קובץ סט הנתונים '{ds}' מכיל רווחים/תווים לא לטיניים")


# --------------------------------------------------------------------------- entry
def validate(meta: dict, spec: Spec, folder: Optional[Path] = None, scan: Optional[dict] = None, dataset_kind: Optional[str] = None,
             deep: Optional[set] = None) -> tuple[Findings, dict]:
    """deep: optional set of extra checks — {"values", "temporal", "joins"} (or {"all"})."""
    fx = Findings()
    if folder and scan is None:
        exclude = {"metadata-config.json", "metadata-report.html", "findings.json", "scan.json"}
        scan = scan_folder(folder, exclude=exclude)
    kind = dataset_kind or meta.get("_meta", {}).get("dataset_kind") or spec.dataset_kind
    include_survey = kind == "survey" or bool(spec.profile.get("survey_block"))
    n_files = max(len(meta.get("Files", [])), len(as_lines(meta.get("Files list"))))
    check_header(meta, spec, include_survey, fx, n_files)
    if include_survey:
        check_survey(meta, spec, fx)
    elif kind in (None, "", "unknown"):
        fx.add("info", "survey", "dataset_kind", "kind_unknown", "לא ידוע אם סט הנתונים הוא סקר סטטיסטי – אם כן, נדרש בלוק הסקר (טבלה 2)", "", "ציין dataset_kind ב-metadata-config.json")
    for item in meta.get("_meta", {}).get("auto_from_docs", []):
        fx.add("info", "fields", item.split(":")[0], "desc_from_docs", f"תיאור נלקח אוטומטית מהתיעוד – יש לאמת: {item}", "", "ערוך ב-metadata-config.json אם אינו מדויק")
    check_files(meta, spec, scan, fx)
    check_keys(meta, fx)
    check_file_names(meta, fx)
    check_profile(meta, spec, scan, fx)
    deep = {x.lower() for x in (deep or set())}
    if "all" in deep:
        deep |= {"values", "temporal", "joins"}
    if "values" in deep:
        check_values_vs_data(meta, scan, fx)
    if "temporal" in deep:
        check_temporal_vs_data(meta, scan, fx)
    if "joins" in deep:
        check_key_joins(meta, folder, fx, scan)
    seen, uniq = set(), Findings()
    for f in fx:
        k = (f["severity"], f["code"], f["where"], f["msg"])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    fx = uniq
    order = {"error": 0, "warning": 1, "info": 2}
    fx.sort(key=lambda f: (order[f["severity"]], f["section"], f["where"]))
    summary = {
        "counts": fx.counts(), "buckets": fx.buckets(), "todo": list(meta.get("_meta", {}).get("todo") or []),
        "n_files_described": len(meta.get("Files", [])), "n_fields_described": sum(len(f.get("File fields", [])) for f in meta.get("Files", [])),
        "dataset_kind": kind, "survey_block_checked": include_survey, "profile": spec.profile_name,
        "guideline_version": spec.base["spec"]["version"], "folder": str(folder) if folder else None,
        "metadata_source": meta.get("_meta", {}).get("source_file"),
        "deep_checks": sorted(deep),
    }
    return fx, summary
