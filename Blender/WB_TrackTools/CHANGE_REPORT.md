# Change report — WB Road Lab 0.2

## Phase accounting

| Phase | Status | Evidence / remaining work |
|---|---|---|
| 0 | Implemented with dependency limitations | Actual Blender 5.1.2 baseline, exact report inventory, linked library repaired locally. Original textures absent; license unknown. |
| 1 | Partially implemented and tested | Safe copied scene; schema v2, editable metadata and sidebar. Fixture-specific graph, no automatic v1 topology migration or complete unified network schema. |
| 2 | Asymmetric-width proof implemented/tested; integration partial | Native sweep and radius tests, curved proof; median/outside pockets change widths. No new terrain-fit or original Boolean integration. |
| 3 | Partially implemented and tested | Connected skew/offset junction, independent corners, directed movements, interchange lane continuations. No complete arbitrary-junction or vehicle conflict solver. |
| 4 | Partially implemented and tested | Median ends/setback, shaped curbs, attached sidewalks, two crosswalks and four endpoints with depressed openings/tiles. Alternate ramp types and independent setback sidewalk networks unfinished. |
| 5 | QA and exchange partial; detailed infrastructure deferred | Six saved/reopened fixtures, UVs/materials, volume/topology and edit-protection checks. No complete markings library, drainage, surveyed interchange, Unreal runtime or game exporter. |
| Extra: parking | Functional tested prototype | N-gon footprint, actual island holes, editable outline curves, road access and stall rows. Multiple access ports/aisles/vertical access grading incomplete. |

## Evaluated fixture statistics

| Fixture | Mesh objects | Vertices | Faces | Regenerate + inspect (s) | Save/reopen |
|---|---:|---:|---:|---:|---|
| intersection | 23 | 41918 | 31189 | 4.24 | passed |
| skew | 23 | 41900 | 31170 | 8.812 | passed |
| boulevard | 35 | 4766 | 4703 | 0.792 | passed |
| arterial | 90 | 8756 | 8194 | 5.627 | passed |
| interchange | 62 | 5527 | 4633 | 3.507 | passed |
| parking | 53 | 636 | 474 | 0.275 | passed |

Timing includes generation and diagnostics on this runtime, not a performance guarantee. Boolean and high-density warning panel work is included. All closed-solid signed volumes were positive in the final fixture pass; warning panels/paint remain intentionally open.

## Original graph trace and WB group mapping

- ROAD: Radius.002 → Store Named Attribute.009 (rad); roadID propagated via Store Named Attribute.018 and other comparison/sample nodes. Named Attribute.012 (rad) → Set Curve Radius.001.Radius.
- road_bool: Named Attribute.004 (rad) → Curve to Mesh.001.Scale (input index 2), and Switch.002.False. This is the actual radius-to-width scale path identified in the supplied detailed graph.
- Mesh Boolean.002.DIFFERENCE and roadID propagation remain untouched; no global scale factor was inserted into road_bool.
- |DJH_border_curve and both terrain groups remain linked original dependencies.
- WB_ROAD_PROFILE: new independent curve resample + asymmetric line profile + Curve to Mesh with Radius connected to Scale + material assignment. The new copy workflow omits original ROAD modifiers; it is not rewired into road_bool.
- WB_CURB_PROFILE: standalone rectangular-profile sweep, rather than a passthrough or cylinder. Adaptive depressed curbs/sidewalks are produced by the portable Python geometry kernel.
- Proposed master names WB_LANE_BOUNDARIES, WB_MEDIAN_PROFILE, WB_CORNER_RETURN, WB_CROSSWALK, WB_CURB_OPENING, WB_CURB_RAMP, WB_SIDEWALK and WB_MARKING_GENERATOR were not created as misleading empty groups. Their implemented geometry functions, where present, live in geometry.py.

## Required pilot fixtures A–H

| Fixture request | Result |
|---|---|
| A | Legacy source evaluated; native curved varying-radius proof supplied. Legacy terrain behavior not byte-identical in topology. |
| B | Independent width sweep tested; taper precision in portable test and lane pockets in boulevard. Not grafted into legacy terrain. |
| C | Boulevard pocket narrows median with opposing outer boundary fixed. |
| D | Connected skew fixture with four distinct, independent corner radii and lane guides. |
| E | Two crosswalks/four independent endpoints, manual override preservation and rendered detail. |
| F | Attached sidewalk and driveway crossings implemented; independent setback spline/grass-buffer termination not complete. |
| G | Paired upper decks over lower road with no inferred lane connection; placeholder structural geometry. |
| H | Reference-informed ramp/interchange prototype; not an exact large surveyed intersection recreation. |