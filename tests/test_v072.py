"""One fixture per behaviour added in 0.7.2 - both raised while wiring the kit into the
google-agg-v2 monthly packages (03/09/2026):

* KP-32 - a layer whose .prj is missing or EMPTY still has coordinates; the SRS is inferred from
  them and flagged as inferred, instead of a TODO the pipeline can never answer;
* KP-33 - when the scanner could not read a layer at all (pyshp missing, broken file) the report
  names that cause first, instead of a cryptic `no_fields` + `Spatial reference system = TODO`.

Everything here is synthetic (pyshp writes the shapefiles).
"""
from __future__ import annotations

import io
from pathlib import Path

from conftest import make_zip

WGS84_PRJ = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
             'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')


def _shp_zip(path: Path, x: float, y: float, prj: str | None) -> Path:
    import shapefile
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYLINE) as w:
        w.field("ID", "N", 10, 0)
        w.field("NAME", "C", 40)
        for i in range(3):
            w.line([[(x + i * 0.01, y), (x + i * 0.01 + 0.005, y + 0.005)]])
            w.record(i + 1, f"link {i + 1}")
    members = {"links.shp": shp.getvalue(), "links.shx": shx.getvalue(), "links.dbf": dbf.getvalue()}
    if prj is not None:
        members["links.prj"] = prj.encode("ascii")
    make_zip(path, members)
    return path


def _by(fx, code):
    return [f for f in fx if f["code"] == code]


def _layer(tmp_path: Path, name: str) -> dict:
    from motmeta.scan import scan_folder
    return next(x for x in scan_folder(tmp_path)["files"] if x["name"] == name)["inner"]["links.shp"]


# =========================================================================== KP-32
def test_empty_prj_infers_wgs84_from_degrees(tmp_path):
    _shp_zip(tmp_path / "bsh.zip", 34.40, 30.85, prj="")          # the zero-byte .prj case
    crs = _layer(tmp_path, "bsh.zip")["crs"]
    assert crs["mot_value"] == "WGS_1984"
    assert crs["missing_prj"] and crs["inferred_from_bbox"]


def test_missing_prj_infers_itm_from_metres(tmp_path):
    _shp_zip(tmp_path / "itm.zip", 180000, 650000, prj=None)
    crs = _layer(tmp_path, "itm.zip")["crs"]
    assert crs["mot_value"] == "EPSG:2039" and crs["inferred_from_bbox"]


def test_real_prj_still_wins_and_is_not_marked_inferred(tmp_path):
    _shp_zip(tmp_path / "tlv.zip", 34.6, 31.7, prj=WGS84_PRJ)
    crs = _layer(tmp_path, "tlv.zip")["crs"]
    assert crs["mot_value"] == "WGS_1984" and not crs.get("inferred_from_bbox")


def test_coordinates_outside_israel_stay_unknown(tmp_path):
    _shp_zip(tmp_path / "odd.zip", 1.0, 1.0, prj="")
    crs = _layer(tmp_path, "odd.zip")["crs"]
    assert crs["mot_value"] is None and crs["missing_prj"] and not crs["inferred_from_bbox"]


def test_inferred_srs_fills_the_metadata_and_reports_an_info(tmp_path, spec):
    from motmeta.build import build_metadata
    from motmeta.validate import validate
    _shp_zip(tmp_path / "bsh.zip", 34.40, 30.85, prj="")
    meta, scan = build_metadata(tmp_path, spec, {"header": {"Title": "t"}})
    layer = next(f for f in meta["Files"] if f["File name"] == "bsh.zip")
    assert layer["Spatial reference system"] == "WGS_1984"           # no TODO the pipeline cannot answer
    assert "bsh.zip: Spatial reference system" not in meta["_meta"]["todo"]
    fx, _ = validate(meta, spec, tmp_path, scan)
    inferred = _by(fx, "crs_inferred")
    assert inferred and inferred[0]["severity"] == "info"
    assert not _by(fx, "not_allowed")


# =========================================================================== KP-33
def test_unreadable_layer_names_the_cause_first(tmp_path, spec, monkeypatch):
    """Simulate `pyshp` missing: the scanner records the error, the report says so up front."""
    import builtins
    from motmeta.build import build_metadata
    from motmeta.validate import validate
    _shp_zip(tmp_path / "layer.zip", 34.6, 31.7, prj="")
    real_import = builtins.__import__

    def no_pyshp(name, *a, **k):
        if name == "shapefile":
            raise ImportError("No module named 'shapefile'")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_pyshp)
    try:
        meta, scan = build_metadata(tmp_path, spec, {"header": {"Title": "t"}})
    finally:
        monkeypatch.setattr(builtins, "__import__", real_import)
    fx, _ = validate(meta, spec, tmp_path, scan)
    unread = _by(fx, "layer_unread")
    assert unread and "pyshp" in unread[0]["msg"] and unread[0]["severity"] == "error"
