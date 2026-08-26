"""One fixture per behaviour added in 0.7.0 (the on-board viewer project's kit proposals).

Every test here is synthetic - no real package is touched. The point of each is the same:
the kit must stop reporting a package for something the FORMAT does not ask of it, without
starting to judge the data instead.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import make_zip

ROUTES = "route_id,line_id,line,direction,alternative,operator,cluster_id_survey,orig_line,dest_line,length\n" \
         "1_1_0,101,1,1,0,Egged,5,A,B,12.5\n1_2_0,101,1,2,0,Egged,5,B,A,12.7\n"
TIMETABLE = "route_id,trip_id,month_year,day_type,day_period,departure_time\n" \
            "1_1_0,1_1_0_08:00_1_2023,1_2023,1,06:00_09:00,08:00\n" \
            "1_2_0,1_2_0_09:00_1_2023,1_2023,1,09:00_15:00,09:00\n"
TRIPS = "trip_index,trip_id,route_id,trip_date,day_period,trip_start_time,trip_end_time,trip_duration," \
        "trip_vehicle_type,trip_weight_factor,total_boardings,total_boardings_factored,num_stops\n" \
        "1,1_1_0_08:00_1_2023,1_1_0,05/03/2023,06:00_09:00,05/03/2023 08:00:00,08:40:00,00:40:00,רגיל,1.5,30,45.0,12\n" \
        "2,1_2_0_09:00_1_2023,1_2_0,05/03/2023,09:00_15:00,05/03/2023 09:00:00,09:35:00,00:35:00,רגיל,1.5,20,30.0,11\n"
OBAD = "trip_index,station_index,station_id,station_name,day_period,stop_time,door_closing_time,boardings," \
       "alightings,through_pass,trip_weight_factor,boardings_factored,alightings_factored,through_pass_factored\n" \
       "1,1,38831,A,06:00_09:00,08:00:00,08:00:30,10,0,0,1.5,15,0,0\n" \
       "1,2,38832,B,06:00_09:00,08:10:00,08:10:30,5,3,7,1.5,7,4,10\n" \
       "2,1,38831,A,09:00_15:00,09:00:00,09:00:30,8,0,0,1.5,12,0,0\n"
OBOD_HEAD = ("trip_index,quest_id,quest_strt_Time,orig_activity,orig_city,zone_id_orig,first_station_id,"
             "first_access_mode,first_access_line,dest_activity,dest_city,zone_id_dest,last_station_id,"
             "last_egress_mode,last_egress_line,pt_boardings,trip_frequency,payment_type,gender,"
             "employment_status,age,driver_license,vehicles_household,accompanying_pass,quest_weight_factor\n")
OBOD_ROWS = ("1,1,08:05:00,בית,ירושלים,3000001,38831,הליכה,Null,עבודה,ירושלים,3000002,38832,הליכה,Null,1,יומי,רב-קו,ז,שכיר,25-34,כן,1,0,2.0\n"
             "1,2,08:07:00,לימודים,ירושלים,3000002,38831,אוטובוס,14,בית,ירושלים,3000001,38832,הליכה,Null,2,שבועי,מזומן,נ,סטודנט,18-24,לא,0,1,2.0\n"
             "2,3,09:02:00,בית,ירושלים,3000001,38831,הליכה,Null,קניות,ירושלים,-4,38832,הליכה,Null,1,יומי,רב-קו,ז,not_recorded,35-44,כן,2,0,2.0\n")

HEADER_CFG = {
    "Publisher": "משרד התחבורה", "Contact": "א", "Contact Email": "a@b.co.il", "Title": "סקר דמו",
    "Description": ["סקר און-בורד לבדיקה"], "Keywords": ["on-board survey", "bus", "passenger counts"],
    "Temporal coverage": "01/2023 - 03/2023", "Spatial coverage": "ירושלים", "Language": "עברית",
    "Contractor": ["סיגמא 6 — ביצוע"], "Daily periods": ["06:00-09:00", "09:00-15:00"],
    "Survey days": "ימי חול א'-ה'", "Vehicle types": ["רגיל"],
}
SURVEY_CFG = {
    "Statistical population": ["נוסעי האוטובוסים"], "Reference area": "ירושלים",
    "Collection period": "מרץ 2023", "Sample frame": ["1_2023"], "Sampling method": ["מדגם שכבות"],
    "Survey method": ["ראיונות פנים אל פנים"], "Survey completeness": "מלא",
}


def _write_zones_shapefile(folder: Path, key_field: str = "YISHUV_STA", codes=(3000001, 3000002)) -> Path:
    """A tiny polygon layer whose key field is spelled the way real CBS layers spell it."""
    shapefile = pytest.importorskip("shapefile")
    stem = folder / "statistical_areas_2022"
    w = shapefile.Writer(str(stem))
    w.field("OBJECTID", "N", 10, 0)
    w.field("SEMEL_YISH", "N", 10, 0)
    w.field("SHEM_YISHU", "C", 40)
    w.field(key_field, "N", 12, 0)
    w.field("SHAPE_Leng", "F", 19, 11)
    for i, code in enumerate(codes, start=1):
        w.poly([[[0 + i, 0], [0 + i, 1], [1 + i, 1], [1 + i, 0], [0 + i, 0]]])
        w.record(i, 3000, "ירושלים", code, 4.0)
    w.close()
    (folder / "statistical_areas_2022.prj").write_text(
        'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
        'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]', encoding="utf-8")
    zp = folder / "zones.zip"
    make_zip(zp, {p.name: p.read_bytes() for p in folder.glob("statistical_areas_2022.*")})
    for p in list(folder.glob("statistical_areas_2022.*")):
        p.unlink()
    return zp


@pytest.fixture()
def ob(tmp_path: Path) -> Path:
    """A minimal but COMPLETE on-board package in the unified format."""
    (tmp_path / "routes.csv").write_text(ROUTES, encoding="utf-8")
    (tmp_path / "timetable.csv").write_text(TIMETABLE, encoding="utf-8")
    (tmp_path / "trips.csv").write_text(TRIPS, encoding="utf-8")
    (tmp_path / "obad.csv").write_text(OBAD, encoding="utf-8")
    (tmp_path / "obod.csv").write_text(OBOD_HEAD + OBOD_ROWS, encoding="utf-8")
    make_zip(tmp_path / "shapes.zip", {"shapes.txt": b"shape_id,shape_pt_lat,shape_pt_lon\n1,31.7,35.2\n"})
    _write_zones_shapefile(tmp_path)
    return tmp_path


@pytest.fixture()
def ob_spec():
    from motmeta.spec import Spec
    return Spec("onboard")


def _build(folder: Path, spec, **over):
    from motmeta.build import build_metadata
    cfg = {"dataset_name": "demo_ob", "header": dict(HEADER_CFG), "survey": dict(SURVEY_CFG)}
    for k, v in over.items():
        if k in ("header", "survey") and v is not None:
            cfg[k] = {**cfg[k], **v}
        else:
            cfg[k] = v
    return build_metadata(folder, spec, cfg)


def _codes(fx):
    return {f["code"] for f in fx}


def _by(fx, code):
    return [f for f in fx if f["code"] == code]


# --------------------------------------------------------------------------- KP-3
def test_validate_out_dir_is_created(ob, tmp_path):
    """`validate --out-dir DIR` used to exit 2 writing a report into a folder that did not exist."""
    import importlib
    cli = importlib.import_module("mot_metadata")
    from motmeta.spec import Spec
    from motmeta.io import write_json
    meta, _ = _build(ob, Spec("onboard"))
    mp = ob / "demo_ob-metadata.json"
    write_json(meta, mp)
    out = tmp_path / "nope" / "deeper"
    assert not out.exists()
    cli.main(["--no-auto-install", "validate", str(ob), "--profile", "onboard",
              "--metadata", str(mp), "--out-dir", str(out)])
    assert (out / "metadata-report.html").is_file()
    assert (out / "findings.json").is_file()


# --------------------------------------------------------------------------- KP-24
def test_headerless_csv_is_not_promoted_to_a_field_list(tmp_path):
    from motmeta.scan import header_is_data, scan_folder
    (tmp_path / "May24_RoutesStops.csv").write_text(
        "101,1,0,1,38831,31.8907,34.7383,יבנה\n102,1,0,2,38832,31.8912,34.7401,יבנה\n", encoding="utf-8")
    e = {x["name"]: x for x in scan_folder(tmp_path)["files"]}["May24_RoutesStops.csv"]
    assert e["headerless"] is True
    assert e["fields"] == []                       # no bus stop was promoted to a column
    assert e["n_rows"] == 2                        # and the first row is counted as data
    # a real Hebrew header, hyphens and all, is still a header
    assert header_is_data(["מזרוע 1 לזרוע 2-סוג רכב 1", "קוד גלאי", "תאריך"]) is False


def test_headerless_csv_is_reported_not_invented(tmp_path, ob_spec):
    from motmeta.validate import Findings, check_fields
    e = {"kind": "table", "format": "CSV", "headerless": True, "first_row": ["101", "31.89", "יבנה"], "fields": []}
    fx = Findings()
    check_fields({"File name": "stops.csv", "File format": "CSV"}, e, ob_spec, fx, "stops.csv", is_gis=False)
    assert "headerless_csv" in _codes(fx)
    assert "no_fields" not in _codes(fx)


def test_delivery_zip_fields_are_exempt(ob, ob_spec):
    from motmeta.validate import FORMAT_EXEMPT, validate
    meta, scan = _build(ob, ob_spec)
    # the members of shapes.zip are not documented files at all
    assert not any(str(n).startswith("shapes.zip/") for n in meta["Files list"])
    fx, summary = validate(meta, ob_spec, ob, scan)
    exempt = _by(fx, "delivery_file_fields_exempt")
    assert exempt and exempt[0]["bucket"] == FORMAT_EXEMPT
    assert summary["buckets"][FORMAT_EXEMPT] >= 1


# --------------------------------------------------------------------------- KP-25
def test_counts_only_package_does_not_owe_zones(ob, ob_spec):
    from motmeta.validate import FORMAT_EXEMPT, validate
    (ob / "obod.csv").unlink()
    (ob / "zones.zip").unlink()
    meta, scan = _build(ob, ob_spec, survey={"Survey completeness": "חלקי"})
    fx, _ = validate(meta, ob_spec, ob, scan)
    relaxed = _by(fx, "expected_file_not_required")
    assert {f["where"] for f in relaxed} == {"obod.csv", "zones.zip"}
    assert all(f["severity"] == "info" and f["bucket"] == FORMAT_EXEMPT for f in relaxed)
    assert "zones.zip" not in {f["where"] for f in _by(fx, "expected_file_missing")}


def test_declaring_partial_alone_does_not_excuse_zones(ob, ob_spec):
    """FP-22's 'together and only together': a package that ships questionnaires has zone
    codes that resolve to something, and owes the layer that resolves them."""
    from motmeta.validate import validate
    (ob / "zones.zip").unlink()
    meta, scan = _build(ob, ob_spec, survey={"Survey completeness": "חלקי"})
    fx, _ = validate(meta, ob_spec, ob, scan)
    assert "zones.zip" in {f["where"] for f in _by(fx, "expected_file_missing")}
    assert not _by(fx, "expected_file_not_required")


# --------------------------------------------------------------------------- KP-26
def test_missing_report_is_a_warning_never_an_error(ob, ob_spec):
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec)
    fx, _ = validate(meta, ob_spec, ob, scan)
    miss = {f["where"]: f for f in _by(fx, "document_missing")}
    assert miss["report"]["severity"] == "warning"
    assert miss["methodology"]["severity"] == "info"
    assert miss["questionnaire"]["severity"] == "info"
    assert not any(f["severity"] == "error" for f in _by(fx, "document_missing"))


def test_a_methodology_document_answers_the_report_item(ob, ob_spec):
    """The summary report IS the methodology - either shape answers the one checked item."""
    from motmeta.validate import validate
    (ob / "methodology_2023.pdf").write_bytes(b"%PDF-1.4\n")
    meta, scan = _build(ob, ob_spec)
    fx, _ = validate(meta, ob_spec, ob, scan)
    assert "report" not in {f["where"] for f in _by(fx, "document_missing")}
    assert "report" in {f["where"] for f in _by(fx, "document_present")}


def test_a_word_report_answers_it_too(ob, ob_spec):
    from motmeta.validate import validate
    (ob / "demo_ob.docx").write_bytes(b"PK\x03\x04")
    meta, scan = _build(ob, ob_spec)
    fx, _ = validate(meta, ob_spec, ob, scan)
    assert "report" not in {f["where"] for f in _by(fx, "document_missing")}


# --------------------------------------------------------------------------- KP-2
@pytest.mark.parametrize("dirty, dirt", [
    ("age?", "trailing_question_mark"),
    ("age​", "invisible_chars"),
    ("last _bus_stop", "space_around_underscore"),
    ("age ", "nbsp"),
])
def test_field_dirt_is_normalised_and_named(dirty, dirt):
    from motmeta.scan import field_dirt, field_key, norm_field
    assert dirt in field_dirt(dirty)
    assert field_key(dirty) == norm_field(dirty).lower()
    assert " " not in norm_field("last _bus_stop")


def test_a_dirty_header_is_not_reported_missing(ob, ob_spec):
    from motmeta.validate import validate
    body = (OBOD_HEAD.replace("orig_activity", "orig_activity?").replace("first_bus_stop", "first_bus_stop")
            + OBOD_ROWS)
    (ob / "obod.csv").write_text(body, encoding="utf-8")
    meta, scan = _build(ob, ob_spec)
    fx, _ = validate(meta, ob_spec, ob, scan)
    missing = {f["where"] for f in _by(fx, "expected_field_missing")}
    assert "obod.csv.orig_activity" not in missing
    alias = _by(fx, "field_alias")
    assert alias and any("orig_activity" in f["where"] for f in alias)
    assert all(f["severity"] != "error" for f in alias)


# --------------------------------------------------------------------------- KP-5
def test_deep_zones_finds_the_key_and_resolves_the_codes(ob, ob_spec):
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec)
    fx, _ = validate(meta, ob_spec, ob, scan, deep={"zones"})
    resolved = _by(fx, "zones_key_resolved")
    assert resolved and "YISHUV_STA" in resolved[0]["where"]
    assert len(_by(fx, "zone_codes_ok")) == 2          # orig and dest both resolve
    assert not _by(fx, "zone_code_unresolved")


def test_deep_zones_reports_codes_the_layer_does_not_index(ob, ob_spec):
    from motmeta.validate import validate
    (ob / "zones.zip").unlink()
    _write_zones_shapefile(ob, codes=(9999991, 9999992))    # a layer this survey's codes do not index
    meta, scan = _build(ob, ob_spec)
    fx, _ = validate(meta, ob_spec, ob, scan, deep={"zones"})
    bad = _by(fx, "zone_code_unresolved")
    assert bad and bad[0]["severity"] == "error"
    assert "-4" not in bad[0]["detail"]                # the documented out-of-area code is allowed


def test_deep_all_includes_zones(ob, ob_spec):
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec)
    _, summary = validate(meta, ob_spec, ob, scan, deep={"all"})
    assert "zones" in summary["deep_checks"]


# --------------------------------------------------------------------------- KP-13
def test_contractor_row_may_carry_a_role(ob, ob_spec):
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec, header={
        "Contractor": ["דאטהסנס — ביצוע", "סיגמא 6 — המרה לפורמט האחוד", "נתיבי איילון"]})
    fx, _ = validate(meta, ob_spec, ob, scan)
    read = _by(fx, "roles_read")
    assert read and "המרה לפורמט האחוד" in read[0]["msg"]
    assert "נתיבי איילון — ביצוע" in read[0]["msg"]     # a bare name keeps the default role
    assert not _by(fx, "role_unknown")


def test_an_unknown_role_is_recorded_not_refused(ob, ob_spec):
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec, header={"Contractor": ["חברה כלשהי — ייעוץ סטטיסטי"]})
    fx, _ = validate(meta, ob_spec, ob, scan)
    unknown = _by(fx, "role_unknown")
    assert unknown and unknown[0]["severity"] == "info"


# --------------------------------------------------------------------------- KP-21
def test_cbs_field_descriptions_ship_with_the_profile(ob, ob_spec):
    meta, _ = _build(ob, ob_spec)
    zones = next(f for f in meta["Files"] if f["File name"] == "zones.zip")
    desc = {f["Name"]: f["Description"] for f in zones["File fields"]}
    assert "TODO" not in desc.get("YISHUV_STA", "TODO")
    assert "TODO" not in desc.get("OBJECTID", "TODO")
    assert "מזהה פנימי" in desc["OBJECTID"]


def test_a_field_the_cbs_file_does_not_know_stays_todo(ob_spec):
    """The kit ships the publisher's own text; it never invents one."""
    ef = next(e for e in ob_spec.expected_files if e["name"] == "zones.zip")
    shipped = ob_spec.shipped_field_descriptions(ef)
    assert "YISHUV_STA" in shipped
    assert "SOMETHING_ELSE" not in shipped


# --------------------------------------------------------------------------- FP-11 / Table 7
def test_not_recorded_is_an_accepted_category(ob, ob_spec):
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec, files={"obod.csv": {"File description": "שאלונים", "fields": {
        "employment_status": {"Description": "תעסוקה", "Values": [
            {"value": "שכיר", "label": "שכיר"}, {"value": "סטודנט", "label": "סטודנט"}]}}}})
    fx, _ = validate(meta, ob_spec, ob, scan, deep={"values"})
    undoc = _by(fx, "value_undocumented")
    assert not any("not_recorded" in f["msg"] for f in undoc)


def test_day_type_carries_the_table_7_codes(ob_spec):
    tt = next(e for e in ob_spec.expected_files if e["name"] == "timetable.csv")
    dt = next(f for f in tt["fields"] if f["Name"] == "day_type")
    assert {v["value"] for v in dt["Values"]} == {"1", "2", "3", "11", "12", "13", "14", "15"}
    assert "טבלה 7" in dt.get("Comments", "")


# --------------------------------------------------------------------------- KP-4
def test_data_encoding_is_recorded_per_file_and_mixture_reported(ob, ob_spec):
    from motmeta.validate import validate
    # Hebrew station names, so the bytes really are Windows-1255 and not ASCII either way
    (ob / "obad.csv").write_text(OBAD.replace(",A,", ",תחנה א,").replace(",B,", ",תחנה ב,"), encoding="cp1255")
    meta, scan = _build(ob, ob_spec)
    encs = {f["File name"]: f.get("Data encoding") for f in meta["Files"] if f["File name"].endswith(".csv")}
    assert encs["obad.csv"] == "Windows-1255"
    assert encs["routes.csv"] == "UTF-8"
    fx, _ = validate(meta, ob_spec, ob, scan)
    assert "encoding_not_uniform" in _codes(fx)


def test_data_encoding_is_a_key_the_onboard_profile_asks_for(ob_spec):
    item = next(it for it in ob_spec.file if it["key"] == "Data encoding")
    assert item["status"] == "required*"


# --------------------------------------------------------------------------- KP-19
def test_findings_json_carries_the_todo_list_and_the_buckets(ob, ob_spec, tmp_path):
    from motmeta.report import write_findings_json
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec, header={"Publisher": ""})
    fx, summary = validate(meta, ob_spec, ob, scan)
    p = tmp_path / "findings.json"
    write_findings_json(fx, summary, p)
    d = json.loads(p.read_text(encoding="utf-8"))
    assert "Publisher" in d["summary"]["todo"]
    assert "kit_format_exempt" in d["summary"]["buckets"]


# --------------------------------------------------------------------------- KP-20
def test_expected_keys_accept_either_trip_index_or_trip_id(ob, ob_spec):
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec)
    meta["Key list"] = ["trips.csv.trip_index -> obad.csv.trip_index",
                        "trips.csv.trip_index -> obod.csv.trip_index"]
    fx, _ = validate(meta, ob_spec, ob, scan)
    missing = {f["where"] for f in _by(fx, "expected_key_missing")}
    # the trips -> obad / obod joins are satisfied by the trip_index spelling
    assert not any("obad.csv" in m and "trips.csv" in m for m in missing), missing
    assert not any("obod.csv.trip" in m for m in missing), missing


def test_the_profile_states_both_spellings(ob_spec):
    alts = [e for e in ob_spec.expected_keys if isinstance(e, list)]
    assert alts, "the trips -> obad / obod joins are alternatives, not one spelling"
    flat = [a for group in alts for a in group]
    assert any("trip_index" in a for a in flat) and any("trip_id" in a for a in flat)


# --------------------------------------------------------------------------- KP-22
def test_an_open_key_column_gets_no_closed_values_list(ob, ob_spec):
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec)
    obod = next(f for f in meta["Files"] if f["File name"] == "obod.csv")
    zone = next(f for f in obod["File fields"] if f["Name"] == "zone_id_orig")
    assert {v["value"] for v in zone.get("Values", [])} <= {"-1", "-2", "-3", "-4"}
    fx, _ = validate(meta, ob_spec, ob, scan, deep={"values"})
    undoc = {f["where"] for f in _by(fx, "value_undocumented")}
    assert "obod.csv.zone_id_orig" not in undoc
    assert "obod.csv.zone_id_orig" in {f["where"] for f in _by(fx, "values_open_key")}


# --------------------------------------------------------------------------- KP-9
def test_a_field_the_format_forbids_in_the_distribution_file_is_not_missing(ob, ob_spec):
    from motmeta.validate import FORMAT_EXEMPT, validate
    meta, scan = _build(ob, ob_spec)
    fx, _ = validate(meta, ob_spec, ob, scan)
    nd = {f["where"]: f for f in _by(fx, "field_not_distributed")}
    assert "obod.csv.orig_lat_lon" in nd
    assert nd["obod.csv.orig_lat_lon"]["severity"] == "info"
    assert nd["obod.csv.orig_lat_lon"]["bucket"] == FORMAT_EXEMPT
    assert "obod.csv.orig_lat_lon" not in {f["where"] for f in _by(fx, "expected_field_missing")}


# --------------------------------------------------------------------------- KP-7
def test_a_degenerate_bounding_box_is_reported(ob, ob_spec):
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec)
    zones = next(f for f in meta["Files"] if f["File name"] == "zones.zip")
    zones["Geographic bounding"] = "162447.0, 627334.4, 162447.0, 627334.4"
    fx, _ = validate(meta, ob_spec, ob, scan)
    bad = _by(fx, "bbox_degenerate")
    assert bad and bad[0]["severity"] == "warning"


# --------------------------------------------------------------------------- KP-10
def test_survey_completeness_is_proposed_never_written(ob, ob_spec):
    from motmeta.validate import validate
    (ob / "obod.csv").unlink()
    meta, scan = _build(ob, ob_spec, survey={"Survey completeness": ""})
    assert meta.get("Survey completeness") in (None, "", "TODO", ["TODO"])
    fx, _ = validate(meta, ob_spec, ob, scan)
    sug = _by(fx, "completeness_suggested")
    assert sug and "חלקי" in sug[0]["msg"] and sug[0]["severity"] == "info"


# --------------------------------------------------------------------------- KP-16
def test_a_season_name_in_sample_frame_is_a_warning_that_names_the_source(ob, ob_spec):
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec, survey={"Sample frame": ["קיץ 1", "1_2023", "2_4_2024"]})
    fx, _ = validate(meta, ob_spec, ob, scan)
    bad = _by(fx, "row_format")
    assert bad and bad[0]["severity"] == "warning"
    assert "קיץ 1" in bad[0]["msg"] and "1_2023" not in bad[0]["msg"].split("–")[-1]
    assert "timetable.csv.month_year" in bad[0]["fix"]


# --------------------------------------------------------------------------- KP-15
def test_the_common_zones_type_spelling_is_read_not_refused(ob, ob_spec):
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec)
    zones = next(f for f in meta["Files"] if f["File name"] == "zones.zip")
    zones["Zones type"] = "אזורים סטטיסטים"        # the spelling 13 of 18 surveys use
    fx, _ = validate(meta, ob_spec, ob, scan)
    norm = _by(fx, "value_normalised")
    assert norm and norm[0]["severity"] == "info"
    assert not any(f["code"] == "not_allowed" and "Zones type" in f["msg"] for f in fx)


# --------------------------------------------------------------------------- KP-14
def test_init_seeds_every_required_key_name(ob_spec):
    from motmeta.build import default_config
    cfg = default_config("onboard", ob_spec)
    for k in ("Contractor", "Daily periods", "Survey days", "Vehicle types"):
        assert k in cfg["header"], k
    for k in ("Survey completeness", "Sample frame", "Sampling method", "Survey method"):
        assert k in cfg["survey"], k
    assert cfg["survey"]["Sample frame"] == []       # seeded EMPTY - a name, not an answer
    assert cfg["header"]["Survey days"] == ""


# --------------------------------------------------------------------------- KP-23 / KP-8
def test_a_nested_zip_over_the_cap_is_listed_not_opened(tmp_path, monkeypatch):
    from motmeta import scan as scanmod
    monkeypatch.setattr(scanmod, "NESTED_ZIP_MAX_MB", 0)     # everything is "too big"
    inner = tmp_path / "_i.zip"
    make_zip(inner, {"deep.csv": b"a,b\n1,2\n"})
    make_zip(tmp_path / "outer.zip", {"inner.zip": inner.read_bytes()})
    inner.unlink()
    e = {x["name"]: x for x in scanmod.scan_folder(tmp_path)["files"]}["outer.zip"]
    assert e["inner"] == {}
    listed = e["nested_zips"][0]
    assert listed["name"] == "inner.zip" and listed["listed_only"] is True
    assert e["nested_zip_cap_mb"] == 0


def test_type_mismatch_is_counted_with_examples(tmp_path, spec):
    from motmeta.scan import scan_folder
    from motmeta.validate import Findings, check_fields
    rows = ["cluster_id_survey"] + ["אשכול צפון", "אשכול דרום", "אשכול מזרח", "12", "אשכול מערב"]
    (tmp_path / "t.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    e = {x["name"]: x for x in scan_folder(tmp_path)["files"]}["t.csv"]
    col = e["fields"][0]
    assert col["n_non_numeric_sampled"] == 4
    assert len(col["text_examples"]) == 4
    fl = {"File name": "t.csv", "File format": "CSV",
          "File fields": [{"Name": "cluster_id_survey", "Type": "Integer", "Description": "אשכול"}]}
    fx = Findings()
    check_fields(fl, e, spec, fx, "t.csv", is_gis=False)
    imp = _by(fx, "type_implausible")
    assert imp and "אשכול צפון" in imp[0]["detail"]
    assert imp[0]["severity"] == "warning"          # a finding, never a silent coercion
