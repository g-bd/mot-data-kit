"""One fixture per behaviour added in 0.7.1.

Four rules, all raised while driving the kit over real on-board deliveries:

* KP-27 - the codes the FORMAT defines for a trip end that is not a zone are an answer, not a
  join orphan;
* KP-28 - a value documented as unknown is an answer, not a TODO; a vague placeholder still is
  not an answer;
* KP-30 - a DBF that declares no encoding is read under a named assumption rather than not read
  at all;
* KP-31 - a lookup table is the parent of its join whichever side of the arrow it is written on.

Everything here is synthetic. As always: the kit must stop reporting a package for something the
format does not ask of it, without starting to judge the data instead.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_zip
from test_phase9 import (OBAD, OBOD_HEAD, OBOD_ROWS, ROUTES, TIMETABLE, TRIPS, _build, _by, _codes,
                         _write_zones_shapefile, ob, ob_spec)      # noqa: F401  (fixtures)


# =========================================================================== KP-28
def test_a_documented_unknown_is_an_answer_not_a_todo(ob, ob_spec):
    """`Contractor = לא ידוע — לא תועד במקורות` answers the key and stays visible as an info."""
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec, header={"Contractor": ["לא ידוע — לא תועד במקורות"]})
    fx, _ = validate(meta, ob_spec, ob, scan)
    mine = [f for f in fx if f["where"] == "Contractor"]
    assert [f["code"] for f in mine] == ["value_unknown_documented"]
    assert mine[0]["severity"] == "info"
    # and it is NOT read as a company plus a role, which is what the em dash would otherwise mean
    assert not _by(fx, "role_unknown")


def test_the_bare_hebrew_token_and_the_english_one_both_answer(ob, ob_spec):
    from motmeta.validate import validate
    for token in ("לא ידוע", "unknown — not documented in the sources", "unknown - not documented in the sources"):
        meta, scan = _build(ob, ob_spec, header={"Contractor": [token]})
        fx, _ = validate(meta, ob_spec, ob, scan)
        codes = {f["code"] for f in fx if f["where"] == "Contractor"}
        assert codes == {"value_unknown_documented"}, token


def test_a_question_mark_is_still_an_error(ob, ob_spec):
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec, header={"Contractor": ["?"]})
    fx, _ = validate(meta, ob_spec, ob, scan)
    bad = [f for f in fx if f["where"] == "Contractor"]
    assert [f["code"] for f in bad] == ["value_placeholder"]
    assert bad[0]["severity"] == "error"


@pytest.mark.parametrize("junk", ["?", "N/A", "-", "TBD", "..."])
def test_every_listed_placeholder_stays_an_error(ob, ob_spec, junk):
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec, header={"Contractor": [junk]})
    fx, _ = validate(meta, ob_spec, ob, scan)
    assert "value_placeholder" in {f["code"] for f in fx if f["where"] == "Contractor"}


def test_todo_and_an_empty_cell_are_untouched(ob, ob_spec):
    """The token relaxes nothing else: TODO is still TODO and a missing key is still missing."""
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec)
    meta["Contractor"] = ["TODO"]
    fx, _ = validate(meta, ob_spec, ob, scan)
    assert "todo" in {f["code"] for f in fx if f["where"] == "Contractor"}
    meta["Contractor"] = []
    fx, _ = validate(meta, ob_spec, ob, scan)
    assert "missing_required" in {f["code"] for f in fx if f["where"] == "Contractor"}


def test_the_generic_dictionary_accepts_it_on_a_header_key(dataset, spec):
    """Author / Contact are the נוהל's own keys - the rule is in the base dictionary, not only
    in the on-board profile."""
    from motmeta.build import build_metadata
    from motmeta.validate import validate
    meta, scan = build_metadata(dataset, spec, {"header": {
        "Publisher": "משרד התחבורה", "Contact": "לא ידוע", "Title": "דמו",
        "Description": ["בדיקה"], "Author": "לא ידוע — לא תועד במקורות"}})
    fx, _ = validate(meta, spec, dataset, scan)
    said = {f["where"] for f in _by(fx, "value_unknown_documented")}
    assert {"Contact", "Author"} <= said
    assert not [f for f in fx if f["where"] in ("Contact", "Author") and f["severity"] == "error"]


def test_a_key_with_a_shape_or_a_vocabulary_is_not_answered_by_unknown(ob, ob_spec):
    """`Created` wants a date and `Survey completeness` wants one of two words; "unknown" is not
    an answer to either, and pretending otherwise would make the existing checks lie."""
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec, survey={"Survey completeness": "לא ידוע"})
    meta["Created"] = "לא ידוע"
    fx, _ = validate(meta, ob_spec, ob, scan)
    assert "value_unknown_documented" not in {f["code"] for f in fx if f["where"] == "Created"}
    assert "date_format" in {f["code"] for f in fx if f["where"] == "Created"}
    assert "value_unknown_documented" not in {f["code"] for f in fx if f["where"] == "Survey completeness"}


def test_the_report_prints_it_as_an_answer_not_as_a_todo(ob, ob_spec):
    from motmeta.report import render_report
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec, header={"Contractor": ["לא ידוע — לא תועד במקורות"]})
    fx, summary = validate(meta, ob_spec, ob, scan)
    html = render_report(list(fx), summary, meta, scan, ob_spec.describe())
    assert "ערכים שתועדו כלא ידועים" in html
    assert "לא ידוע — לא תועד במקורות" in html


def test_a_profile_may_add_a_token_but_not_remove_one():
    from motmeta.spec import Spec
    base, onboard = Spec(None).unknown_tokens, Spec("onboard").unknown_tokens
    assert set(base["values"]) <= set(onboard["values"])
    assert set(base["rejected"]) <= set(onboard["rejected"])


# =========================================================================== KP-27
def test_the_formats_own_zone_codes_are_not_orphans(ob, ob_spec):
    """-1..-4 describe a trip end that is not a zone. They index nothing on purpose."""
    from motmeta.validate import validate
    rows = OBOD_ROWS + "".join(
        OBOD_ROWS.splitlines()[0].replace("3000001", str(code), 1) + "\n" for code in (-1, -2, -3))
    (ob / "obod.csv").write_text(OBOD_HEAD + rows, encoding="utf-8")
    meta, scan = _build(ob, ob_spec)
    fx, _ = validate(meta, ob_spec, ob, scan, deep={"zones"})
    assert not _by(fx, "zone_code_unresolved")
    special = _by(fx, "zone_special_codes")
    assert special and all(f["severity"] == "info" for f in special)
    orig = next(f for f in special if "zone_id_orig" in f["where"])
    assert "-1 (חוץ לארץ): 1" in orig["detail"]
    assert "-2 (יישובים פלסטיניים): 1" in orig["detail"]
    assert "-3 (" in orig["detail"]


def test_the_codes_come_from_the_profile_not_from_the_document(ob, ob_spec):
    """A package that documented no `Values` for the zone columns is judged the same way -
    the codes are the format's, and the profile is where the kit reads them."""
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec)
    for fl in meta["Files"]:
        if fl["File name"] == "obod.csv":
            for fd in fl.get("File fields", []):
                if fd["Name"] in ("zone_id_orig", "zone_id_dest"):
                    fd.pop("Values", None)
    fx, _ = validate(meta, ob_spec, ob, scan, deep={"zones"})
    assert not _by(fx, "zone_code_unresolved")
    assert _by(fx, "zone_special_codes")


def test_a_code_the_layer_really_does_not_index_is_still_counted(ob, ob_spec):
    """The exemption is for the four codes the format names, not for anything negative-looking."""
    from motmeta.validate import validate
    (ob / "obod.csv").write_text(OBOD_HEAD + OBOD_ROWS.replace("3000002", "8888888"), encoding="utf-8")
    meta, scan = _build(ob, ob_spec)
    fx, _ = validate(meta, ob_spec, ob, scan, deep={"zones"})
    bad = _by(fx, "zone_code_unresolved")
    assert bad and any("8888888" in f["detail"] for f in bad)
    assert not any("-4" in f["detail"] for f in bad)


def test_the_special_codes_are_not_counted_in_the_percentage(ob, ob_spec):
    """The denominator is the codes that were actually asked of the layer."""
    from motmeta.validate import validate
    (ob / "zones.zip").unlink()
    _write_zones_shapefile(ob, codes=(9999991, 9999992))
    meta, scan = _build(ob, ob_spec)
    fx, _ = validate(meta, ob_spec, ob, scan, deep={"zones"})
    dest = next(f for f in _by(fx, "zone_code_unresolved") if "zone_id_dest" in f["where"])
    assert "מתוך 2 " in dest["msg"]          # 3000001, 3000002 - the -4 row is not in the count


# =========================================================================== KP-31
def _zone_key_list(meta: dict, col: str = "zone_id_orig") -> dict:
    meta = dict(meta)
    meta["Key list"] = [f"obod.csv.{col} -> zones.zip.YISHUV_STA"]
    return meta


def test_a_join_onto_a_lookup_layer_is_judged_in_the_direction_it_is_used(ob, ob_spec):
    """The layer is national; the survey uses a slice of it. Every zone nobody travelled to is
    not a finding, and every code that resolves means the join is clean."""
    from motmeta.validate import validate
    (ob / "zones.zip").unlink()
    _write_zones_shapefile(ob, codes=(3000001, 3000002, 3000003, 3000004, 3000005, 3000006))
    meta, scan = _build(ob, ob_spec)
    fx, _ = validate(_zone_key_list(meta), ob_spec, ob, scan, deep={"joins"})
    assert not _by(fx, "join_orphans")
    assert not _by(fx, "join_lookup_like")
    ok = _by(fx, "join_ok")
    assert ok and ok[0]["where"] == "obod.csv.zone_id_orig -> zones.zip.YISHUV_STA"


def test_a_code_absent_from_the_lookup_is_still_an_orphan(ob, ob_spec):
    from motmeta.validate import validate
    (ob / "obod.csv").write_text(OBOD_HEAD + OBOD_ROWS.replace("3000002", "8888888"), encoding="utf-8")
    meta, scan = _build(ob, ob_spec)
    fx, _ = validate(_zone_key_list(meta), ob_spec, ob, scan, deep={"joins"})
    bad = _by(fx, "join_orphans")
    assert bad and "8888888" in bad[0]["detail"]
    assert bad[0]["where"] == "obod.csv.zone_id_orig -> zones.zip.YISHUV_STA"


def test_the_special_codes_are_left_out_of_the_join_too(ob, ob_spec):
    """`zone_id_dest` carries a -4; the join is clean, not 33 % broken."""
    from motmeta.validate import validate
    meta, scan = _build(ob, ob_spec)
    fx, _ = validate(_zone_key_list(meta, "zone_id_dest"), ob_spec, ob, scan, deep={"joins"})
    assert not _by(fx, "join_orphans")
    assert _by(fx, "zone_special_codes")


def test_an_ordinary_relation_keeps_its_declared_direction(ob, ob_spec):
    """Nothing about a normal parent -> child key changes: an orphan child row is still one."""
    from motmeta.validate import validate
    (ob / "obad.csv").write_text(OBAD + "9,1,38831,A,06:00_09:00,08:00:00,08:00:30,1,0,0,1.5,1,0,0\n",
                                 encoding="utf-8")
    meta, scan = _build(ob, ob_spec)
    meta["Key list"] = ["trips.csv.trip_index -> obad.csv.trip_index"]
    fx, _ = validate(meta, ob_spec, ob, scan, deep={"joins"})
    bad = _by(fx, "join_orphans")
    assert bad and "9" in bad[0]["detail"]


# =========================================================================== KP-30
def _cp1255_layer(folder: Path, with_cpg: bool = False, ldid: int = 0x57) -> Path:
    """A zipped shapefile whose attribute table is Windows-1255 and says so nowhere."""
    shapefile = pytest.importorskip("shapefile")
    stem = folder / "Lamas_Census_Tracts_2011"
    w = shapefile.Writer(str(stem), encoding="cp1255")
    w.field("YISHUV_STA", "N", 12, 0)
    w.field("SHEM_YISHU", "C", 40)
    for i, (code, name) in enumerate([(3000001, "אור עקיבא"), (3000002, "מאיר שפיה")], start=1):
        w.poly([[[i, 0], [i, 1], [i + 1, 1], [i + 1, 0], [i, 0]]])
        w.record(code, name)
    w.close()
    dbf = stem.with_suffix(".dbf")
    raw = bytearray(dbf.read_bytes())
    raw[29] = ldid                       # "ANSI" - the writing machine's code page, i.e. nothing
    dbf.write_bytes(bytes(raw))
    (folder / "Lamas_Census_Tracts_2011.prj").write_text(
        'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
        'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]', encoding="utf-8")
    members = {p.name: p.read_bytes() for p in folder.glob("Lamas_Census_Tracts_2011.*")}
    if with_cpg:
        members["Lamas_Census_Tracts_2011.cpg"] = b"1255"
    zp = folder / "zones.zip"
    make_zip(zp, members)
    for p in list(folder.glob("Lamas_Census_Tracts_2011.*")):
        p.unlink()
    return zp


def test_a_cp1255_dbf_without_a_cpg_is_read_not_dropped(tmp_path):
    """pyshp decodes a DBF as strict UTF-8. That layer used to arrive with NO fields at all,
    which no answer in metadata-config.json could ever have filled in."""
    from motmeta.scan import scan_folder
    _cp1255_layer(tmp_path)
    e = {x["name"]: x for x in scan_folder(tmp_path)["files"]}["zones.zip"]
    layer = next(v for k, v in e["inner"].items() if k.lower().endswith(".shp"))
    assert layer.get("error") is None
    assert [c["name"] for c in layer["fields"]] == ["YISHUV_STA", "SHEM_YISHU"]
    assert layer["dbf_encoding_assumed"] == "cp1255"
    assert layer["dbf_ldid"] == 0x57
    assert "אור עקיבא" in [c.get("example") for c in layer["fields"]]


def test_the_assumption_is_reported_never_silent(tmp_path, ob_spec):
    from motmeta.validate import validate
    for name, body in (("routes.csv", ROUTES), ("timetable.csv", TIMETABLE), ("trips.csv", TRIPS),
                       ("obad.csv", OBAD), ("obod.csv", OBOD_HEAD + OBOD_ROWS)):
        (tmp_path / name).write_text(body, encoding="utf-8")
    _cp1255_layer(tmp_path)
    meta, scan = _build(tmp_path, ob_spec)
    fx, _ = validate(meta, ob_spec, tmp_path, scan)
    said = _by(fx, "dbf_encoding_assumed")
    assert said and said[0]["severity"] == "info" and "cp1255" in said[0]["msg"]
    assert "zones.zip" not in {f["where"] for f in _by(fx, "no_fields")}


def test_a_cpg_is_believed_and_nothing_is_assumed(tmp_path):
    from motmeta.scan import scan_folder
    _cp1255_layer(tmp_path, with_cpg=True)
    e = {x["name"]: x for x in scan_folder(tmp_path)["files"]}["zones.zip"]
    layer = next(v for k, v in e["inner"].items() if k.lower().endswith(".shp"))
    assert "dbf_encoding_assumed" not in layer
    assert layer["dbf_encoding_file"] == "1255"
    assert "אור עקיבא" in [c.get("example") for c in layer["fields"]]


def test_a_utf8_layer_is_still_read_as_utf8(ob):
    """The fallback is a fallback: a modern layer is not quietly re-read as Windows Hebrew."""
    from motmeta.scan import scan_folder
    e = {x["name"]: x for x in scan_folder(ob)["files"]}["zones.zip"]
    layer = next(v for k, v in e["inner"].items() if k.lower().endswith(".shp"))
    assert "dbf_encoding_assumed" not in layer
    assert layer["dbf_encoding_used"] == "utf-8"


def test_the_layers_values_can_be_read_for_a_join(tmp_path):
    """The same encoding walk backs `read_column_values`, or the key check would still be blind."""
    from motmeta.scan import read_column_values
    _cp1255_layer(tmp_path)
    assert read_column_values(tmp_path, "zones.zip", "YISHUV_STA") == {"3000001", "3000002"}
    assert read_column_values(tmp_path, "zones.zip", "SHEM_YISHU") == {"אור עקיבא", "מאיר שפיה"}


def test_the_code_page_byte_is_used_when_it_names_one(tmp_path):
    """LDID 0xC9 names cp1251 outright - the fallback must not overrule what the file says."""
    from motmeta.scan import dbf_codec_candidates
    head = bytes(29) + bytes([0xC9]) + bytes(2)
    assert [c for c, _ in dbf_codec_candidates(head)][:3] == ["utf-8", "cp1251", "cp1255"]
    assert dbf_codec_candidates(head, "UTF-8")[0][1] == "cpg"
    assert [c for c, _ in dbf_codec_candidates(bytes(32))][:2] == ["utf-8", "cp1255"]
