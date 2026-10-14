# RoadLab 0.11.0 — free movement and terrain following

1. Extract this package. Replace your existing RoadLab addon with RoadLab_Addon_v0110.zip through Preferences > Add-ons > Install from Disk, enable it, and restart Blender.
2. Open RoadLab_XY_Edit.blend. Select the road curve, press Tab, select a control point and use G to move it freely in X/Y. Angled junctions now regenerate.
3. Open RoadLab_Z_Terrain.blend. Move a road control point with G, Z. The road grades between points and the terrain follows its perimeter. The green terrain object still has its original editable source plane.
4. Open RoadLab_Street_Network.blend to test two intersections inside one curve object with multiple splines.
5. RoadLab > Terrain contact controls Follow road surface, Blend distance and Terrain spacing. Smaller spacing creates a denser surface. Turn following off to display the source plane.

## What changed

The road compiler now constructs angle-based junction polygons, triangulates each junction, and stitches quad approach strips through shared vertices. It supports bent POLY roads, multiple junctions and closed loops. Height changes use graded approach profiles; nearly collinear crests use a bounded plane fit to avoid sideways spikes.

Terrain is generated from the unmodified source heightfield plane, with pavement cutouts and matching road perimeter vertices. A quintic distance blend grades back into the source terrain. Terrain sampling avoids extra pavement-edge vertices, preventing T-junction seams in the tested cases.

Unchanged road patches are cached. Z-only terrain edits reuse triangulation and resample affected height domains. X/Y terrain edits currently rebuild the terrain triangulation; the whole road graph is still scanned and its output mesh assembled. Fully local terrain topology updates remain future work. This is not a claim of complete incremental evaluation.

## Limits of this development build

- Editable road source must use POLY splines with constant width within each spline. Bézier roads and point-width transitions are not implemented in the new core.
- NW/NE/SW/SE fields remain network defaults. Independent persistent per-junction/vertex radius controls are still pending.
- The corner panel shows a conservative allowed radius range using angle, width, approach length and neighboring patches. Requested values remain stored; constrained applied values are reported visibly. Extremely short or acute arrangements may have no safe fit and retain the previous surface with a visible warning. Automatic merging of every extreme arrangement is not complete.
- Overlapping roads connect only when their interpolated crossing heights match. Shared junction points across splines must be moved together to remain connected. Linked junction handles are not yet implemented.
- Ground following is for roads resting on terrain. Bridge roads need a separate curve object with Grade terrain to this road disabled. Per-section bridge handling within one network is pending.
- Terrain contact expects an unmodified upward-facing heightfield mesh; the original terrain pipeline is left intact and is not overwritten. New edge-layer/terrain integration, final UV layout, LOD/collision export and parking lots remain pending.
- This is not yet an AAA-certified production mesh pipeline or a guarantee for every input arrangement.

## Validation

Blender 5.1.2 on Linux, headless: ten additional layout checks (including acute angles, bends, multiple junctions, a closed loop and raised roads), eight prior layout regressions, native Edit-mode X/Y/Z changes, central and repeated E extrusion, fresh addon installation, live terrain settings, save/reopen, matching seam vertex sets in both directions and preservation of the source plane. The 46 portable project tests pass. The original-road UI still exposes all 19 original inputs. Windows interactive responsiveness needs user testing.

Screenshots are actual Blender renders. Demo materials are simple gray asphalt and green terrain; no original commercial libraries are included. The mesh compiler runs in Python and Geometry Nodes displays its cached output.
