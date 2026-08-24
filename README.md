# mot-data-kit

**ערכת skills להפצת מידע תחבורתי של משרד התחבורה — לכלי AI.**
**Skills that prepare Israel MoT transport-data metadata — for AI tools.**

---

## עברית

### מה זה

ארבעה skills שמכינים, בודקים, מתקנים ואורזים את **קובץ המטא-דאטה** הנדרש לפי *נוהל הכנה, תיעוד והפצה של קבצי מידע תחבורתי* (גרסה 1.3) של משרד התחבורה, כולל פרופילים ייעודיים לסקרי **און-בורד** (פורמט 1.0) ולחבילות **גלאים** חודשיות (פורמט 1.02).

הפלט: `<שם>-metadata.json / .xlsx / .pdf` בפריסת משרד התחבורה, ולצידו **דוח פערים בעברית** שאומר בדיוק מה חסר או לא תואם.

> הערכה בודקת את **שלמות התיעוד וההתאמה בין המטא-דאטה לקבצים** — היא אינה בודקת את נכונות הנתונים עצמם, בדיוק כמו הנוהל.

| skill | מה הוא עושה |
|---|---|
| `mot-metadata` | הכללי: סורק תיקייה, שואל רק מה שאי-אפשר לגזור מהקבצים, מייצר מטא-דאטה + דוח |
| `mot-onboard` | פרופיל לסקרי און-בורד: קבצי החובה, השדות, המפתחות ובלוק הסקר |
| `mot-sensors` | פרופיל לחבילת `SensorDataSal_*.zip`: שלוש הטבלאות, שמות השדות וכלל ה-NA |
| `mot-fix` | תיקונים מכניים לפי הדוח (שמות, קידוד, ‎.cpg, פגמי מטא-דאטה) — תמיד dry-run קודם, עם גיבוי |

### התקנה

**Claude Code** — שתי פקודות:

```
/plugin marketplace add g-bd/mot-data-kit
/plugin install mot-data-kit@mot-data-kit
```

**Claude.ai / Claude Desktop** — הגדרות ← Capabilities ← Skills ← העלאת skill, ומעלים את
`mot-metadata-skill-<version>.zip` (או את הערכה המלאה) מדף ה-Releases.

**ChatGPT** — פותחים Project, מדביקים ב-Instructions את התוכן של `skills/mot-metadata/SKILL.md`,
ומעלים לקבצי ה-Project את `skills/` מתוך ה-ZIP. עם Code Interpreter פעיל הוא מריץ את הסקריפטים על קבצים שמעלים לצ'אט.

**בלי AI, משורת הפקודה** — מספיק Python 3.10+; החבילות מתקינות את עצמן בהרצה הראשונה.

### שימוש

```bash
python skills/mot-metadata/scripts/mot_metadata.py setup                    # פעם אחת: בדיקה והתקנה
python skills/mot-metadata/scripts/mot_metadata.py build    <תיקייה>        # יצירת מטא-דאטה + דוח
python skills/mot-metadata/scripts/mot_metadata.py validate <תיקייה>        # בדיקת מטא-דאטה קיים
python skills/mot-metadata/scripts/mot_metadata.py package  <תיקייה> --metadata <קובץ>   # אריזת ZIP להפצה
python skills/mot-metadata/scripts/mot_fix.py               <תיקייה> --metadata <קובץ>   # תכנית תיקון (הוסיפו --apply)
```

בכלי AI פשוט מבקשים בשפה חופשית: *"הכן מטא-דאטה לפי נוהל ההפצה לתיקייה הזאת"* / *"בדוק את metadata.xlsx מול הנוהל"*.
ה-skill שואל רק מה שאי-אפשר לגזור מהקבצים (מפרסם, איש קשר, כותרת, תיאורים), וכל מה שנשאר פתוח מסומן `TODO` ומופיע בדוח.

הוסיפו `--profile onboard` או `--profile sensors` לסקרי און-בורד ולחבילות גלאים,
ו-`--deep values,temporal,joins` לבדיקות התאמה מעמיקות בין המטא-דאטה לנתונים.

**מדריך מלא בעברית:** `GUIDE-he.html` (התקנה, שימוש יומיומי, קריאת הדוח, עדכון גרסאות הנוהל).

### מה נסרק

CSV (UTF-8 / Windows-1255 / UTF-16 / gzip), Excel (xlsx וגם xls ישן), Shapefile, GeoJSON, GeoPackage,
ZIP (כולל zip בתוך zip) ו-GTFS. תיעוד קיים (README / PDF / DOCX) נקרא אוטומטית ומשמש לתיאורי השדות.

---

## English

### What it is

Four skills that create, validate, fix and package the **metadata file** required by the Israel Ministry of
Transport data-distribution guideline (*נוהל הכנה, תיעוד והפצה של קבצי מידע תחבורתי* v1.3), with domain profiles
for **on-board surveys** (format v1.0) and monthly **traffic-sensor** packages (format v1.02).

Output: `<name>-metadata.json / .xlsx / .pdf` in the ministry layout, plus a **Hebrew RTL gap report** listing
exactly what is missing or inconsistent.

> The kit checks **documentation completeness and metadata↔files consistency** — never the correctness of the
> data itself, exactly like the guideline.

| skill | what it does |
|---|---|
| `mot-metadata` | the generic engine: scans a folder, asks only what the files cannot answer, writes metadata + report |
| `mot-onboard` | on-board survey profile: mandatory files, fields, keys and the survey block |
| `mot-sensors` | `SensorDataSal_*.zip` profile: the three tables, field dictionary and the NA rule |
| `mot-fix` | mechanical fixes driven by the report (names, encoding, .cpg, metadata defects) — dry-run first, always backed up |

### Install

**Claude Code** — two commands:

```
/plugin marketplace add g-bd/mot-data-kit
/plugin install mot-data-kit@mot-data-kit
```

**Claude.ai / Claude Desktop** — Settings → Capabilities → Skills → upload skill, using
`mot-metadata-skill-<version>.zip` (or the full kit) from the Releases page.

**ChatGPT** — create a Project, paste `skills/mot-metadata/SKILL.md` into the Instructions, and upload the
`skills/` folder from the ZIP to the Project files. With Code Interpreter enabled it runs the scripts on files
you upload to the chat.

**No AI, plain CLI** — Python 3.10+ is enough; dependencies self-install on first run.

### Use

```bash
python skills/mot-metadata/scripts/mot_metadata.py setup                    # one-time: verify + install deps
python skills/mot-metadata/scripts/mot_metadata.py build    <folder>        # create metadata + report
python skills/mot-metadata/scripts/mot_metadata.py validate <folder>        # check an existing metadata file
python skills/mot-metadata/scripts/mot_metadata.py package  <folder> --metadata <file>   # distribution ZIP + checklist
python skills/mot-metadata/scripts/mot_fix.py               <folder> --metadata <file>   # fix plan (add --apply)
```

In an AI tool just ask in plain language: *"prepare MoT metadata for this folder"* / *"validate metadata.xlsx
against the guideline"*. The skill asks only what the files cannot tell it (publisher, contact, title,
descriptions); anything still open is written as `TODO` and listed in the report.

Add `--profile onboard` / `--profile sensors` for those domains, and `--deep values,temporal,joins` for deeper
metadata↔data consistency checks.

**Full Hebrew guide:** `GUIDE-he.html`.

### What it reads

CSV (UTF-8 / Windows-1255 / UTF-16 / gzip), Excel (xlsx and legacy xls), Shapefile, GeoJSON, GeoPackage,
ZIP (including nested zips) and GTFS. Existing documentation (README / PDF / DOCX) is harvested into field
descriptions automatically.

### Tests

```bash
python -m pytest tests -q          # 18 unit tests on synthetic fixtures
claude plugin eval .               # skill-behaviour evals (early access)
```

### Bundled specification versions

| spec | version | date |
|---|---|---|
| נוהל הכנה, תיעוד והפצה של קבצי מידע תחבורתי | 1.3 | 15/05/2024 |
| פורמט אחוד לנתוני סקרי און-בורד | 1.0 | 13/11/2024 |
| פורמט נתוני ספירות גלאים | 1.02 | 31/05/2026 |

When the ministry publishes a new version: `python skills/mot-metadata/scripts/spec_update.py <new-spec.pdf>`
produces a diff against the bundled dictionary to review before updating.
