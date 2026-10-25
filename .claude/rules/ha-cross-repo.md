---
description: HA integration files live in a separate git repo — commit there separately
---

# HA Cross-Repo Commit Rule

The HA migration writes files that live in **`flowcool/homeassistant-config`**, not this repo.

## Paths (same physical location)

```
/volume1/home-assistant/homeassistant/config/     (source of truth, = HA /config)
/home/flow/claude_project/homeassistant/         (symlink to same)
```

## Files owned by TSOC migration in that repo

- `packages/projet_thermal_soc.yaml`
- `templates/sensor_thermal_soc.yaml`
- `configuration.yaml` (recorder entries for `input_number.thermal_walls_*`)
- `automations.yaml` (TSOC notification wiring)

## Rule

A `git commit` from this project root **never touches those files**. Any session editing HA-side files must separately `cd` into `homeassistant-config` and commit there, following that repo's conventions (branch-then-merge for structural work, French commit messages, 1 commit per logical task, no force-push).

Incident: 2026-07-01 to 2026-07-04 — HA config changes sat uncommitted 3 days.
