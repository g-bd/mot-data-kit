---
name: Fix mechanical file defects
tags: [fix]
plugins: ["../.."]
runs: 2
max_turns: 15
timeout_seconds: 420
allowed_tools: [Bash, Read, Glob, Grep, Skill]
context:
  add_dirs: ["fixtures"]
---

בתיקיית fixtures יש קובץ עם שם בעייתי (תווים בלתי נראים ורווחים) ובקידוד Windows-1255.
הצג לי קודם תכנית תיקון (dry-run) של ערכת ה-mot, החל אותה, ותאר בעברית מה שונה ואיפה הגיבוי.
