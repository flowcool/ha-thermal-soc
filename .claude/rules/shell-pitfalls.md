---
description: NAS shell environment pitfalls that break common patterns
---

# Shell Pitfalls (NAS / UGreen DXP4800PLUS)

- `rm` and `cp` are aliased to `rm -i` / `cp -i` — interactive prompts break `&&` chains silently. Always use `\rm -f` and `\cp`.
- Python heredocs (`python3 - <<'EOF'`) inside `&&` chains produce empty output. Save scripts to `.py` files and run them directly.
- `monitor_passive.sh` writes via nohup fd — never `mv` that file while the process runs. Use `cp` to a new path, replace after stopping.
