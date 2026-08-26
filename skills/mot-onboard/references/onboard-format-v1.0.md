# פורמט אחוד לנתוני סקרי און-בורד — גרסה 1.0 (13/11/2024)

Source: משרד התחבורה, אגף תכנון מערכתי / שולחן עגול איסוף מידע (קבוצת עבודה סקרי נוסעים באוטובוסים) ·
page https://www.gov.il/he/pages/transportation-data-distribution · PDF "פורמט אחוד און בורד גירסא 1.0 141124.pdf"
(35 pages; authors ד"ר גולן בן-דור, אינג' מרכוס סניוק). Binding for MoT-funded OB surveys from publication; results are
published on the round-tables site and on data.gov.il. Built on the data-distribution נוהל (v1.3) but self-contained.

The format fixes **how the survey results file is prepared** — not how to run the survey, what to ask, or QA levels.
Orderers may add requirements as long as they do not contradict the format.

## Dataset structure (§3.3, Figure 1 / Table 5)
| File | Status | Content |
|---|---|---|
| routes.csv | required | lines in the survey (line, direction, alternative) |
| shapes.zip | required | geographic description of the survey lines — licensing format or **GTFS** (GTFS → fields need not be documented, only the format stated). Short survey: one file named with the base map id, e.g. `shapes_12_2019.zip`; long survey: one zip per licensing period inside `shapes.zip` |
| timetable.csv | required | licensed timetables of the survey lines (the frame the sample was drawn from) |
| plan.csv | optional | sampling plan: trips planned to be sampled (same structure as timetable.csv) |
| trips.csv | required | trips actually surveyed, incl. trip-level expansion factor |
| obad.csv | required* | boarding/alighting counts per stop |
| obod.csv | required* | questionnaire results |
| zones.zip | required | polygon layer of the survey zones (statistical areas / traffic zones) used to code origins & destinations |
| xxx_year.pdf | required* | survey report (expansion method, statistics, survey method, questionnaire sample) |
| xxx_year_metadata.xlsx | required | metadata |

Whole dataset = one ZIP with all files + one metadata file + documentation. Tables are CSV, GIS in shapefile or GTFS,
report in PDF. Every version gets full metadata noting the version and whether it is partial.

## General rules (§3.4–3.8)
- Field names: English, lowercase, **snake_case** (`car_ownership`, not `carOwnership`); file names as in Table 5.
- Distribution files carry **no identifying data** (names, addresses, O/D coordinates) — only zone codes.
- **No empty cells**: a field without data is `Null`.
- Licensing periods (5 per year) → a survey spanning periods keeps one combined timetable file and one combined
  trips file; period id = `month_year` (`3_2024`) or `month_month_year` (`2_4_2024`).
- `trip_id` (Text) = `line_id _ direction _ alternative _ departure_time [_ day_type] _ month_year`,
  e.g. `21008_1_0_08:00_1_2020`, `21008_1_0_08:00_3_1_2020` (day types: 1 = א'-ה', 2 = ו', 3 = ש'; timetable also
  allows 11..15 = single weekdays א'..ה').
- `trip_index` (Integer, unique) is the key from trips.csv to obad.csv / obod.csv (a trip may be sampled twice).
- Key list to declare: `routes.csv.route_id -> timetable.csv.route_id`, `timetable.csv.route_id -> trips.csv.route_id`,
  `timetable.csv.trip_id -> trips.csv.trip_id`, `trips.csv.trip_id -> obad.csv.trip_id`, `trips.csv.trip_id -> obod.csv.trip_id`
  (+ `obod.csv.zone_id_orig/dest -> zones.zip.zone_id`).

## Metadata header (Table 3) — additions to נוהל Table 1 (marked *)
Publisher, Contact, Contact Email, Author*, Author Email, Title (e.g. "סקר נוסעים באוטובוסים במטרופולין תל אביב, 2023"),
Description (block), Keywords (e.g. און-בורד, סקר נוסעים, מטרופולין תל אביב, אוטובוסים, סקר תחנות), Created, Version*,
Last updated, **Contractor\*** (block, required — executing companies), Temporal coverage, **Daily periods\*** (block,
required — `hh:mm-hh:mm` ascending, e.g. 06:00-09:00, 09:00-15:00), **Survey days\*** (required — e.g. ימי חול
א'-ה' / ו' / ש'), Spatial coverage, Language, **Vehicle types\*** (block, required — רגיל / מפרקי / מיניבוס),
Related documents, References, Legal constrains, **Statistical population** (block, required),
**Survey completeness\*** (required — "מלא" when all Figure-1 files exist, "חלקי" when only counts), **Reference area**
(required), **Collection period** (required), **Sample frame** (block, required — `month_year` rows matching the
timetable), **Sampling method** (block, required), Sample size trips\* / passengers\* (optional), Sample proportion
trips\* / passengers\* (optional), **Survey method** (block, required), Response rate\* (optional), Estimation method
(block, optional), Data validation (block, optional).

## Per-file keys (Table 4) — additions
File name, File format (CSV / Excel / JSON / Shapefile (SHP)), File description, File size, File date, Spatial coverage*,
Spatial reference system* (ITM / EPSG:2039 / GRS_1980 / WGS_1984), Geographic bounding*, Geographic type* (Point /
Polyline / Polygon), **Zones type\*** (zones layer: אזורים סטטיסטיים / אזורי תנועה), **Data encoding\*** (UTF-8 /
Windows-1255), **File comments\***, File fields (block per נוהל Table 4).

## Field dictionaries (Tables 6–12) — see profile.json for the full list with status
- **routes.csv** (T6): route_id Text(key) = line_id_direction_alternative; line_id, line, direction (Integer), alternative,
  operator (Text), cluster_id_survey (required*), orig_line, dest_line, cluster_id_line, line_name, line_type,
  line_service, vehicle_type, line_purpose (optional), length Real (km).
- **timetable.csv / plan.csv** (T7/T8): route_id Text(key), trip_id Text(key), month_year Text (mm_yyyy), day_type Text
  (required*), day_period Text (hh:mm_hh:mm), departure_time DateTime (hh:mm).
- **trips.csv** (T9): trip_index Integer(key), trip_id Text(key), route_id, trip_date Date, day_period, trip_start_time
  DateTime, trip_end_time DateTime, trip_duration Time (computed), trip_vehicle_type (one of Vehicle types),
  number_of_doors, surveyors_planned, surveyors_in_practice, forms_distributed (optional), trip_weight_factor Real,
  total_boardings Integer (from obad), total_boardings_factored Real, max_pass_factored, average_pass_factored
  (optional), num_stops Integer.
- **obad.csv** (T10): trip_index Integer(key), station_index (1..N along the route), station_id (MoT stop code),
  station_name, day_period, stop_time Time, door_closing_time Time (required*), boardings, alightings, through_pass
  (raw), trip_weight_factor, boardings_factored, alightings_factored, through_pass_factored.
- **obod.csv** (T11): trip_index Integer(key), quest_id, quest_strt_Time Time, orig_activity, orig_address*, orig_city,
  orig_lat_lon* (WGS84), zone_id_orig Integer(key) (−1 חוץ לארץ, −2 יישובים פלסטיניים, −3 מחנות צה"ל/שב"ס, −4 לא ידוע),
  first_station_id, first_bus_stop, first_access_mode, first_access_line, first_access_other, dest_activity,
  dest_address*, dest_city, dest_lat_lon*, zone_id_dest Integer(key), last_station_id, last_bus_stop, last_egress_mode,
  last_egress_line, last_egress_other, pt_boardings, trip_frequency, payment_type, gender, employment_status, age,
  driver_license, vehicles_household, accompanying_pass, quest_weight_factor Real. (* = not in the distribution file.)
  Each survey adapts this table to its questionnaire; required fields keep their names.
- **zones.zip** (T12, example = CBS statistical areas 2022): semel_yishuv, shem_yishuv, shem_yishuv_english, stat_2022,
  **zone_id** (rename of yishuv_stat_2022 — national unique statistical-area id), rova, tat_rova*, cod_tifkud,
  shape_length, shape_area. For traffic zones state which model/version in File description.

## How the kit reads this format (0.7.0, proposals from the on-board viewer project, 2026-08)

The format text above is unchanged — this section records where the **kit's reading** of it was
corrected after driving it over eighteen real deliveries. Everything here follows the format; where
the format is silent or contradicts itself, the kit records both readings and decides neither.

- **Table 5, "GTFS → fields need not be documented"** is read as covering the whole delivery
  container, not only a GTFS feed: `shapes.zip` and any licensing zip inside it are carried through
  **unchanged**, so the metadata states the file name and the format and stops there. Their members
  are not documented files, and an unanswered `Description` inside one is recorded in the
  `kit_format_exempt` bucket, never as a blocking error. `profile.json → delivery_files`.
- **A counts-only package** (`Survey completeness = חלקי` **and** no `obod.csv`) does not owe
  `obod.csv` or `zones.zip`. Two conditions, not one: a package that declares `חלקי` and still ships
  questionnaires has zone codes that resolve to something, and owes the layer that resolves them.
  `profile.json → required_files.when`.
- **The documents.** Table 5 lists the data files and says nothing about what a survey is delivered
  WITH. The profile now expects a **summary report / methodology** document (warning when neither is
  there), and records a separate methodology document and a questionnaire at `info`. Never an error:
  the point is that the absence is stated, not that the package is refused. **The summary report IS
  the methodology** — the sampling frame, the expansion method and the field procedure are chapters
  of it — so either shape answers the one checked item, `.pdf` or `.docx`.
- **`trip_index` vs `trip_id`.** §3.8's Key list prints `trips.csv.trip_id -> obad/obod.trip_id`;
  §3.6 and Tables 10–11 name `trip_index` as the key from `trips.csv` to `obad.csv`/`obod.csv`.
  The kit accepts **either** and demands neither in particular (`expected_keys` alternatives).
- **The zones layer's key** is looked for under `zone_id`, `YISHUV_STA`, `YISHUV_STAT_2022`,
  `YISHUV_STAT11`, `STAT11`, `TAZ`; the field that matched is named, and `--deep zones` then
  resolves `obod.zone_id_orig/dest` against it, allowing the documented −1..−4. The format still
  asks for the field to be renamed `zone_id`, and the kit still says so.
- **The CBS statistical-areas field descriptions ship with the profile**
  (`references/cbs-fields.json`, the CBS's own text from `readme_statistical_areas_2022.pdf`).
  Nobody in this kit authored that layer, so nobody in this kit invents its field descriptions —
  and a field the file does not know stays `TODO`.
- **Field names** are matched after the typography is removed: zero-width characters, a stray `?`,
  `last _bus_stop`, an NBSP, case. The canonical name is reported (`field_alias`). A **synonym** is
  deliberately NOT matched — the kit does not decide that one contractor's `boarding` "is"
  `boardings`.
- **`month_year`** accepts `m_yyyy`, `mm_yyyy` and `m_m_yyyy` — §3.7's own examples (`1_2020`,
  `2_4_2024`) are unpadded. `Sample frame` rows are checked against the same syntax, at warning, with
  `timetable.csv.month_year` named as the source of truth.
- **`not_recorded`** is an accepted category token beside `Null` (§3.5): the question was not asked
  or the answer was not written down, which is not the same as "unknown", which is an answer.
- **Open key columns** (`*(key)`, or any column in the declared Key list) get no closed `Values`
  list and no `value_undocumented`: a statistical-area code is an open set of thousands. For those
  the join is what can be checked.
- **`orig_lat_lon` / `dest_lat_lon`** carry `required*` (not plain `required`) beside
  `distribution: false`: required of the survey, forbidden in the distribution file. Their absence
  there is the format being obeyed.
- **`Data encoding`** is a per-file key of Table 4 and is recorded per file; a package that mixes
  encodings is reported (`encoding_not_uniform`).
- **`Contractor`** rows may read `<name> — <role>` (`ביצוע` / `ניהול ובקרה` / `המרה לפורמט האחוד`);
  a bare name means `ביצוע`. Accepted, never demanded — the format has not said this yet.

### Added in 0.7.1 (owner rules, 26/08/2026 — the on-board viewer project)

- **The special zone codes are not orphans.** `zone_id_orig` / `zone_id_dest` carry the codes the
  format defines in Table 11 for a trip end that is not a zone — **−1** חוץ לארץ, **−2** יישובים
  פלסטיניים, **−3** מחנות צה"ל ושב"ס, **−4** לא ידוע. They index nothing in `zones.zip` **by
  design**, so they are excluded from `join_orphans` and from `zone_code_unresolved` — from the
  count and from what the percentage is a percentage of — and reported instead as an `info`
  `zone_special_codes` with how many rows carry each. The kit reads the codes from the profile's own
  `Values` for those fields (`profile.json → expected_files → obod.csv`); nothing is written into
  the code, so a format that adds or renumbers one need only change the dictionary.
- **The zones join is judged in the direction it is used.** The format writes the key line as
  `obod.csv.zone_id_orig -> zones.zip.zone_id`, because the code column points at the layer. Read as
  an ordinary parent → child that counts every zone **nobody travelled to** — 42 % of a national
  layer for a metro survey, and silently nothing for a smaller one. `zones.zip` now carries
  `key_role: lookup`, so it is the parent whichever side of the arrow it is written on, and the
  orphans are the codes the layer does not index.
- **An unknown contractor is an answer.** `Contractor` (and `Author`, `Contact`) may carry
  `לא ידוע` / `לא ידוע — לא תועד במקורות` / `unknown — not documented in the sources`: no `todo`, an
  `info` `value_unknown_documented`, and the row is not split into a name and a role. `?`, `N/A`, an
  empty cell and `TODO` remain errors. See the base twin, `guidelines-v1.3.md`.
- **A zones layer that declares no encoding is still read.** A `.dbf` written in Windows-1255 whose
  code-page byte says only "ANSI" (`0x57`) and which ships no `.cpg` used to fail a strict UTF-8
  decode, leaving the layer with **zero** documented fields — which no answer in
  `metadata-config.json` could ever have filled in. The kit now tries the `.cpg`, then UTF-8, then
  the code page the DBF names, then Windows-1255, and says which it used (`dbf_encoding_assumed`).
  The format's own remedy is still the right one: ship a `.cpg`.

Still open with the format's author, **not** decided by the kit: the definition of
`Sample size passengers` (rows in `obod` or passengers counted in `obad` — they differ by a factor of
three) and of `Response rate` (two ratios in use, differing 2×).

## Appendix 1
Full metadata of the TLV-metro on-board survey, pulse 1 (2019–2022): Publisher משרד התחבורה, Author נתיבי איילון,
Contractor Sigma 6, Vehicle types מפרקי / מיניבוס, Temporal coverage ינואר 2020 – יוני 2022, Sample frame 2019_12,
2020_1_3, 2021_4_6, 2021_10, 2021_11_12, 2022_1_3, 2022_4_6, Daily periods 06:00-00:00, Survey days ימי חול (א'-ה'),
Spatial coverage מטרופולין תל אביב, Dataset file onboard_tlvm_peima_1, Keywords און-בורד, סקר נוסעים, מטרופולין תל אביב,
אוטובוסים, סקר תחנות; Files list routes.csv, timetable.csv, … (see the PDF for the per-file tables).
