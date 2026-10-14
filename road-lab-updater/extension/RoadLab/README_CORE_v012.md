# RoadLab 0.12.0 — planar acute merging and adaptive updates

Extract this package, replace the existing RoadLab addon with RoadLab_Addon_v0120.zip, enable it and restart Blender. Open one of the included editable scenes.

- RoadLab_Acute_Radius_4m.blend: a 22-degree junction whose exposed circular corner retains a 4 m radius, verified against actual perimeter vertices.
- RoadLab_Acute_Merged.blend: a roughly 6-degree branch becomes one pavement footprint. Its swallowed internal corner keeps the requested radius setting, but has no exposed arc; the sidebar says so.
- RoadLab_Nearby_Junctions.blend: nearby intersection footprints merge, remove internal overlap boundaries and generate a shared exposed perimeter.

## Updates while editing

RoadLab > Viewport quality > Mesh updates defaults to Auto. It uses the observed Python rebuild cost: small unmerged road edits can refresh live, throttled to about 30 updates per second. Heavier work waits while Blender's move/rotate/scale or editing operator is active, then builds after placement and a short event-coalescing delay. Numeric-field changes are debounced. The cached surface remains visible while the control curve moves. Cancelling a move whose source returns to the valid state does not rebuild geometry.

After placement forces deferred evaluation. Live forces preview updates and can be expensive on dense scenes. Last rebuild time is shown in the panel. The timing is compiler/terrain time, not a full GPU viewport-frame measurement. These scheduling paths were tested inside headless Blender; Windows mouse-drag responsiveness still needs user testing.

## Mesh changes

Only overlapping planar patches are unioned. Their internal boundaries and overlapping sample grids are removed, and the exposed footprint is retriangulated with one interior grid. Unrelated road patches are reused and retain their quads. Requested radii stay stored. Exposed arcs retain their radius where they fit; constraints and hidden corners are reported explicitly. Terrain holes use the new perimeter, with matching seam vertex sets checked in both directions.

## Current limits

This merging pass is for flat, same-height pavement. Sloped/graded roads continue to use the earlier graded road/terrain pipeline, but complex sloped overlap merging is pending. Different-height crossings are kept separate. Per-junction persistent handles, point-width transitions, edge-layer integration, final UVs and export meshes remain pending. The graph is still scanned and the output assembled; X/Y terrain topology still rebuilds globally. This development build is not yet the completed AAA pipeline.

## Evidence

Five overlap layouts pass independent face-overlap, duplicate-face, winding and closed-perimeter checks. An exposed 4 m arc is verified geometrically. Unrelated street faces remain identical after an edited merge. The ten free-movement layouts and the terrain-following regression pass. Scheduler instrumentation records zero heavy builds across twenty deferred drag updates, one rebuild after placement, zero after cancel, and checks Auto and forced Live paths. Fresh installation is checked separately. Renders are actual Blender output with simple materials and no bundled commercial node libraries.
