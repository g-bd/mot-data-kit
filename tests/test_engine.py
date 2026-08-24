"""Engine regression tests on synthetic fixtures: scan → build → xlsx round-trip → validate → fix."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from conftest import make_zip


# --------------------------------------------------------------------------- scan
def test_scan_types_and_coded(dataset):
    from motmeta.scan import scan_folder
    s = scan_folder(dataset)
    by = {e["name"]: e for e in s["files"]}
    st = {c["name"]: c for c in by["stations.csv"]["fields"]}
    assert st["station_id"]["inferred_type"] == "Integer"
    assert st["station_id"]["unique_in_sample"] is True
    assert st["station_type"]["candidate_values"] == ["1", "2"]
    ct = {c["name"]: c for c in by["counts.csv"]["fields"]}
    assert ct["count_date"]["inferred_type"] == "Date"
    assert ct["count_date"]["format_hint"] == "dd/mm/yyyy"
    assert ct["station_id"]["unique_in_sample"] is False
    assert by["README.md"]["role"] == "document"


def test_scan_encodings(tmp_path):
    from motmeta.scan import scan_folder
    (tmp_path / "heb1255.csv").write_text("id,שם\n1,שלום\n", encoding="cp1255")
    (tmp_path / "u16.csv").write_bytes("id,name\n1,a\n".encode("utf-16"))
    s = scan_folder(tmp_path)
    by = {e["name"]: e for e in s["files"]}
    assert by["heb1255.csv"]["encoding"] == "cp1255"
    assert by["heb1255.csv"]["fields"][1]["name"] == "שם"
    assert by["u16.csv"]["encoding"].startswith("utf-16")
    assert [c["name"] for c in by["u16.csv"]["fields"]] == ["id", "name"]


def test_scan_nested_zip_and_gtfs(tmp_path):
    from motmeta.scan import scan_folder
    inner = Path(tmp_path / "_i.zip")
    make_zip(inner, {"deep.csv": b"a,b\n1,2\n"})
    make_zip(tmp_path / "outer.zip", {"inner.zip": inner.read_bytes(), "top.csv": b"x,y\n3,4\n"})
    inner.unlink()
    make_zip(tmp_path / "gtfs.zip", {n: b"h\n1\n" for n in ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")})
    s = scan_folder(tmp_path)
    by = {e["name"]: e for e in s["files"]}
    assert "inner.zip/deep.csv" in by["outer.zip"]["inner"]
    assert by["outer.zip"]["inner"]["inner.zip/deep.csv"]["n_rows"] == 1
    assert by["gtfs.zip"]["gtfs"] is True


def test_scan_backup_and_kit_outputs_excluded(dataset):
    from motmeta.scan import scan_folder
    (dataset / "_mot_backup_1").mkdir()
    (dataset / "_mot_backup_1" / "old.csv").write_text("a\n1\n", encoding="utf-8")
    (dataset / "findings.json").write_text("{}", encoding="utf-8")
    s = scan_folder(dataset)
    names = [e["name"] for e in s["files"]]
    assert not any("backup" in n or n == "findings.json" for n in names)


# --------------------------------------------------------------------------- build
def test_build_todo_hints_and_keys(dataset, spec):
    from motmeta.build import build_metadata
    meta, scan = build_metadata(dataset, spec, {"dataset_name": "demo"})
    assert meta["Dataset file"] == "demo.zip"
    assert sorted(meta["Files list"]) == ["counts.csv", "stations.csv"]
    # doc harvest picked the README schema lines
    st = next(f for f in meta["Files"] if f["File name"] == "stations.csv")
    sid = next(f for f in st["File fields"] if f["Name"] == "station_id")
    assert sid["Description"] == "station identifier code"
    assert "(key)" in sid["Type"]
    # key heuristic: unique parent -> child
    assert meta["Key list"] == ["stations.csv.station_id -> counts.csv.station_id"]
    # unanswered required -> TODO
    assert meta["Publisher"] == "TODO"
    assert "Publisher" in meta["_meta"]["todo"]
    # coded field got auto Values
    stype = next(f for f in st["File fields"] if f["Name"] == "station_type")
    assert [v["value"] for v in stype.get("Values", [])] == ["1", "2"]


def test_build_from_seeds_config(dataset, spec, tmp_path):
    from motmeta.build import build_metadata, config_from_metadata
    meta, _ = build_metadata(dataset, spec, {"dataset_name": "demo", "header": {"Publisher": "משרד התחבורה", "Title": "דמו"}})
    cfg = config_from_metadata(meta, spec)
    assert cfg["header"]["Publisher"] == "משרד התחבורה"
    assert "stations.csv" in cfg["files"]
    meta2, _ = build_metadata(dataset, spec, cfg)
    assert meta2["Publisher"] == "משרד התחבורה"


# --------------------------------------------------------------------------- xlsx round trip
def test_xlsx_roundtrip(dataset, spec, tmp_path):
    from motmeta.build import build_metadata
    from motmeta.io import write_xlsx, read_xlsx
    meta, _ = build_metadata(dataset, spec, {"dataset_name": "demo", "header": {
        "Publisher": "פ", "Contact": "א", "Title": "ט", "Description": ["שורה 1", "שורה 2"],
        "Keywords": ["traffic counts", "bus"], "Temporal coverage": "07/2026", "Spatial coverage": "ארצי"}})
    p = tmp_path / "demo-metadata.xlsx"
    write_xlsx(meta, p, spec, include_survey=False)
    back = read_xlsx(p, spec)
    assert back["Publisher"] == "פ"
    assert back["Description"] == ["שורה 1", "שורה 2"]
    assert back["Keywords"] == ["traffic counts", "bus"]
    assert [f["File name"] for f in back["Files"]] == [f["File name"] for f in meta["Files"]]
    f0 = back["Files"][0]["File fields"]
    assert {x["Name"] for x in f0} == {x["Name"] for x in meta["Files"][0]["File fields"]}
    # values survive
    stb = next(f for f in back["Files"] if f["File name"] == "stations.csv")
    stype = next(f for f in stb["File fields"] if f["Name"] == "station_type")
    assert [v["value"] for v in stype.get("Values", [])] == ["1", "2"]
    assert back["_meta"]["raw_keys"] == {}  # our own writer uses canonical casing


# --------------------------------------------------------------------------- validate
def _errs(fx, code=None):
    return [f for f in fx if f["severity"] == "error" and (code is None or f["code"] == code)]


def test_validate_clean_dataset(dataset, spec):
    from motmeta.build import build_metadata
    from motmeta.validate import validate
    hdr = {"Publisher": "פ", "Contact": "א", "Title": "ט", "Description": ["ד"], "Keywords": ["traffic counts", "bus", "national"],
           "Temporal coverage": "07/2026", "Spatial coverage": "ארצי"}
    files = {"stations.csv": {"File description": "תחנות", "fields": {"station_name": {"Description": "שם תחנה"}, "station_type": {"Description": "סוג תחנה", "Values": [{"value": "1", "label": "עירונית"}, {"value": "2", "label": "בין-עירונית"}]}}},
             "counts.csv": {"File description": "ספירות", "fields": {"count_id": {"Description": "מזהה ספירה"}, "count_date": {"Description": "תאריך"}}}}
    meta, scan = build_metadata(dataset, spec, {"dataset_name": "demo", "dataset_kind": "monitoring", "header": hdr, "files": files})
    fx, summary = validate(meta, spec, dataset, scan)
    assert summary["counts"]["error"] == 0, [f["msg"] for f in _errs(fx)]


def test_validate_catches_defects(dataset, spec):
    from motmeta.build import build_metadata
    from motmeta.validate import validate
    meta, scan = build_metadata(dataset, spec, {"dataset_name": "demo", "dataset_kind": "monitoring",
                                                "header": {"Publisher": "פ", "Contact": "א", "Title": "ט", "Description": ["ד"],
                                                           "Keywords": ["bus"], "Temporal coverage": "07/2026", "Spatial coverage": "ארצי"}})
    meta["Created"] = "2026-07-01"                       # wrong date format
    meta["Dataset file"] = "demo"                         # no .zip
    meta["Files list"].append("ghost.csv")                # listed but not described / not on disk
    meta["Files"][0]["File fields"][0]["Type"] = "Whatever"
    meta["Key list"] = ["stations.csv.nope -> counts.csv.station_id", "bad line"]
    fx, summary = validate(meta, spec, dataset, scan)
    codes = {f["code"] for f in fx}
    assert {"date_format", "listed_not_described", "file_not_found", "field_type_unknown", "key_field_missing", "key_syntax"} <= codes
    assert any(f["code"] == "dataset_zip" for f in fx)


def test_validate_survey_block_required_for_survey(dataset, spec):
    from motmeta.build import build_metadata
    from motmeta.validate import validate
    meta, scan = build_metadata(dataset, spec, {"dataset_name": "demo", "dataset_kind": "survey",
                                                "header": {"Publisher": "פ", "Contact": "א", "Title": "ט", "Description": ["ד"],
                                                           "Keywords": ["bus"], "Temporal coverage": "07/2026", "Spatial coverage": "ארצי"}})
    for k in ("Statistical population", "Survey method"):
        meta.pop(k, None)
    fx, _ = validate(meta, spec, dataset, scan, dataset_kind="survey")
    assert any(f["code"] in ("missing_survey", "todo") and f["section"] == "survey" for f in fx)


def test_validate_field_mismatch_and_invisible(dataset, spec):
    from motmeta.build import build_metadata
    from motmeta.validate import validate
    meta, scan = build_metadata(dataset, spec, {"dataset_name": "demo", "dataset_kind": "monitoring"})
    st = next(f for f in meta["Files"] if f["File name"] == "stations.csv")
    st["File fields"][0]["Name"] = "station_id​"     # ZWSP
    st["File fields"].append({"Name": "phantom", "Type": "Text", "Description": "x"})
    fx, _ = validate(meta, spec, dataset, scan)
    codes = {f["code"] for f in fx}
    assert "field_name_invisible" in codes
    assert "field_in_meta_not_file" in codes


def test_deep_values_and_temporal(dataset, spec):
    from motmeta.build import build_metadata
    from motmeta.validate import validate
    files = {"stations.csv": {"File description": "x", "fields": {
        "station_type": {"Description": "t", "Values": [{"value": "1", "label": "a"}, {"value": "9", "label": "never used"}]}}}}
    meta, scan = build_metadata(dataset, spec, {"dataset_name": "demo", "dataset_kind": "monitoring",
                                                "header": {"Temporal coverage": "2019"}, "files": files})
    fx, summary = validate(meta, spec, dataset, scan, deep={"values", "temporal"})
    codes = {f["code"] for f in fx}
    assert "value_undocumented" in codes          # data has code 2, metadata documents 1 and 9
    assert "value_unused" in codes                # 9 never appears
    assert "temporal_mismatch" in codes           # data is 2026, header says 2019
    assert summary["deep_checks"] == ["temporal", "values"]


def test_deep_joins(dataset, spec):
    from motmeta.build import build_metadata
    from motmeta.validate import validate
    (dataset / "orphan.csv").write_text("count_id,station_id\n9,999\n", encoding="utf-8")
    meta, scan = build_metadata(dataset, spec, {"dataset_name": "demo", "dataset_kind": "monitoring"})
    meta["Key list"] = ["stations.csv.station_id -> orphan.csv.station_id",
                        "stations.csv.station_id -> counts.csv.station_id"]
    fx, _ = validate(meta, spec, dataset, scan, deep={"joins"})
    joins = {f["code"] for f in fx if f["section"] == "keys"}
    assert "join_orphans" in joins or "join_lookup_like" in joins
    assert "join_ok" in joins


def test_dbf_truncation_hint(tmp_path, spec):
    from motmeta.validate import check_fields, Findings
    fl = {"File name": "layer.shp", "File format": "SHP",
          "File fields": [{"Name": "YISHUV_STAT_2022", "Type": "Integer", "Description": "d"}]}
    e = {"kind": "gis", "fields": [{"name": "YISHUV_STA", "inferred_type": "Integer"}]}
    fx = Findings()
    check_fields(fl, e, spec, fx, "layer.shp", is_gis=True)
    codes = {f["code"] for f in fx}
    assert "dbf_truncated_name" in codes
    assert "dbf_name_length" in codes


# --------------------------------------------------------------------------- profiles
def test_profiles_merge():
    from motmeta.spec import Spec
    ob = Spec("onboard")
    keys = [it["key"] for it in ob.header_keys(True)]
    assert "Contractor" in keys and "Daily periods" in keys and "Survey completeness" in keys
    assert keys.index("Contractor") < keys.index("Dataset file")
    assert any(e["name"] == "obod.csv" for e in ob.expected_files)
    sn = Spec("sensors")
    assert sn.profile["package_pattern"].startswith("^SensorDataSal")
    assert len(sn.expected_files) == 3


def test_sensor_package_matching(tmp_path):
    from motmeta.spec import Spec
    from motmeta.build import build_metadata
    t1 = "מתאריך,משעה,לתאריך,לשעה,תקופה דק,סוג רכב 1,סוג רכב 2,סוג רכב 3,סוג רכב 4,סוג רכב 5,גרסת פורמט\n01/07/2026,00:00,31/07/2026,23:59,60,דו גלגלי,פרטי,מסחרי,משאית/אוטובוס,משאית כבדה,1.02\n"
    make_zip(tmp_path / "SensorDataSal_260701_260731.zip", {"SensorDataSal_260701_260731_table1.csv": t1.encode("cp1255")})
    spec = Spec("sensors")
    meta, _ = build_metadata(tmp_path, spec, {})
    assert meta["Temporal coverage"].startswith("01/07/2026")
    fl = next(f for f in meta["Files"] if f["File name"].endswith("table1.csv"))
    fld = next(f for f in fl["File fields"] if f["Name"] == "תקופה דק")
    assert fld["Description"].startswith("בסיס הזמן")


# --------------------------------------------------------------------------- fix
def test_fix_plan_and_apply(tmp_path):
    import importlib
    mot_fix = importlib.import_module("mot_fix")
    (tmp_path / "bad name(1).csv").write_text("a,b\nשלום,עולם\n", encoding="cp1255")
    make_zip(tmp_path / "arch.zip", {"in side.csv": b"x\n1\n"})
    rc = mot_fix.main([str(tmp_path)])
    assert rc == 0                                        # dry run
    plan = json.loads((tmp_path / "fix-plan.json").read_text(encoding="utf-8"))
    kinds = {a["kind"] for a in plan["actions"]}
    assert {"rename", "reencode", "zipnames"} <= kinds
    rc = mot_fix.main([str(tmp_path), "--apply"])
    assert rc == 0
    assert (tmp_path / "bad_name1.csv").exists()
    with zipfile.ZipFile(tmp_path / "arch.zip") as z:
        assert z.namelist() == ["in_side.csv"]
    backups = list(tmp_path.glob("_mot_backup_*"))
    assert backups and (backups[0] / "bad name(1).csv").exists()


def test_fix_partial_actions(tmp_path):
    import importlib
    mot_fix = importlib.import_module("mot_fix")
    (tmp_path / "first bad.csv").write_text("a\n1\n", encoding="utf-8")
    (tmp_path / "second bad.csv").write_text("b\n2\n", encoding="utf-8")
    mot_fix.main([str(tmp_path)])
    import json as _json
    plan = _json.loads((tmp_path / "fix-plan.json").read_text(encoding="utf-8"))
    n = next(x["n"] for x in plan["actions"] if x["path"] == "second bad.csv")
    rc = mot_fix.main([str(tmp_path), "--apply", "--actions", str(n)])
    assert rc == 0
    assert (tmp_path / "second_bad.csv").exists()
    assert (tmp_path / "first bad.csv").exists()          # untouched
