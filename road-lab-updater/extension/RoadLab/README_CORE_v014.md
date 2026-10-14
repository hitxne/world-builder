# RoadLab 0.14 — loops, corners and native editing tools

Install the inner RoadLab_Addon_v0140.zip, enable RoadLab, and open a supplied sample scene. Press T in the 3D viewport to show Blender's toolbar. RoadLab's seven tools appear after Scale. Hover an icon for its name. Use Object Mode for the toolbar brushes; use Edit Mode for control points and selection-based corner settings.

## Toolbar
- Raise / Lower: paint elevation. Radius is metres; strength is metres per second.
- Flatten: paint toward the road height captured at the start of the stroke.
- Smooth: relax local elevation differences. Flatten/smooth strength controls the blend rate.
- Widen: paint increased width. Adds curve handles about every 2 m in the brush region when needed, so the widened road remains curve-authored.
- Bank: click the road and drag sideways to twist the cross-section. Radius controls the affected region; strength controls drag sensitivity. Tilt is limited to about ±34 degrees.
- Slice: click where road-to-terrain contact stops. Terrain contact remains disabled toward that spline's end until Alt + Slice reconnects it. On closed splines, the completed cut uses the shorter arc between the two cuts.

Wheel adjusts brush radius. Releasing LMB completes one undoable stroke. Esc cancels the stroke and restores its source data. Road geometry previews during the stroke; terrain updates at release. Terrain and source curve remain editable. Top-bar tool settings show radius/strength only for brushes; Slice shows detach/reattach guidance. Road sculpt in the sidebar provides reset actions.

## Selected corners
Move road points with G then Z. The redundant numeric point-height controls were removed from the panel. Select a bend or junction point and expand Selected points → Corners. Only applicable directions appear, arranged NW/NE above SW/SE. Choose one direction, then edit its Radius or Lift. Lift is a smooth local elevation offset relative to the curve's base height, allowing local embankments. Inner and outer corners are labeled; limits are reported if a requested outer radius would consume the road's opposite edge. The corner panel is hidden at straight or endpoint selections.

## Closed loops
Closing a spline or joining two branches with F retains the terrain island inside the road. Both inner and outer borders are normalized for constrained triangulation while preserving signed coverage. Exterior bends use circular fillets rather than sharp miter joins.

## What stays authored
Elevation sculpting and banking use a sparse road-local 1 m displacement grid; they do not overwrite the source curve or terrain plane. Width sculpting adds/edits authoring handles. Bridge cuts change a face-level ground-contact attribute while retaining the complete visible road. Terrain under the bridge returns toward its editable source height.

## Current limits
This is the first brush/toolbar implementation. Headless Blender tests verify real geometry, settings, tool registration, keymaps, icons, source preservation, save/reopen and seams. Native Windows mouse interaction and interactive undo have not been manually tested.

Bridge boundaries snap to generated mesh faces, so precision depends on road sample spacing. A bridge span is constrained to one spline. Cuts are stored in road-local space and reprojected when a path changes; reapply them after major spline reordering. Slice defines terrain contact only; it does not raise the deck, add deck thickness, or generate pillars. Corner lift affects the selected geographic corner through a smooth radial falloff rather than direct selection of an evaluated mesh vertex. The deformation grid is fixed at 1 m. Sculpting does not add topology; sample spacing must be fine enough for the desired detail.

Acute footprint merging with tapered approaches remains unsupported; a rejected width edit retains the last valid geometry, and Esc restores the source for that stroke. The core is not yet a final AAA export pipeline.
