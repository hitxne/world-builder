# WB Road Lab 0.3 — terrain sculpting update

Start with README_TERRAIN.md and Scenes/WB_Terrain_Sculpt.blend for the new terrain tools. Install WB_RoadLab_Addon_v03.zip. The documentation below describes the retained version 2 example scenes; its terrain limitations apply to that older workflow. The connected version 3 world has separate terrain grading and circular brushes.

This replaces the earlier unvalidated pilot. It is a functioning experimental extension with six example scenes and a native curve-profile proof. It is not the completed master road-engine specification or an exact reconstruction of the reference interchange.

## Quick start
1. Extract the outer WB_RoadLab_v02.zip.
2. Disable/remove the old WB TrackTools Pilot add-on, restart Blender, then install the enclosed WB_RoadLab_Addon_v02.zip through Preferences > Add-ons > Install from Disk. Enable WB TrackTools Road Lab.
3. Open Scenes/WB_Intersection.blend, WB_Arterial.blend, WB_Interchange.blend, or WB_Parking.blend.
4. Press N in the 3D viewport > WB Roads. The scene already contains its graph and controls. Change values and press Apply controls / regenerate. Loading an example explicitly replaces existing WB output and resets that example.
5. Use material colors in Solid view or Material Preview. Example scenes have rendered overview images in Evidence.

The separately installed add-on is required for controls and regeneration. Meshes remain visible without it. Geometry uses meters. Export/import editable graph commands preserve IDs and parameters. JSON is the source model; meshes are derived output.

## Working controls
- Intersection: independent NW | NE / SW | SE curb radii; approach width, length, bearing and lateral offset; curb height, sidewalk width and sampling spacing. Corner identity is attached to adjacent physical approaches. Geographic relabeling after arbitrary rotations is not implemented.
- Crosswalks: each of four endpoints has independent anchor station, opening width, left/right transition length, run, warning depth and rotation offset. Curb and sidewalk geometry depress around the opening. Opposite endpoints face across the road. Move an arrow handle, select it and Capture selected endpoint handle to retain a manual position/rotation. Off-curb positions produce warnings; do not assume all manual placements are solved.
- Boulevard: left-turn pocket consumes median width, fixed outside boundaries, start/taper/end controls; separate median end station and rounded/tapered nose.
- Arterial: three through lanes per direction, independent outside turn pockets, bike bands/green patches, staggered driveway stations. Auxiliary-lane and driveway dimensions appear in the expanded sidebar section. Driveway end surfaces meet the back of sidewalk; final drainage/grade transitions are not a complete engineering model.
- Interchange: lane-to-ramp and ramp-to-lane continuations; split/merge/turn stations, opposing turn connector, independent far-median setback and U-turn guide; paired elevated decks, simple barriers and piers with no inferred connection to the lower road. This is a topology pilot, not the photographed interchange, and the upper highway is not yet connected to ramps.
- Parking: simple convex or concave N-gon perimeter, real planter holes cut from asphalt, island curbs and stall rows. Select an outline in WB_PARKING_OUTLINES, enter Edit Mode, move/add/remove its POLY points, return to Object Mode and Apply edited lot / island outlines. Add a new island from a selected closed POLY curve with Add selected polygon as planter. Polygons use a flat XY plane. Clockwise newly added islands are reversed; existing outlines must retain CCW order.
- Native curve profile: select any source curve and Create selected curve profile (copy). The source is preserved; an independent copied alignment gets WB_ROAD_PROFILE. Edit left/right widths in its modifier and point radii with Alt+S. Existing TrackTools modifiers are omitted from the new copy. This command does not integrate terrain shrinkwrap, original intersection booleans or grading into the new profile.

## Edit protection / rollback
Direct edits to generated meshes and movement-guide curves block regeneration rather than being silently erased. Duplicate/save those objects first or explicitly load a replacement example. Moved endpoint handles must be captured before regeneration. Existing custom materials are reused. Parking outline edits are applied explicitly. Switching/loading examples can explicitly reset parking source outlines; save/export important edits first.
Original uploads were never overwritten. The original ROAD, road_bool, border and terrain node groups are not rewired. Hide WB_GENERATED or reopen your original file to return to the legacy view. Keep an exported graph or saved scene before changing fixtures.

## TrackTools startup copy and dependencies
Scenes/WB_Startup_Extension.blend retains the original scene with a separate WB intersection placed at X=200 m. It needs your original TT_NodeGroups file: copy it beside that scene and name the copy WB_TrackTools_Dependency.blend. The dependency is intentionally not redistributed in this bundle. The source scene references unpacked asphalt and grass textures; copy the original texture folder beside the dependency if you want those legacy materials to resolve. No replacement textures are claimed for the original materials. New WB materials are standalone.

Source ROAD evaluated geometry was unchanged after extension creation and save/reopen: 322 vertices / 270 faces in the supplied .blend. Source terrain has 4,033 vertices; its Boolean face count varied across evaluation (4,157–4,160 observed). Bounds matched and surface-area variation was tiny, but exact original terrain topology invariance is not established. The deep JSON was useful for exact dependency tracing; evaluated current .blend contents take precedence over a report from a different saved state.

## Actual verification
Reference runtime: official Blender 5.1.2 Linux x64, matching the user's version. Its archive SHA-256 matched the published checksum. Real meshes, PNG renders and .blend files were generated in background Blender.
- Six fixtures: evaluated topology, positive signed volume for closed solids, no nonmanifold edges or zero-area faces, UV/material assignments, deterministic regeneration, orphan-mesh regression and saved/reopened vertex hashes.
- 38 portable geometry/model tests: unit conversion, triangulated area, closed topology, outside sidewalk placement, endpoint facing/isolation, taper precision, lane direction, radius isolation, median setback, bridge disconnection, parking polygon/island validation and JSON round-trip.
- Blender workflow tests: load/rebuild operators, captured endpoint override with exact far-endpoint preservation, corner edits preserving manual positions, safe repeated source-curve copy commands; parking outline workflow is separately tested.
- WB_ROAD_PROFILE: left width 3→6 m preserves the −3 m right boundary; radius edit changes evaluated output; planar surface and curved varying-radius proof checked.
Warnings/marking panels intentionally have open edges. Closed per-object topology does not certify absence of every possible surface intersection. Renders and face-volume tests are evidence for these fixtures, not exhaustive user-generated geometry QA.

## Known limitations
New meshes do not deform the legacy terrain or replace road_bool. No universal automatic road junction finder, adaptive lane-conflict solver, swept vehicle-envelope certification, traffic simulation, terrain grading, full bridge abutments/embankments, drainage, signs/signals/lighting or game export is implemented. Lane paths are directed editable metadata/guides; movement markings/arrows and some lane labels remain incomplete. Ramp corners, gores and channelizing islands need a more general branch solver. U-turn clearance is not certified.

Parking presently has one configured road access in the fixture. Multiple access ports, shared neighboring lots, curved perimeter rounding, drive-through queues, accessible symbols/aisles and truck circulation are future work. Stall rows support arbitrary bearing and configurable dimensions in the JSON; sidebar stall-row editing is not implemented. The perimeter is a simple polygon; holes are separate planter definitions. Touching/complex nested polygons and corner cases are not fully supported. Planter/lot outline edits do not automatically relocate an access port. Sidewalk crossings at lot entrances need a complete vertical-grade solution. Panel joints, independent setback sidewalk networks, refuge segments and alternate ramp topologies are unfinished. Manual warning tiles on tight curved curbs need better surface fitting. Original textures were not supplied. No working Unreal adapter/UI is claimed.

## Reproduce
Use Blender 5.1.2 (substitute executable path):

    blender --background --threads 4 --python WB_TrackTools/build_blender.py -- WB_Output "TT_startup_scene_01(2).blend" "TT_NodeGroups(3).blend"
    blender --background --threads 4 --python WB_TrackTools/test_blender_nodes.py -- WB_Output
    blender --background --threads 4 --python WB_TrackTools/test_blender_workflow.py -- workflow_validation.json
    python -m unittest discover -s WB_TrackTools/tests -v

build_blender.py can omit the two source paths to create standalone fixtures only. WB_ONLY_FIXTURES=parking (environment variable) rebuilds just that fixture and retains other report entries. Rebuild on your own PC if using a different Blender version. A Blender script exception may still leave a zero shell exit status; require WB_BUILD_COMPLETE or the test success marker in logs.

## License and standards
The TrackTools license was not provided or verified. This is for the user's private local modification workflow. No permission to publish or redistribute TrackTools data is asserted. The original commercial dependency is excluded from the delivery. Original node graphs remain external dependencies; new WB groups are written independently. See standards_and_reference_notes.md for exact current publications and which constraints are actually checked. Presets are configurable visualization defaults, not engineering certification.
