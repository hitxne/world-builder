# Integrated world and lot construction milestone

## Reprioritization against the full directive

The original acceptance target is an independent editable world: island/water,
sculpt/paint, roads/buildings, imported textured model, transforms, save/reopen,
interchange export and Windows launch. Earlier work over-focused on game-file
inventory/car previews. This increment addresses the actual construction path;
proprietary format investigation is supplementary and does not gate the core editor.

## Implemented

- World/Lot/Asset mode navigation with a large world viewport and retained Asset
  Creator split view. Existing themes and controls remain shared.
- Seeded editable heightfield island with dimensions/seed, raise/lower/smooth/flatten
  brushes and independent sand/grass material layers. Brush release records one
  shared-history undo step. Height/paint source is saved and reconstructed.
- Independent ocean surface with editable transform/water level. This is flat water,
  not fluid simulation, shoreline effects or connected canal filling.
- Catmull-Rom spline road meshes, sidewalks, center markings, control-point and width
  editing, colliders and surface/friction metadata. No automatic intersection or
  cut/fill solver. Rendered/collidable geometry is not a validated game track.
- Rectangular lots with terrain grading, lot-local grid placement, floor levels, walls, rectangular rooms,
  floors/foundations, gable roofs, real wall apertures and opening frames/windows,
  stairs and original procedural palms. Openings are part of wall source geometry,
  not decorative rectangles covering solid walls. No animated door leaf is claimed.
- Lot/child parent IDs and opening/frame attachment index persist. Whole-lot
  transforms and duplication preserve child placements. Doors/windows update with
  wall regeneration. Wall/road points and height/roof rise are editable in Properties.
- Shared `.wbworld` persistence/undo for construction, scene hierarchy, transforms,
  material groups/base colors/metallic/smoothness and embedded supported textures.
  Original OBJ files are not required to reopen a project.
- Local reusable object/whole-lot library under the app's persistent data directory;
  search and independent-instance placement. Stable library identity is retained.
- OBJ `usemtl` groups, MTL Kd/map_Kd and PNG/JPEG texture import. Missing/unsupported
  references produce explicit warnings. Reimport confirms replacement and preserves
  object ID, transforms and child relationships; undo restores the prior state.
- Recursive OBJ/MTL export of lots and world objects with material groups and texture
  files, source-preserving checks and world-space transforms. glTF/native game export
  remains pending. Source normals/maps other than supported albedo are not implied.
- One-minute recovery snapshot, recovery/last-project buttons and dirty-state prompts.
  Shader references are generated for standalone retention without replacing user
  scenes. A separate explicit Windows x64 build entry point already exists.

## Validation executed

The new engine-independent WorldConstruction/WorldGeometry code compiled with Roslyn
4.11 and ran on .NET 8.0.15 in the cloud. Executable harness passed the geometry
assertions across original test inputs: seeded terrain, terrain operations/painting,
field-source JSON roundtrip, correct road width/sidewalk/marking groups, door clearance,
invalid opening rejection, index/finite-value/nondegenerate checks and all construction
primitives. The JSON harness uses field-only serialization to match the source schema;
it does not substitute for Unity JsonUtility tests.

The same executable also compiled/runs the actual read-only SimsPackage and
GameArchiveDiagnostic/GameArchiveRead classes against original synthetic containers:
zlib inflate/checksum, invalid payload isolation/refusal, ZIP mesh-name discovery,
bounded entry read/CRC verification and encrypted-entry rejection. These are genuine
C# executions, not a reimplementation of the tested classes in Python.

Configuration/asset GUID checks, C# grammar checks and `git diff --check` passed.
Unity-specific tests were added for terrain/submesh persistence, lot parent identity
and OBJ material groups. Existing Unity regressions remain. No Unity engine or Windows
runtime is installed here: Unity compilation/API type-checking, NUnit execution, UI
layout/input/physics/shader rendering and Windows builds remain **unverified**.

## Windows/local acceptance sequence

1. Update the development branch and reopen Unity 6000.6.5f1.
2. Run EditMode tests; fix/report any engine compilation errors before proceeding.
3. Press Play; choose Florida Island Test. Confirm terrain/ocean/road/lot/house/palms.
4. Raise/lower shoreline, paint sand/grass, undo/redo. Save a named world.
5. Select the lot, enter Lot Mode, draw another room and roof; cut door/window openings.
   Confirm holes in the wall geometry, floor/grid behavior and child transforms.
6. Change a road point/width, move the lot and verify its children move with it.
7. Import an original Blender OBJ with MTL/albedo, edit transforms; save/reopen.
8. Stop Play, enter Play again, open the saved `.wbworld`; verify all source parameters,
   geometry, material groups/textures and placements. Save a lot to the asset library
   and place it in a fresh world. Verify recovery snapshot and source reimport/undo.
9. Export OBJ/MTL/textures and reopen in Blender to verify hierarchy-as-named-objects,
   scale, materials, normals and transforms. This does not validate game-native output.
10. Build Windows Release, run the actual executable outside Unity, repeat core steps,
    then distribute the whole build directory. Do not mark the release Complete until
    these steps run successfully.

## Remaining directive requirements

Advanced mesh/UV tools and visual transform gizmos; real-time placement previews and
measurement overlays; docking/layout persistence; richer floor/foundation/roof tools,
angles/alignment/group management; generated textures/full PBR and transparency;
terrain noise/erosion/biomes/streaming; water/canals; road banking/intersections/cut-fill;
large-scene performance baselines; full game environment/furniture import; Blender
linked-instance conflict handling; glTF; validated Assetto Corsa conversion; and
Windows packaging/smoke tests remain independent subsequent milestones. No UI buttons
for these unimplemented operations were added.
