# Large-map scalability — core architectural priority

The user intends to build a huge map. Scalability is a parallel priority alongside UI design and usability, not a late optimization. New systems must preserve large-world compatibility. Operational ease of use and large-world foundations take precedence over expanding the construction catalog or export targets.

## Current blockers, observed in source

- One editable terrain mesh; generation UI dimensions limited to 512 m and heightfields to 129×129 samples. Increasing dimensions decreases terrain detail without adding samples.
- Every editable object is resident. There is no chunk streaming or overview representation.
- A single embedded .wbworld snapshot holds geometry/textures. Open rejects files over 128 MiB or 2,000 objects.
- Undo captures full-scene JSON. Each brush rebuilds the terrain and every following road; history is bounded by 20 snapshots/32 MiB.
- Control-point coordinate fields are bounded to ±2,000 m. Float transforms have no managed large-world coordinate scheme.
- Independent mesh/material instances, synchronous scene capture and lack of measured runtime budgets limit scale.

These are existing safety/foundation limits, not advertised huge-map capacity. Raising or removing them without changing the architecture is insufficient.

## Implementation order

1. **Chunked world source and persistence.** Separate the world index, terrain chunks, shared assets and placements. Keep stable IDs and a migration path from current projects; preserve existing sources and saves. Support atomic changed-chunk writes rather than rewriting every mesh and texture. Reject unsupported project versions clearly.
2. **Local terrain/road updates and history.** Only rebuild affected terrain chunks and intersecting dependent road spans. Preserve terrain seams, road continuity and undo across chunk boundaries. Replace full-world brush snapshots with bounded changes while retaining reusable shared history.
3. **Asset reuse and visibility/detail.** Share immutable meshes/materials/textures between placements; detach copies for actual edits. Add LOD/instancing/culling where appropriate. Maintain cheap world overview geometry while the active lot/area retains precise editing detail. Reduce collider detail/residency separately from visual detail.
4. **Asynchronous residency.** Load needed chunks around the camera/editing area, with configurable budgets, progress and cancellation. Protect dirty/active chunks from eviction until saved. Navigation to distant areas must load the required editable data; the overview must not rely on all detailed chunks being loaded.
5. **Coordinate precision.** Store global world positions independently of local Unity float transforms. Use chunk-local coordinates and a managed origin strategy for rendering, physics, input, placement, history and export. Camera-relative shading alone is insufficient.
6. **Measured acceptance.** Profile both the editor application and standalone Windows player. Establish target hardware/map dimensions/density as measured test inputs, not assumed capacity. Report actual frame times, memory, draw calls, terrain update latency, chunk loading and save times.

## Non-negotiable editing behavior

Users can zoom from island overview to a lot, edit with direct feedback, navigate away, return and recover the same editable source. Saved unloaded chunks remain part of the world and exports. Search/hierarchy cannot silently omit unloaded objects. Undo, references, source provenance and export must work across residency boundaries.

## Scale validation

Build original synthetic test worlds with increasing extent and object density. Test chunk-border sculpting, roads across boundaries, many shared tree/building placements, navigation to distant locations, autosave/recovery, and save/reopen while chunks are unloaded. Record hardware, world size, resident versus total objects and peak memory. Verify corruption/cancellation recovery and compare reloads with authoritative source data.

Performance budgets must be calibrated on the user's actual target hardware. Do not claim a maximum map size or sustained frame rate without measurements. Current status: **Not started for streaming/chunk persistence; small-scene source available; huge-map acceptance unverified**.

## Immediate next engineering work

Audit and introduce chunk-local world/terrain source boundaries and affected-area update tracking while continuing UI feedback/navigation repairs. Preserve the existing small-world workflow during migration. Do not add a large-map-size slider that suggests streaming or scalable persistence already exists.
