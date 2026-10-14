#!/usr/bin/env bash
set -euo pipefail
BLENDER="${BLENDER:-blender}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/dist/stable"
"$BLENDER" --background --command extension validate "$ROOT/extension"
"$BLENDER" --background --command extension build --source-dir "$ROOT/extension" --output-dir "$ROOT/dist/stable"
"$BLENDER" --background --command extension server-generate --repo-dir "$ROOT/dist/stable"
printf 'Repository generated: %s\n' "$ROOT/dist/stable/index.json"
