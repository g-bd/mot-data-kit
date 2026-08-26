"""Spec model: base נוהל dictionary + optional profile (onboard / sensors / custom)."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent.parent                      # skills/mot-metadata
SKILLS_ROOT = SKILL_DIR.parent                      # skills/
BASE_SPEC = SKILL_DIR / "references" / "spec.json"

BUILTIN_PROFILES = {
    "onboard": SKILLS_ROOT / "mot-onboard" / "references" / "profile.json",
    "sensors": SKILLS_ROOT / "mot-sensors" / "references" / "profile.json",
}


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_profile_path(profile: Optional[str]) -> Optional[Path]:
    if not profile or profile in ("none", "generic"):
        return None
    if profile in BUILTIN_PROFILES and BUILTIN_PROFILES[profile].exists():
        return BUILTIN_PROFILES[profile]
    p = Path(profile)
    if p.exists():
        return p
    raise FileNotFoundError(f"profile '{profile}' not found (built-ins: {', '.join(BUILTIN_PROFILES)})")


class Spec:
    """Merged view of the base dictionary and (optionally) one profile."""

    def __init__(self, profile: Optional[str] = None, base_path: Path = BASE_SPEC):
        self.base = _load(base_path)
        self.profile_path = resolve_profile_path(profile)
        self.profile: dict = _load(self.profile_path) if self.profile_path else {}
        self.profile_name = self.profile.get("profile", "generic")
        self.header = self._merge(self.base["header"], self.profile.get("header_extra", []))
        self.survey = self._merge(self.base["survey"], self.profile.get("survey_override", []))
        self.file = self._merge(self.base["file"], self.profile.get("file_extra", []))
        self.field = copy.deepcopy(self.base["field"])
        self._shipped_desc: dict[str, dict[str, str]] = {}

    # ---- merge helpers -------------------------------------------------------
    @staticmethod
    def _merge(base_list: list[dict], extra: list[dict]) -> list[dict]:
        items = copy.deepcopy(base_list)
        index = {it["key"]: it for it in items}
        for ex in extra:
            ex = dict(ex)
            key = ex["key"]
            if key in index:
                index[key].update({k: v for k, v in ex.items() if k not in ("after",)})
                continue
            after = ex.pop("after", None)
            ex.setdefault("kind", "value")
            ex.setdefault("status", "optional")
            ex.setdefault("he", key)
            if after and after in index:
                pos = next(i for i, it in enumerate(items) if it["key"] == after) + 1
                items.insert(pos, ex)
            else:
                items.append(ex)
            index[key] = ex
        return items

    # ---- lookups -------------------------------------------------------------
    def header_keys(self, include_survey: bool) -> list[dict]:
        """Header dictionary in output order. Survey keys are spliced before 'Dataset file'."""
        if not include_survey:
            return list(self.header)
        out: list[dict] = []
        for it in self.header:
            if it["key"] == "Dataset file":
                out.extend(self.survey)
            out.append(it)
        return out

    def key_map(self, include_survey: bool = True) -> dict[str, dict]:
        m = {it["key"]: it for it in self.header}
        if include_survey:
            m.update({it["key"]: it for it in self.survey})
        return m

    def allowed(self, name: str) -> list[str]:
        return list(self.base.get(name, []))

    @property
    def field_types(self) -> list[str]:
        return self.allowed("field_types")

    @property
    def keywords(self) -> list[str]:
        out: list[str] = []
        for vals in self.base.get("keywords", {}).values():
            out.extend(vals)
        return out

    @property
    def dataset_kind(self) -> Optional[str]:
        return self.profile.get("dataset_kind")

    @property
    def unknown_tokens(self) -> dict:
        """Tokens that answer a required text key with "this is not known" (KP-28).

        `values` are accepted as an answer and reported as an `info` so they stay visible;
        `rejected` are the vague placeholders that are NOT an answer and remain errors. A
        profile may add tokens of its own; it cannot take one away, and it cannot turn a
        rejected placeholder into an answer - the base dictionary decides what does not count.
        """
        base = self.base.get("unknown_tokens") or {}
        prof = self.profile.get("unknown_tokens") or {}
        merged: dict[str, Any] = {"note": prof.get("note") or base.get("note", ""),
                                  "source": prof.get("source") or base.get("source", "")}
        for k in ("values", "rejected"):
            seen, out = set(), []
            for v in list(base.get(k) or []) + list(prof.get(k) or []):
                key = str(v).strip().casefold()
                if key and key not in seen:
                    seen.add(key)
                    out.append(str(v))
            merged[k] = out
        return merged

    @property
    def expected_files(self) -> list[dict]:
        return self.profile.get("expected_files", [])

    @property
    def expected_keys(self) -> list:
        """Declared joins. An entry may be a string, or a LIST of alternatives any one of
        which satisfies the expectation (KP-20: the format prints `trip_id` in its Key list
        and names `trip_index` as the key in its tables; the kit may not pick a winner)."""
        return self.profile.get("expected_keys", [])

    @property
    def delivery_patterns(self) -> list[str]:
        """Files the format lets a package carry THROUGH unchanged (GTFS / licensing zips).
        Their fields need not be documented - format Table 5."""
        return list((self.profile.get("delivery_files") or {}).get("patterns", []))

    def is_delivery_file(self, name: str) -> bool:
        base = re.sub(r"[​-‏‪-‮﻿]", "", Path(name).name)
        return any(re.search(p, base, re.I) for p in self.delivery_patterns)

    def shipped_field_descriptions(self, ef: Optional[dict]) -> dict[str, str]:
        """Field descriptions the profile SHIPS for a standard third-party layer
        (`field_descriptions_file`), keyed upper-case. Nobody in this kit authored the
        layer, so nobody in this kit invents its field descriptions - the file carries
        the publisher's own text and its source. Empty when the profile ships none."""
        fname = (ef or {}).get("field_descriptions_file")
        if not fname or not self.profile_path:
            return {}
        if fname not in self._shipped_desc:
            p = self.profile_path.parent / fname
            data = _load(p) if p.exists() else {}
            self._shipped_desc[fname] = {k.upper(): v for k, v in (data.get("fields") or {}).items()}
        return self._shipped_desc[fname]

    def describe(self) -> dict[str, Any]:
        d = {"guideline": self.base["spec"], "profile": self.profile_name}
        if self.profile:
            d["profile_spec"] = self.profile.get("spec")
        return d


def lookup_key(spec_items: list[dict], raw: str) -> Optional[dict]:
    """Case/space-insensitive lookup of a metadata key (e.g. 'version' -> 'Version')."""
    norm = " ".join(str(raw).strip().lower().replace("_", " ").split())
    for it in spec_items:
        if " ".join(it["key"].lower().split()) == norm:
            return it
    return None
