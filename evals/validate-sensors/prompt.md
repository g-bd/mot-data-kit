---
name: Validate sensor package metadata
tags: [sensors, validate]
plugins: ["../.."]
runs: 2
max_turns: 15
timeout_seconds: 420
allowed_tools: [Bash, Read, Glob, Grep, Skill]
context:
  add_dirs: ["fixtures"]
---

בתיקיית fixtures יש חבילת נתוני גלאים חודשית (SensorDataSal_260701_260731.zip) ללא קובץ מטא-דאטה.
צור לה קובץ מטא-דאטה לפי נוהל הפצת המידע של משרד התחבורה עם הפרופיל המתאים לגלאים, ואמור לי בעברית מה נשאר להשלים.
