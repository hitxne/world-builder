#!/usr/bin/env bash
set -euo pipefail
BLENDER="${BLENDER:-blender}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/dist/stable"
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT
"$BLENDER" --background --command extension validate "$ROOT/extension"
"$BLENDER" --background --command extension build --source-dir "$ROOT/extension" --output-dir "$STAGING"
"$BLENDER" --background --command extension server-generate --repo-dir "$STAGING"
# Only the newest release appears in the feed. Older archives remain downloadable.
cp "$STAGING"/*.zip "$ROOT/dist/stable/"
cp "$STAGING/index.json" "$ROOT/dist/stable/index.json"
printf 'Repository generated: %s\n' "$ROOT/dist/stable/index.json"
