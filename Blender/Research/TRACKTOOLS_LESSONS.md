# Learning from TrackTools: native expansion redesign

This study compares the supplied TrackTools 2.1.1 node library with our shipped 0.8.2 expansion. The exploratory solver and Edit Mode preview changes in scratch are not a replacement for the redesign described here. No production addon release is made by this study.

## What the source actually shows

TrackTools exposes a reusable even-thickness curve extrusion helper and a polygon-curve information helper. The latter derives neighboring directions, a bisector and an angle-related dot product. The extrusion helper uses curve-space correction before/around the sweep. This is the appropriate starting point for our layered profiles; a generic sweep followed by solid-mesh repair is a more expensive way to compensate for corner geometry.

The native ROAD pipeline produces road surfaces and useful border/intersection data. It already performs road-level intersection processing. TERRAIN_GEOMETRY uses selected subdivision with configurable distance ranges. TERRAIN_SHAPE uses proximity and ray sampling, and also contains optional Boolean operations. TrackTools is not Boolean-free: the lesson is to preserve its shared preparation and avoid repeating expensive work downstream.

Blender already caches evaluated ROAD objects for their dependents. Our cost is not necessarily repeated execution of the entire original ROAD group. Our per-layer groups repeat collection realization, pavement-cutter construction and Boolean cleanup after reading those cached outputs. The road-only reference collection includes all native roads, which also broadens dependency invalidation across otherwise unrelated features.

Our control-field helper is already shared per road. That is useful, but does not share the pavement cutter, junction solving, or terrain contact preparation. We also independently resample layer paths at 0.25 m and control sampling at 0.1 m, regardless of the native resolution setting. Every feature's full solid and top-face boundary curves are then added to the native terrain targets.

## A measured prototype, with limits

`native_curve_helper.py` creates our own thin Geometry Nodes wrappers. One uses a basic curve sweep; the other references the user's installed, unchanged TrackTools even-thickness helper. It copies no commercial groups or assets and saves no original scene.

On Blender 5.1.2, a three-point bent-road test with a 2.2 m sidewalk profile produced:

| Wrapper | Median whole dependency-graph update | Vertices | Faces | Extra WB mesh Booleans |
|---|---:|---:|---:|---:|
| Basic curve sweep | 39.66 ms | 344 | 340 | 0 |
| Native even-thickness helper | 39.79 ms | 344 | 340 | 0 |

Five warm source-point updates were measured per method. The difference is within ordinary timing variation; the result supports reusing native corner correction without a meaningful cost increase in this isolated case.

The original terrain was enabled with its original road-only targets. It did **not** observe the research sidewalk. Per-vertex overrides, partial masks, repeated-layer ordering, crossing lowering, terrain contact, and all difficult corner cases are not integrated in this prototype. These numbers are not a production or large-network speed claim, and the Windows crash was not reproduced or certified fixed by this study.

A separate 0.8.2 bent-road test did not reproduce the claimed sidewalk-versus-curb cost difference: curb cleanup measured about 179 ms and sidewalk cleanup about 147 ms. Both dropped to about 108–110 ms with WB cleanup disabled, then about 11 ms with terrain evaluation also disabled. This identifies significant cleanup/contact overhead in the test, but the user's actual scene and new crash log remain necessary to explain their particular sidewalk behavior.

## Redesign, in implementation order

1. **Shared road preparation.** Keep the original curve and ROAD modifier authoritative. Prepare border paths, stations, tangents, side orientation, source identifiers and layer cumulative offsets once per road. Consume native border density by default; do not automatically densify every path. Use the existing native helper by reference where its contract fits, with no edits to the original commercial groups.
2. **Stable curve-space layers.** Generate each independent ordered profile from that shared preparation. Apply width, gap, height and enable values consistently in the same curve frame. Verify the helper's thickness factor, profile height, crossfall, masks and attribute propagation before integrating it. A native helper is not automatically compatible with our post-sweep displacement math.
3. **Shared terrain contacts.** Build a compact terrain-contact representation per road, using top surfaces and the boundaries needed by the terrain solver. Preserve active-layer height steps, disabled spans, crossing transitions and bridge/tunnel classification. Do not substitute one outer outline if that loses curb/grass height constraints. Connect these contacts to the original native terrain while preserving its subdivision and blending controls. Generated rendering solids must not be the required upstream source for terrain preparation.
4. **Bounded junction work.** Reuse native intersection/border information to identify regions requiring additional work. Solve only affected profile bands around those regions. Keep distant roads out of each feature's clipping inputs. Share a region's preparation across its layers. Benchmark local cleanup before choosing a solver; solver substitution alone is not the architectural repair.
5. **Dependency isolation.** Start with nearby-road references derived from expanded footprint bounds. For networks stored as one multi-spline object, investigate segment/region identifiers and chunk-level snapshots: a per-object collection alone will not isolate that network. Update only snapshots whose geometry or settings changed, without rebuilding them on every viewport draw or repurposing native radius/tilt fields.

## Improvements beyond the current native controls

| Improvement | Benefit | Required correctness check |
|---|---|---|
| Curvature- and corner-aware sampling | Detail where shape requires it, sparse straight spans | Maximum shape error and exact mask endpoints, not just fewer vertices |
| Miter limit with explicit bevel/round behavior | Predictable acute corners and near-U-turns | Preserve specified width and contact; never silently shrink the layer |
| Persistent layer and segment identity | Reorder, insert, duplicate and undo without losing overrides | Interpolate inserted controls and preserve duplicated-instance independence |
| Layer recipes and side-specific controls | Repeat road/curb/grass/sidewalk arrangements consistently | Independent instance data; optional collapse versus preserved gap when disabled |
| Junction corner and crossing-end controls | Independent NW/NE/SW/SE radii and ramp transitions | Skewed approaches, asymmetric openings and disabled curb spans |
| Derived lane connectivity | Lane additions, drops, turn pockets, ramps and median/U-turn setbacks | Retain native curve authoring; derive connectivity instead of replacing it with a JSON world |
| Shared contacts for parking and terrain sculpting | N-gon lots, planter islands and shaped overpass approaches | Ground contact and road clearance across edits; no circular road/terrain dependencies |
| Placement constraints for bridge supports | Automatic spacing plus movable stations on usable ground/medians | Pillar footprint clearance and varying terrain-to-deck height |
| Evaluation diagnostics | Identify slow geometry, terrain, material or helper work in the actual scene | Report timings without forcing extra evaluations or dirtying the scene |

These are proposals and acceptance criteria, not implemented features of the research wrapper.

## Release gates

Compare the same saved scene, shading mode, resolution, hardware and edit sequence with unmodified TrackTools, then with curb-only, sidewalk-only and repeated layers. Record warm median and p95 update latency, worst-case stalls, geometry size, helper memory and unrelated-feature invalidations. Separate cold compilation from steady-state editing. Include straight roads, tight bends, acute/skewed junctions, repeated layers, disabled spans, grade-separated crossings and a larger multi-road network.

The user's crash sequence must be part of the gate: add a curb or sidewalk, edit/duplicate/rotate the road into an intersection, then move controls and change resolution including 1.57 m. Windows 5.1.2 testing and the actual user's scene are required before claiming that Windows crash is fixed.

Installer tests must use Blender's real install/enable/disable/re-enable operators. Check deferred timers, cancellation on disable, file reload and upgrade of existing feature bindings. Original node-group identity and input semantics must remain intact; no commercial library or extracted node definitions belong in the distribution.

For region caching, the key test is that editing one region leaves distant unchanged layer geometry unchanged. For geometry, inspect terrain penetration/gaps, overlap, width at acute angles, height/crossfall, caps, UVs and material assignments. An attractive screenshot and a small-scene speed ratio are insufficient release criteria.
