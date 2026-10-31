---
name: elara-skill-upkeep
description: Review and refine the ELARA skills in .claude/skills - fold in lessons from recent commits and sessions, fix stale commands, merge or split skills. Use at the end of a substantial session, when a skill's instructions turned out wrong, or when asked to tidy the skills.
---

# Skill upkeep

1. `git log --since="2 weeks ago" --stat` and STATUS.md: what changed in flow, tools, traps?
2. For each skill: run (or dry-read) every command it gives; fix what is stale.
3. Add new traps where they bite; delete advice that no longer applies. Keep each
   SKILL.md under ~80 lines; move detail into the scripts' docstrings.
4. A recurring multi-step manual procedure -> new skill (`elara-<topic>`), with a
   description that says WHEN to use it.
5. Append a dated changelog line to every skill touched; commit with the change.

Current toolbox: elara-design-flow, elara-pin-audit, elara-docs-sync,
elara-env-setup, elara-skill-upkeep.

### Changelog
- 2026-10-31 created.
