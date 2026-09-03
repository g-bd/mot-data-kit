"""One fixture per behaviour added in 0.7.3 (owner rules, 03/09/2026):

* a Parquet table is a data file like a CSV - its schema is the field list, its footer the row
  count, and it is aligned with the metadata (fields in file vs. in metadata, values, joins)
  on disk and inside a zip;
* sizes are real: `Size` / `File size` carry the readable unit (B / KB / MB / GB) AND the exact
  byte count, so a 6 KB lookup table is no longer "0.006" and a 300-byte one no longer "0.0";
* Spatial coverage never carries the "occupied territories" wording, in any language - the
  build refuses to write it (the key goes back to TODO and the refusal is recorded) and the
  validator flags it as an error wherever a metadata file already has it.

Everything here is synthetic (pyarrow writes the Parquet files).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from conftest import make_zip

pa = pytest.importorskip("pyarrow")
import pyarrow.parquet as pq  # noqa: E402

HDR = {"Publisher": "פ", "Contact": "א", "Title": "ט", "Description": ["ד"], "Keywords": ["traffic counts", "bus", "national"],
       "Temporal coverage": "07/2026", "Spatial coverage": "ארצי"}


def _by(fx, code):
    return [f for f in fx if f["code"] == code]


def _parquet_bytes(n: int = 30) -> bytes:
    import datetime as dt
    import io
    t = pa.table({
        "count_id": pa.array(range(1, n + 1), pa.int64()),
        "station_id": pa.array([101 + (i % 10) for i in range(n)], pa.int32()),
        "count_date": pa.array([dt.date(2026, 7, (i % 28) + 1) for i in range(n)], pa.date32()),
        "measured_at": pa.array([dt.datetime(2026, 7, (i % 28) + 1, 8, 30) for i in range(n)], pa.timestamp("ms")),
        "volume": pa.array([i * 10.5 for i in range(n)], pa.float64()),
        "day_type": pa.array(["weekday" if i % 7 < 5 else "weekend" for i in range(n)], pa.string()),
    })
    buf = io.BytesIO()
    pq.write_table(t, buf, compression="snappy")
    return buf.getvalue()


@pytest.fixture()
def pq_folder(tmp_path: Path) -> Path:
    (tmp_path / "stations.csv").write_text(
        "station_id,station_name\n" + "".join(f"{101 + i},S{i}\n" for i in range(10)), encoding="utf-8")
    (tmp_path / "counts.parquet").write_bytes(_parquet_bytes())
    return tmp_path


# =========================================================================== Parquet
def test_parquet_is_scanned_like_a_table(pq_folder, spec):
    from motmeta.scan import scan_folder
    s = scan_folder(pq_folder)
    e = next(x for x in s["files"] if x["name"] == "counts.parquet")
    assert e["role"] == "data" and e["format"] == "Parquet" and e["kind"] == "table"
    assert e["n_rows"] == 30 and e["n_cols"] == 6 and e["row_groups"] >= 1
    assert "SNAPPY" in e["parquet"]["compression"]
    types = {f["name"]: f["inferred_type"] for f in e["fields"]}
    # types come from the Arrow schema, not from a string sample
    assert types == {"count_id": "Integer", "station_id": "Integer", "count_date": "Date",
                     "measured_at": "DateTime", "volume": "Real", "day_type": "Text"}
    dt_col = next(f for f in e["fields"] if f["name"] == "day_type")
    assert dt_col["candidate_values"] and set(dt_col["candidate_values"]) == {"weekday", "weekend"}
    assert next(f for f in e["fields"] if f["name"] == "count_id")["unique_in_sample"]


def test_parquet_is_aligned_with_the_metadata(pq_folder, spec):
    """Fields in the file vs. in the metadata, values, joins - exactly as for a CSV."""
    from motmeta.build import build_metadata
    from motmeta.validate import validate
    files = {"stations.csv": {"File description": "תחנות", "fields": {"station_id": {"Description": "מזהה"}, "station_name": {"Description": "שם"}}},
             "counts.parquet": {"File description": "ספירות", "fields": {
                 "count_id": {"Description": "מזהה"}, "station_id": {"Description": "תחנה"}, "count_date": {"Description": "תאריך"},
                 "measured_at": {"Description": "זמן"}, "volume": {"Description": "נפח"},
                 "day_type": {"Description": "סוג יום", "Values": [{"value": "weekday", "label": "חול"}, {"value": "weekend", "label": "סופ\"ש"}]}}}}
    meta, scan = build_metadata(pq_folder, spec, {"dataset_name": "demo", "dataset_kind": "monitoring", "header": HDR, "files": files,
                                                  "keys": ["stations.csv.station_id -> counts.parquet.station_id"]})
    fl = next(f for f in meta["Files"] if f["File name"] == "counts.parquet")
    assert fl["File format"] == "Parquet"
    assert [x["Name"] for x in fl["File fields"]] == ["count_id", "station_id", "count_date", "measured_at", "volume", "day_type"]
    fx, summary = validate(meta, spec, pq_folder, scan, deep={"values", "joins"})
    assert summary["counts"]["error"] == 0, [f["msg"] for f in fx if f["severity"] == "error"]
    assert _by(fx, "join_ok"), "the join through the Parquet column was checked"
    # a field the metadata documents but the file does not have is still caught
    files["counts.parquet"]["fields"]["ghost"] = {"Description": "אין"}
    meta2, _ = build_metadata(pq_folder, spec, {"dataset_name": "demo", "dataset_kind": "monitoring", "header": HDR, "files": files})
    meta2["Files"][0 if meta2["Files"][0]["File name"] == "counts.parquet" else 1]["File fields"].append({"Name": "ghost", "Type": "Text", "Description": "אין"})
    fx2, _ = validate(meta2, spec, pq_folder, scan)
    assert _by(fx2, "field_in_meta_not_file")


def test_parquet_inside_a_zip_and_its_column_values(tmp_path, spec):
    from motmeta.scan import read_column_counts, scan_folder
    make_zip(tmp_path / "pack.zip", {"counts.parquet": _parquet_bytes(), "readme.txt": b"x"})
    s = scan_folder(tmp_path)
    z = next(x for x in s["files"] if x["name"] == "pack.zip")
    inner = z["inner"]["counts.parquet"]
    assert inner["format"] == "Parquet" and inner["n_rows"] == 30 and inner["size_bytes"] > 0
    assert read_column_counts(tmp_path, "pack.zip/counts.parquet", "day_type") == {"weekday": 22, "weekend": 8}
    (tmp_path / "counts.parquet").write_bytes(_parquet_bytes())
    assert read_column_counts(tmp_path, "counts.parquet", "day_type") == {"weekday": 22, "weekend": 8}
    assert read_column_counts(tmp_path, "counts.parquet", "no_such_column") is None


def test_without_pyarrow_the_file_is_listed_and_the_cause_named(pq_folder, monkeypatch):
    from motmeta.scan import scan_folder
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", None)
    e = next(x for x in scan_folder(pq_folder)["files"] if x["name"] == "counts.parquet")
    assert e["format"] == "Parquet" and e["fields"] == [] and "pyarrow" in e["error"]


# =========================================================================== real sizes
def test_human_size_units():
    from motmeta.scan import human_size, size_text
    assert human_size(0) == "0 B"
    assert human_size(612) == "612 B"
    assert human_size(6 * 1024 + 300) == "6.3 KB"
    assert human_size(16_469_000) == "15.7 MB"
    assert human_size(2 * 1024 ** 3 + 40 * 1024 ** 2) == "2.04 GB"
    assert human_size(1024) == "1 KB"
    assert size_text(1_234_567) == "1.2 MB (1,234,567 bytes)"


def test_metadata_carries_unit_and_exact_bytes(dataset, spec):
    from motmeta.build import build_metadata
    meta, scan = build_metadata(dataset, spec, {"dataset_name": "demo", "header": HDR})
    n = (dataset / "stations.csv").stat().st_size
    st = next(f for f in meta["Files"] if f["File name"] == "stations.csv")
    assert st["File size"] == f"{n} B ({n:,} bytes)"          # a tiny file is no longer 0.0
    assert meta["Size"].endswith(f"({scan['total_size_bytes']:,} bytes)") and " B (" in meta["Size"] or " KB (" in meta["Size"]
    assert scan["total_size_bytes"] == sum(e["size_bytes"] for e in scan["files"])


def test_a_zip_member_and_a_shapefile_report_their_own_size(tmp_path, spec):
    from motmeta.build import build_metadata
    csv = b"a,b\n1,2\n3,4\n" * 200
    make_zip(tmp_path / "pack.zip", {"t.csv": csv})
    meta, scan = build_metadata(tmp_path, spec, {"dataset_name": "demo", "header": HDR})
    member = next(f for f in meta["Files"] if f["File name"] == "pack.zip/t.csv")
    assert member["File size"] == f"{len(csv) / 1024:.1f}".rstrip("0").rstrip(".") + f" KB ({len(csv):,} bytes)"


# =========================================================================== Spatial coverage wording
@pytest.mark.parametrize("bad", ["השטחים הכבושים", "יהודה ושומרון (השטחים הכבושים)", "Occupied Territories",
                                 "the occupied Palestinian territories", "ה​שטחים ה​כבושים"])
def test_the_forbidden_wording_is_an_error_wherever_it_is(dataset, spec, bad):
    from motmeta.build import build_metadata
    from motmeta.validate import validate
    meta, scan = build_metadata(dataset, spec, {"dataset_name": "demo", "header": HDR})
    meta["Spatial coverage"] = bad                       # a hand-made file that already carries it
    meta["Files"][0]["Spatial coverage"] = bad
    fx, _ = validate(meta, spec, dataset, scan)
    hits = _by(fx, "spatial_coverage_wording")
    assert {f["severity"] for f in hits} == {"error"}
    assert {f["section"] for f in hits} == {"header", "files"}
    assert all("אזור יהודה ושומרון" in f["fix"] for f in hits)


@pytest.mark.parametrize("good", ["ארצי", "מטרופולין תל אביב", "אזור יהודה ושומרון", "מחוז הצפון", "Jerusalem district"])
def test_official_designations_pass(dataset, spec, good):
    from motmeta.build import build_metadata
    from motmeta.validate import validate
    meta, scan = build_metadata(dataset, spec, {"dataset_name": "demo", "header": {**HDR, "Spatial coverage": good}})
    fx, _ = validate(meta, spec, dataset, scan)
    assert not _by(fx, "spatial_coverage_wording")
    assert meta["Spatial coverage"] == good


def test_the_build_refuses_to_write_it_even_when_asked(dataset, spec):
    """The config says it; the kit writes TODO, records the refusal, and the report says why."""
    from motmeta.build import build_metadata
    from motmeta.report import render_report
    from motmeta.validate import validate
    files = {"stations.csv": {"File description": "תחנות", "Spatial coverage": "occupied territories"}}
    meta, scan = build_metadata(dataset, spec, {"dataset_name": "demo", "header": {**HDR, "Spatial coverage": "השטחים הכבושים"}, "files": files})
    assert meta["Spatial coverage"] == "TODO"
    assert next(f for f in meta["Files"] if f["File name"] == "stations.csv")["Spatial coverage"] == "TODO"
    assert "Spatial coverage" in meta["_meta"]["todo"] and "stations.csv: Spatial coverage" in meta["_meta"]["todo"]
    refused = meta["_meta"]["refused_wording"]
    assert {r["key"] for r in refused} == {"Spatial coverage", "stations.csv: Spatial coverage"}
    assert {r["term"] for r in refused} == {"כבוש", "occupied"}
    fx, summary = validate(meta, spec, dataset, scan)
    assert not _by(fx, "spatial_coverage_wording")        # nothing forbidden was written
    assert any(f["code"] == "todo" and f["where"] == "Spatial coverage" for f in fx)
    html = render_report(list(fx), summary, meta, scan)
    assert "נוסח שנדחה" in html and "השטחים הכבושים" in html


def test_a_profile_may_add_a_term_but_not_remove_one(spec):
    from motmeta.spec import Spec
    s = Spec(None)
    s.profile = {**s.profile, "spatial_coverage_wording": {"forbidden": ["disputed"]}}
    assert s.forbidden_wording("disputed area") == "disputed"
    assert s.forbidden_wording("השטחים הכבושים") == "כבוש"
    assert s.forbidden_wording(["ארצי", "occupied zone"]) == "occupied"
    assert s.forbidden_wording(None) is None
