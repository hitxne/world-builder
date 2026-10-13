# Circular terrain brushes — WB Road Lab 0.3

## Quick start

1. Extract the outer WB_RoadLab_v03.zip.
2. Disable the previous WB Pilot / Road Lab add-on. Install the enclosed WB_RoadLab_Addon_v03.zip through Blender Preferences > Add-ons > Install from Disk and enable WB TrackTools Road Lab. Tested with Blender 5.1.2.
3. Open Scenes/WB_Terrain_Sculpt.blend.
4. Press N in the 3D viewport > WB Roads > Terrain sculpting.
5. Choose Raise, Lower, Smooth or Flatten, set Brush radius and Strength, then click Sculpt terrain. Drag the left mouse button over the ground.
6. Enter or right-click keeps the session. Esc restores the terrain from before the session. Save your .blend to retain the edits.

Shift + wheel changes radius; Ctrl + wheel changes strength. Middle mouse and the unmodified wheel navigate. Use Object Mode. The orange ring shows the footprint. Raise/Lower strength is meters per second; Smooth/Flatten strength is response speed. Flatten can sample the starting height of each drag or use an explicit elevation.

## Terrain detail and persistent hills

Terrain detail spacing controls mesh resolution in meters. Lower values provide more vertices for smaller brushes. Apply detail / rebuild terrain resamples your stored terrain baseline without resetting it. The terrain grid is limited to 250,000 vertices. Hills and depressions can have arbitrary height-field shapes; caves, overhangs and adaptive mesh subdivision are not supported.

Brush edits change a stored baseline and reapply grading. Vertices beneath grade-controlled pavement remain at the pavement target. Surrounding terrain blends toward the road using Road grading blend. Elevated bridge decks do not directly raise the ground beneath them, so the underpass stays open. Bridge-side embankments can be sculpted manually. Detailed bridge abutments, concrete slope coverings and complete bridge structures are unfinished.

Use selected mesh as terrain baseline captures a separate evaluated terrain mesh in world coordinates without modifying it. That mesh must cover the configured terrain bounds and supply a height at every sample. Incomplete meshes fail without replacing the existing WB result. Hide your original terrain manually to avoid overlapping surfaces.

## Connected example

The v3 graph connects lower-road lanes to highway lanes through ramps. The N-gon parking lot has two separate road accesses and real planter holes. Openings cut through the road/lot curbs. JSON stores road alignments, lane IDs, connection stations and Bezier handles, parking grade planes and access anchors. Import/export is in the main WB Roads panel. A complete graphical network editor is unfinished; network entity changes currently use JSON.

The example is a geometry demonstration, not a reconstruction of the photographed interchange. Diagnostics currently flag a steep entry ramp and a steep automatic grading transition. Automatic grading is not a complete earthworks solver. Protected roadbed height changes require editing the road/ramp graph. The original TrackTools files were preserved and their commercial dependency is excluded from this package.

## Actual verification

Native Blender tests cover the supplied connected solids' closed topology, nonmanifold edges, zero-area faces, brush modes, circular locality, protected roadbed, rebuild preservation, finer terrain resampling and save/reopen. The earlier 38 portable road-model tests and four new brush tests cover the kernels.

The modal cursor, navigation and graphical undo behavior have not been exercised in a graphical Blender session here. Images are actual Blender renders from delivered geometry. They are not UI screenshots or illustrations.

To reproduce:

    blender --background --factory-startup --threads 4 --python WB_TrackTools/test_terrain_native.py -- WB_Output_v03

Require WB_TERRAIN_TESTS_PASSED and WB_TERRAIN_RENDERED in the log. Blender may return shell status zero after a Python exception. See Evidence for native test reports and overview/bridge-side hill renders.
