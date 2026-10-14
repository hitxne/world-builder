# WB Road Lab 0.5 — terrain face clearance

Disable the earlier Road Lab add-on, install WB_RoadLab_Addon_v05.zip, enable RoadLab, and open Scenes/WB_Clear_Terrain.blend. The bridge support and terrain panels are under N > RoadLab.

For your existing v0.3/v0.4 scene, install the updated add-on and use Terrain sculpting > Apply detail / rebuild terrain once. This adds the face-clearance attributes required by the sculpting tool. Save a copy of your scene first if you want to retain the previous result. Direct edits to generated geometry continue to block replacement.

## Fix

The earlier terrain protection tested vertices and used an edge collar. Faces between those vertices could still cross pavement. Some raised ramp sections were also absent from the grading targets, so the first attempted fix missed them. Version 0.5 grades against ground surfaces, then separately checks whole terrain-triangle overlaps against the final assembled physical surfaces, including elevated roads and ramp sections excluded from upward grading.

Pixel inspection also found green slivers in narrow gaps between the ramp and parent street. Closed asphalt transition aprons now cover those fork/merge gaps, overlap the adjoining pavement by 0.2 m, and cut the corresponding curb/sidewalk openings. They remain separate closed solids to avoid Boolean slivers at the joins; a single welded export mesh is not claimed for these pieces. Each connection can set apron_length in JSON (40 meters by default, zero disables it). This is a local connection transition, not a general junction or lane-conflict solver.

Each overlap is clipped in XY. Terrain and pavement heights are affine over each triangle, so the maximum height difference occurs at a vertex of that clipped polygon. Violating terrain faces are lowered beneath the full pavement thickness plus the configured clearance gap, rather than just below the asphalt top. Shared-vertex lowering preserves constraints already satisfied. Per-vertex upper limits then keep Raise, Lower, Smooth and Flatten from recreating those overlaps.

Committed sculpting stores both the editable baseline and the visible terrain surface. The visible surface is reused or resampled when the road geometry, world bounds and grading settings match. Road changes invalidate that snapshot and calculate new grading/clearance. Exact scene save/reopen retains the source and protection attributes.

## Evidence and limits

The supplied scene is checked against all overlapping terrain/surface triangle pairs, with zero clearance violations after rebuilding, all four brush modes and save/reopen. The test also detects the defect in the previous saved scene. Forty-six portable tests pass, including the case where a road crosses a terrain triangle but all three terrain vertices lie outside the road footprint. A separate final check verifies clearance beneath the full 0.22 m pavement plus a 0.025 m gap, closed positive solids, and asphalt at the previously green screenshot pixels. Exact overlap counts are in the validation reports.

StreetClear.png repeats the prior street-level camera. OverviewClear.png shows the complete network. The images are actual Blender renders. Live graphical brush UI/undo testing remains outstanding. This fixes the terrain protrusions; the previously identified steep ramp/embankment transitions and unfinished bridge detailing remain separate work. The conservative face correction can lower a small area beside a pavement edge, especially on a coarse terrain grid. Finer terrain detail reduces that effect.

Bridge spacing and individual support controls remain as documented in README_BRIDGES.md. All original upstream files remain untouched and the commercial dependency is excluded.
