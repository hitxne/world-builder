# 0.8.1: native layer performance repair

Keep enabled spans connected; cap only disabled gaps. Use fast viewport Booleans with precise render/review mode and an empty-result fallback. Avoid unchanged modifier retags and stack rewrites on normal control-point movement. Automatically upgrade existing WB groups while retaining socket identifiers and bindings.

Test-scene median with curb and sidewalk: 2.93 s to about 0.12 s per dependency-graph update. Native terrain stays enabled. Layer checks pass in fast/precise modes; existing-group adoption and native/46 portable regressions pass. See README_NATIVE_EXPANSION.md for quality settings and benchmark scope.
