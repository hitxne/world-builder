# World Builder

Independent Windows-first world and lot construction application in Unity.
Target editor: **6000.6.5f1**. Work is on `development/world-builder-operational`;
[PR #1](https://github.com/hitxne/world-builder/pull/1) remains draft while native
Unity/Windows validation is incomplete.

## Core priorities: usability and large-map scalability

Make the existing world/lot workflow understandable and usable before expanding
features. A feature is not accepted merely because its code exists: users must be
able to find it, understand its state, perform the action and recover from mistakes.
See [usability priority and acceptance gate](docs/UI-USABILITY-PRIORITY.md).
Large-map scalability is a parallel architectural requirement: terrain chunks,
streamed detail, shared assets, precision and incremental persistence must support
the intended huge map. See [large-world priority](docs/LARGE-WORLD-PRIORITY.md).
The current small-scene prototype is not yet suitable for a huge production map.

## Use the world/lot workflow

1. Open this project in Unity 6000.6.5f1 and press Play.
2. Choose **World Build > Create World > Florida Island Test** to create an original island, ocean,
   neighborhood road, editable lot, house and palms. Or Generate Island with your
   own dimensions/seed and build from an empty world.
3. Sculpt terrain with Raise/Lower/Smooth/Flatten, and paint Sand/Grass.
4. Draw Road: click control points on terrain, then Finish Road or Enter. Width,
   sidewalks and control points remain editable in Properties.
5. Draw Lot: click two corners. Select the lot and enter Lot Mode.
6. Draw Room/Wall/Floor/Roof with two clicks. Door/Window tools cut real openings
   in existing walls. Place Stairs, choose floor level and edit dimensions/transforms.
7. Save `.wbworld` inside the app **before stopping Play**. Reopen it to continue;
   Unity's saved editor scene does not contain runtime edits.
8. Save a selected object or whole lot to Local Asset Library for reuse in another
   project. Import/Reimport OBJ with supported MTL/PNG/JPEG textures; export the
   world or edited assets as OBJ/MTL with texture files.

World, Lot and Asset modes use the same authoritative scene, hierarchy, materials,
selection, snapshot history and project serialization. Lots actually parent their
walls/floors/frames, so moving a lot moves its building. Construction source data
(heightfield, paint layers, splines and openings) persists alongside generated meshes.

## Windows application build

Use **World Builder > Build Windows Release** in Unity with Windows x64 Build
Support installed. Output: `Builds/Windows/WorldBuilder.exe` and required companion
files. The build also packages the whole directory in a timestamped ZIP under Builds. A Development build menu is available for debugging. The build creates a separate bootstrap
scene and generated shader resources; it does not overwrite the saved user scene.
A Windows build has not been produced or smoke-tested in this cloud environment.

## Verification

The engine-independent C# geometry/container code compiled and its executable tests
passed in cloud (.NET 8). Tested: deterministic islands, raise/flatten/paint, source
round-trip, road width/sidewalks/markings, real wall apertures, nondegenerate geometry,
zlib resources and bounded ZIP read/CRC/encryption rejection. Configuration/GUID,
C# grammar and whitespace checks also passed. Unity EditMode tests are included but
have not run here; UI, physics, materials and the Windows player need local testing.

```powershell
dotnet run --project tools/world-geometry-tests/WorldGeometryTests.csproj
```

In Unity, run **Window > General > Test Runner > EditMode > Run All**. See
[world/lot acceptance and release status](docs/WORLD-LOT-MILESTONE.md).

## Current limits

This is a functional source increment, not a verified World Builder 1.0 release.
Water is an independent flat surface, not a validated ocean/connected canal simulator.
Roads have mesh collisions and editable splines, but automatic cut/fill, intersections
and driving-game validation are pending. Windows execution, advanced modeling/gizmos,
large-world streaming, full PBR material editing and game-native export remain pending.

Game adapters are read-only subsets: plain Forza mesh parts/ordinary ZIP entries and
some Sims MLOD layouts. Full textured environment-asset browsing/import, MiniZip,
cross-package Sims dependencies and unsupported game encodings remain incomplete.
No game renderer, proprietary assets, encrypted-archive decryption or game source
files are included. See [game adapter status](docs/GAME-ASSET-ADAPTERS.md).

Primary eventual game export: original Assetto Corsa (2014); GTA V second;
CarX Street experimental. Generic OBJ export is not a complete Assetto Corsa track.

Workspace controls: **Layout** resizes panels and restores defaults. **Scene** and
**Properties** toggle panels; narrow windows open them as temporary drawers.
Hierarchy **Search** filters names. Catalog category changes cancel the previous
tool; **Cancel Tool** and Escape are available. Camera offers Top/Front/Side views.
See [directive audit](docs/DIRECTIVE-AUDIT.md) for current acceptance status.

Direct editing: choose **Move**, **Rotate** or **Scale** in the catalog and drag
an object in the viewport. Move snaps to the grid on a horizontal plane; Rotate
changes local yaw; Scale is uniform. Release commits one undo step; Escape
restores the starting transform. With the viewport focused, H selects Hand/Move. See Controls for the Sims-inspired mappings.
Select a library asset, then click terrain or the active lot to place it; Escape
cancels before creating anything. These controls still need Unity runtime validation.

Terrain brushes now expose radius and strength sliders with numeric values.
Terrain-following roads, sidewalks, markings and colliders update after sculpting
and share the stroke undo step. Turn off **Follow terrain** in road Properties for
elevated roads. This is surface conformance, not an intersection or cut/fill solver.

See [PC build controls](docs/SIMS-BUILD-CONTROLS.md). The top-bar **Controls**
button displays the mappings inside the application. Shortcuts act in the focused
editable viewport; typing in input fields and using dialogs remains separate.

**Local Library > Import Sims export folder** imports an exported OBJ collection
recursively, with supported MTL/PNG/JPEG references, cancellation, duplicate
skipping and an import report. The library now pages through matching entries
instead of stopping after the first 200. This is an external-export import path,
not complete direct extraction of the installed Sims Build/Buy catalog.

A [local package-to-OBJ batch exporter](tools/sims-export/README.md) is now
available without Unity. It exports supported MLOD geometry and reports missing
coverage. It does not yet export every Build/Buy item or reproduce game materials.

**Add Sims Assets** is the normal one-step game import: select the Sims 4 EXE.
World Builder finds the installation and runs supported extraction/library import
automatically. This flow and real game coverage still need Unity/Windows testing;
textures and complete catalog support remain incomplete.
