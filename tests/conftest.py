"""Synthetic fixtures for the mot-data-kit engine tests (no real data needed)."""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "mot-metadata" / "scripts"
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture()
def dataset(tmp_path: Path) -> Path:
    """A small complex dataset: two linked CSVs, a coded field, a date field, a README with schema lines."""
    (tmp_path / "stations.csv").write_text(
        "station_id,station_name,station_type\n"
        "101,North,1\n102,South,2\n103,East,1\n104,West,2\n105,Mid,1\n"
        "106,A,1\n107,B,2\n108,C,1\n109,D,2\n110,E,1\n", encoding="utf-8")
    rows = ["count_id,station_id,count_date,volume"]
    for i in range(1, 31):
        rows.append(f"{i},{101 + (i % 10)},{(i % 28) + 1:02d}/07/2026,{i * 10}")
    (tmp_path / "counts.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# demo dataset\n\n"
        "station_id | station identifier code\n"
        "volume | hourly traffic volume in vehicles\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def spec():
    from motmeta.spec import Spec
    return Spec(None)


def make_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
