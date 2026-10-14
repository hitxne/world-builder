# RoadLab 0.9.3 — Blender test build

RoadLab adds a unified sidebar to the existing curve-and-terrain workflow. The sidebar writes directly to native modifier inputs; it does not maintain a second copy of their values.

## Install and open the sample

Disable the previous road add-on and restart Blender. Install RoadLab_Addon_v093.zip, enable RoadLab, then open Scenes/RoadLab_Sample.blend from the test package. Press N, choose RoadLab, open Scene, and use Link node library to select your existing .blend containing ROAD, TERRAIN_GEOMETRY and TERRAIN_SHAPE. Save your own copy.

The original commercial library and texture assets are external dependencies. They are not included in this package.

## Sidebar navigation

Every section and each individual layer's settings starts collapsed. Blender may remember expansion states from an earlier session.

- Scene: choose the road and terrain, connect the scene or its external node library.
- Road shape: width, sample spacing and crown rise; Edit road curve selects the original curve and enters Edit Mode.
- Junctions: native junction smoothing. This is not independent corner-radius control.
- Road elevation: height, terrain following/reference, bridge and tunnel thresholds.
- Edge layers: ordered curb, grass and sidewalk instances, reorder and Remove. Expand each instance to change its point settings. The selected list row determines the cross-section and crossing-ramp target.
- Terrain contact: fitting distances, cutouts and refinement bands.
- Curve processing: original input subdivision, alignment offset and smoothing controls.
- Materials: asphalt, terrain and selected-layer materials. Texture mapping is a collapsed child section.
- Viewport quality: fast curve editing and exact layer junction cleanup.

Smaller Sample spacing values generate finer road samples. Layer sampling is still separate from road sampling; this build does not fix that architectural limitation.

## Point controls and layers

In Object Mode, Width, Gap before layer, inclusion and height apply to all original road control points. In the road's Edit Mode, they affect selected points only. Read first loads the first selected point's values. Exclude and Include remove or restore a span. Remove deletes one entire layer, clears its point fields and closes its space in the stack; shared profiles are preserved.

Grass has no underside or sidewalls. Its outer edge anchors 5 mm above the editable base terrain mesh. It does not sample the fully evaluated terrain with road-contact modifiers, which would create a dependency loop. Inner height offset moves the road-side edge. Existing generated rectangular grass profiles are converted to open top profiles.

Add branch creates a separate connected spline from one selected road point and inherits its layer settings. It preserves the through-road topology. It does not establish that normal central-point extrusion or the resulting junction mesh is correct.

## Recover grass and asphalt materials

The sample uses plain display-color materials, not the original textured materials. Materials > Import materials imports material datablocks from your original Blender scene without replacing current assignments. Select the imported asphalt, terrain and layer materials in the same section. Locate textures searches your chosen texture folder for missing images. For asphalt image textures, enable Generate UVs in Texture mapping and switch Blender to Material Preview or Rendered view. Solid view shows display colors.

## Current limits and evidence

Installation, sample library relinking, all 19 native road inputs in the sidebar, collapsed defaults, material import/texture lookup, layer removal, grass surface fitting and selected-point branch inheritance have passed limited Blender 5.1.2 Linux checks. These checks do not replace manual Windows UI verification.

The branch/junction road-mesh defect is unresolved. Corners and layer junctions can still fold or tear. The optional RoadLab_Junction_Stress.blend intentionally exposes those defects. The earlier Windows crash sequence has not been verified fixed.

Independent native lane topology, corner radii, median systems, crosswalk endpoints, parking/planters, sculpt brushes and bridge supports are not completed in this native workflow. Separate legacy examples are not proof of integration. The shared native-pipeline performance redesign is incomplete. The original source files are preserved.
