#!/usr/bin/env bash
# PostToolUse hook: warn when editing files in homeassistant-config repo
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

if [[ "$file_path" == *"/volume1/docker/homeassistant/"* ]] || \
   [[ "$file_path" == *"/claude_project/homeassistant/"* ]]; then
  echo '{"additionalContext": "Ce fichier vit dans homeassistant-config (pas ha-thermal-soc). Penser à committer séparément dans ce repo avec les conventions HA (branche, commit FR, 1 commit/tâche)."}'
fi
