# Bridge supports — WB Road Lab 0.4

Install WB_RoadLab_Addon_v04.zip, enable WB TrackTools Road Lab, and open Scenes/WB_Bridge_Supports.blend. Press N in the 3D viewport > WB Roads > Bridge supports.

1. Choose a bridge, default support spacing, column diameter and cap dimensions.
2. Generate default support spacing creates regularly spaced supports and skips blocked positions. Automatic supports begin at half the selected spacing from the alignment start. Skipped positions are reported.
3. Choose an Individual support index and press Load individual support.
4. Change Along bridge to slide that support along the alignment. Across bridge changes its lateral offset. Apply individual support position validates and commits the change. Invalid positions preserve the existing graph and geometry.
5. Individually edited support positions are retained when default spacing is regenerated. Export the editable graph or save the .blend to preserve identities and overrides.

Each support consists of a round vertical column and a wide tapered concrete cap. The cap follows the local bridge alignment and underside elevation. Column height is calculated from the terrain around its footprint to the cap bottom; the foot embeds into the terrain. Terrain sculpting refreshes supports when the sculpting session is committed. Columns must remain beneath their bridge deck.

The complete column diameter plus a configurable clearance margin must fit on clear terrain or inside a median. Road pavement, ramp pavement, parking surfaces, road curbs and sidewalks block placement. A narrow median does not count as valid ground. Median definitions are explicit polygons in support_medians, associated with a ground road; the example creates a real median surface, curb and asphalt opening under the bridges. Graph editing is currently required to create or resize these median polygons.

Native tests exercise default spacing, individual sliding, rejection with rollback, median width rejection, terrain placement, varying bridge height, refresh after terrain edits, positive closed solids and save/reopen persistence. The graphical panel and interactive undo have not been tested in a live graphical Blender session. These are configurable visualization components; foundation design, bearing hardware, girder systems, abutments and structural engineering calculations remain unfinished. Earlier ramp/terrain grading artifacts remain a separate issue.

The original TrackTools uploads were preserved. The new scene and materials are standalone. The older terrain and road example workflows are documented in README_TERRAIN.md and README_v02.md.
