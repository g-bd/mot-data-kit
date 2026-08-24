---
name: mot-onboard
description: Create or validate the metadata of an on-board (OB) bus passenger survey dataset according to the Israel MoT "פורמט אחוד לנתוני סקרי און-בורד" v1.0 (13/11/2024) on top of the data-distribution נוהל v1.3. Knows the mandatory file set (routes.csv, shapes.zip/GTFS, timetable.csv, plan.csv, trips.csv, obad.csv, obod.csv, zones.zip, survey report PDF, metadata xlsx), every expected field with type/status/description, the trip_id / route_id conventions, the key-list links, the extra header keys (Contractor, Daily periods, Survey days, Vehicle types, Survey completeness) and the survey block (Statistical population, Sample frame, Sampling method, Survey method...). Use when the user mentions "on-board", "און-בורד", "OB survey", "סקר נוסעים באוטובוסים", "obad/obod/trips", "פעימה", "סקר עולים יורדים", or wants to prepare/validate an OB survey for distribution. Generic datasets → mot-metadata; sensors → mot-sensors.
---

# mot-onboard — on-board survey metadata (format v1.0)

This skill is the **onboard profile** of `mot-metadata`: same engine, same commands, with
`--profile onboard`. Read `../mot-metadata/SKILL.md` for the workflow; this file adds what is
specific to on-board surveys. Reference text: `references/onboard-format-v1.0.md`;
machine-readable expectations: `references/profile.json`.

```
python ../mot-metadata/scripts/mot_metadata.py init     <folder> --profile onboard
python ../mot-metadata/scripts/mot_metadata.py build    <folder> --profile onboard --name <survey>_<year>
python ../mot-metadata/scripts/mot_metadata.py validate <folder> --profile onboard [--metadata F]
python ../mot-metadata/scripts/mot_metadata.py build    <folder> --profile onboard --from <old metadata.xlsx>
```

## What the profile adds automatically

- **Dataset kind = survey** → the survey block is mandatory (נוהל Table 2 as adapted by the OB
  format: Statistical population, Survey completeness*, Reference area, Collection period, Sample
  frame (one `month_year` row per licensing period), Sampling method, Survey method; optional:
  Sample size/proportion trips & passengers*, Response rate*, Estimation method, Data validation).
- **Extra header keys** (marked * in the format): Contractor (block), Daily periods (block,
  `hh:mm-hh:mm` ascending), Survey days, Vehicle types (block), Survey completeness (מלא / חלקי).
- **Expected files** (Table 5) with their descriptions pre-filled and their field dictionaries
  (Tables 6–12) used to pre-fill `Type`, `Description`, `Comments` and the `Values` of coded fields
  (`day_type` 1/2/3/11–15, `zone_id_*` negative codes −1..−4). Files are matched by name:
  `routes.csv`, `shapes*.zip` / `gtfs*.zip` (GTFS → no field documentation needed, format noted),
  `timetable.csv`, `plan.csv` (same structure as timetable), `trips.csv`, `obad.csv`, `obod.csv`,
  `zones*.zip` / `statistical_areas*.shp` (GIS → CRS/bbox/geometry + `Zones type`), survey report
  `.pdf` (→ Related documents), `*metadata*.xlsx`.
- **Expected key list**: routes→timetable (route_id), timetable→trips (route_id, trip_id),
  trips→obad / obod (trip_id), obod zone_id_orig/dest → zones.zone_id.
- **Naming**: field names must be lowercase `snake_case` English (format §3.4); `trip_id` =
  `line_id_direction_alternative_departure_time[_day_type]_month_year`; `trip_index` is the unique
  per-trip key linking trips/obad/obod.
- Distribution files must not contain identifying data (names, addresses, coordinates of
  origin/destination — `orig_address`, `orig_lat_lon`, `dest_address`, `dest_lat_lon`); no empty
  cells — missing data is `Null`.

## Intake questions specific to OB (ask, then write to metadata-config.json)

1. Contractor(s) that executed the survey.
2. Daily periods used for expansion (e.g. 06:00-09:00, 09:00-15:00 ...).
3. Survey days represented (ימי חול א'-ה' / ו' / ש').
4. Vehicle types sampled (רגיל / מפרקי / מיניבוס).
5. Survey completeness: מלא (all files of Figure 1) or חלקי (boardings/alightings only).
6. Statistical population, Reference area, Collection period, Sample frame (`month_year` rows),
   Sampling method, Survey method; optional sample sizes/proportions, response rate, expansion
   (estimation) method, validation done.
7. Which zones layer was used (statistical areas 2022 / model traffic zones) → `Zones type`, and
   whether the zone key field was renamed to `zone_id` as the format requires.

## Validating older surveys (pre-format, e.g. TLV-metro pulse 1 ver0.8)

Expect many "expected file/field missing" findings (routes.csv / timetable.csv naming, `trip_index`,
`*_factored` fields, `zone_id_*`, `day_period`). Report them as **format gaps** distinct from
**נוהל gaps** (survey block, GIS keys, Files list ≠ Files, key-list syntax, Excel date cells, key
casing). The user decides whether to restructure the data to v1.0 or to document it as-is with a
note in `Comments` that the dataset predates the format. Either way the נוהל gaps must be fixed.

## No code execution available?

Follow `../mot-metadata/SKILL.md` (manual section) and use `references/onboard-format-v1.0.md`
Tables 3–12 as the checklist; `references/profile.json` lists every expected field with its status
(required / required* / optional).
