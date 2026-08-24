# פורמט המרת נתוני גלאי נת"י לסל הספירות הלאומי — גרסה 1.02 (31/05/2026)

Source: משרד התחבורה, אגף תכנון מערכתי / שולחן עגול איסוף מידע. Circulated by e-mail as
`260531 פורמט נתוני ספירות גלאים - גירסא 1.02.docx`; the gov.il page
https://www.gov.il/he/pages/uniform_format_traffic_sensors was **not yet live** when this was written (08/2026) — a
letter from ליאור רוזן (מנהל אגף בכיר תכנון תחבורתי) about sensor-data transfer by the corporations will accompany it.
Current version = section (חתך) level; a junction (צומת) level is planned. The conversion rules (5-min → hourly, invalid
data, directions) are based mostly on the uniform traffic-counts format.

## Purpose
Coordinate the monthly transfer of traffic-volume data from Netivei Israel's traffic-management system (radar
detectors per lane, continuous all year) to the CBS (הלמ"ס) for the national count basket (סל הספירות הלאומי): convert
lane-level high-resolution detector data into **hourly counts per road section and direction**.

## Monthly package
`SensorDataSal_<from_date>_<to_date>.zip` (dates `yymmdd`, e.g. `SensorDataSal_260101_260131.zip`) containing three CSV
files `SensorDataSal_<from>_<to>_table1.csv`, `_table2.csv`, `_table3.csv`. Each month stands alone and contains only
that month's counts; all active sensors are included. (Real files are Windows-1255 encoded with Hebrew headers.)

### Table 1 — count period (one row)
מתאריך, משעה — start of the monthly count period · לתאריך, לשעה — end · תקופה (דק') — output time base in minutes
(60 = hourly) · סוג רכב 1–5 — vehicle-class code definitions: 1 דו גלגלי, 2 פרטי, 3 מסחרי, 4 משאית/אוטובוס, 5 משאית
כבדה · גרסת פורמט — format version of the file structure. Acts as the header of the other files.
Real header: `מתאריך, משעה, לתאריך, לשעה, תקופה דק, סוג רכב 1..5, גרסת פורמט`.

### Table 2 — sensor list (one row per active sensor)
קוד גלאי — unique detector id · מספר דרך / ק"מ מקום הצבה — linear location · קואורדינטה (WGS84 `POINT(lon lat)`) ·
קואורדינטה X,Y (ITM) · סוג גלאי (מכ"ם / מצלמה / לולאה) · תיאור זרוע 1 / זרוע 2 — nearest junction/interchange names
up-road (זרוע 1) and down-road (זרוע 2) · זרוע 1 ק"מ / זרוע 2 ק"מ · מספר נתיבים זרוע 1 / זרוע 2.
Junction names and km posts come from Netivei Israel's GeoNet. The sensor belongs to the section between arm 1 and arm 2;
direction 1 = flow from arm 1 to arm 2, direction 2 = from arm 2 to arm 1. Arm 1 is the side where the km post is lower
(km increases from arm 1 to arm 2).
Real header: `קוד גלאי, מספר דרך מקום הצבה, קמ מקום הצבה, קואורדינטות, ITM קואורדינטות, סוג גלאי, תיאור זרוע צומת 1,
זרוע 1 קמ, מספר נתיבים זרוע 1, תיאור זרוע צומת 2, זרוע 2 קמ, מספר נתיבים זרוע 2`.

### Table 3 — hourly counts (one row per sensor-hour)
קוד גלאי (per Table 2) · תאריך · משעה, לשעה (e.g. 08:00–09:00) · מזרוע 1 לזרוע 2 – סוג רכב 1..5 (direction 1 volumes) ·
מזרוע 2 לזרוע 1 – סוג רכב 1..5 (direction 2 volumes). Exactly one row per sensor per hour with both direction groups.
Size: rows = sensors × 24 × days (≈ 432k rows for 600 sensors / 30 days). A count may be `0` (no vehicles) or `NA`
(no data — see below).
Real header: `קוד גלאי, תאריך, משעה, לשעה, מזרוע 1 לזרוע 2-סוג רכב 1 … 5, מזרוע 2 לזרוע 1-סוג רכב 1 … 5`.

## Location, section and arms (§3)
Sensor location = verbal description ("דרך 65, בין מחלף X למחלף Y"), road number + km (of the sensor or its lighting
pole), a representative coordinate, and the section geometry (which movements are counted and how they group into arms).

## Lane → direction conversion key (§4)
The management system reports per sensor and **lane code**. A conversion key (system table, maintained before every
monthly file) maps each sensor-lane to direction 1 / 2: define the sensor's section (road, km, coordinate) → set the arms
(§3) → assign each lane code to an arm using orthophoto / road plans → record (sensor, lane, direction).

## Hourly aggregation (§5)
Input rows: sensor, lane, T_start, T_end = T_start + Δt, volumes per class 1–5.
Step A: join the key, replace lane by direction, sum classes over all lanes of the same section-direction per Δt.
Step B: for every station, direction and day, for each hour 00–24 collect the Δt intervals whose start lies in the hour;
`Coverage_minutes = N_intervals × Δt`. If coverage = 60 → full hour: `Volume_hour[class] = Σ Volume_Δt[class]`.
If coverage < 60 → partial hour: **no completion or extrapolation; all class volumes = NA**.

## Partial hours (§6)
Communication failures, disabled sensors, counts starting/ending mid-hour → partial coverage. Rule: only a full hour
(all planned intervals, all lanes of the section-direction) gets volumes; if even one interval is missing, all five class
fields are null — the row is still written (date + hour) to keep the chronological sequence. In CSV, null = empty cell or
an agreed token such as `NA`; **never 0** (0 means "no traffic", not "no data").

## Description template (for the metadata)
"נתוני נפח תנועה שעתיים לפי חתך דרך וכיוון, שהומרו מנתוני גלאי מכ"ם לפי נתיב של מערכת ניהול התנועה של נתיבי ישראל,
בהתאם לפורמט המרת נתוני גלאים לסל הספירות הלאומי גרסה 1.02. הקובץ החודשי כולל את תקופת הספירה (טבלה 1), רשימת הגלאים
הפעילים עם הגדרת הזרועות (טבלה 2) וספירות שעתיות לפי 5 סוגי רכב ו-2 כיוונים (טבלה 3). שעות ללא כיסוי מלא מסומנות NA."
