---
name: Create metadata for a small dataset
tags: [generic, create]
plugins: ["../.."]
runs: 2
max_turns: 15
timeout_seconds: 420
allowed_tools: [Bash, Read, Glob, Grep, Skill, Write]
context:
  add_dirs: ["fixtures"]
---

Create a Ministry of Transport metadata file (per the data-distribution guideline) for the dataset in the
fixtures folder. Do not ask me questions — use the README for descriptions and leave anything unknown as TODO.
Then list, in Hebrew, what a human still needs to fill in.
