# World Builder

A Windows-first, game-feeling, standalone map and asset creation tool. The first milestone is **Asset Creator**: a dual-viewport reference / editable-workspace application with Blender OBJ importing. Longer term: Sims-inspired parametric Building Mode; Forza-inspired roads, terrain, water, and foliage; portable export targeting original Assetto Corsa (2014) first, GTA V second, and CarX Street as research.

## Status

**Early source prototype — not a downloadable Windows build.** Unity 6 project skeleton; no game-engine port, no Sims/Forza asset extraction, no finished map exporter.

## Quick start (developer)

1. Install Unity Hub and **Unity 6** with Windows build support. Open this folder as a project in Unity.
2. Install the High Definition Render Pipeline package if Unity prompts you to resolve packages.
3. Open any empty scene and choose **World Builder > Create Starter Scene** from the Unity editor menu.
4. Press Play. The runtime Asset Creator UI should open.
5. Use **Import OBJ** to select a local Blender-exported `.obj` file (geometry, UVs, and normals only in this first prototype; MTL/textures are next). The Unity Editor has an OBJ file picker. Standalone builds currently require the `WORLD_BUILDER_OBJ_PATH` environment variable; a native Windows file picker is planned.
6. Orbit either viewport with left-drag, zoom with the scroll wheel.
7. Native Windows builds must be built and tested on a Windows machine with Unity installed.

## Key design requirements

- The custom World Builder project is the authoritative editable data source, not a Forza or Sims engine file.
- Asset Creator is permanent; Blender OBJ/MTL import → adjust → library → reimport/export is a central workflow.
- Reference pane and edit pane are visually separate. Installed Forza/Sims resources are only indexed through supported, read-only adapters and are **not automatically extractable or reusable**.
- Preserve original user-supplied mesh source and asset IDs; optimize generated runtime geometry separately.
- Allow categorized materials, surface painting, assembly, LODs, and OBJ/MTL or glTF exports in subsequent iterations.
- Target games: original Assetto Corsa first, GTA V second, CarX Street experimental. OBJ alone is not a complete drivable-map export.

## Current implementation boundaries

The prototype includes a two-camera viewport, camera orbit, a runtime OBJ geometry reader and persistence of the last selected local source path, plus directory-probe foundations. The full procedural 3D building systems, original game-resource decoders, texture-brush painting, high-quality baking, production asset library, signed updates, and game exporters are **planned but not yet implemented**.

Do not commit copyrighted game assets, extracted packages, or imported commercial models to this repository. The Blender folder contains our own generated demonstration scenes; commercial TrackTools nodes remain external dependencies.

## TrackTools + WB Geometry Nodes expansion

On the `BLENDER` branch, [Blender](Blender/README.md) now provides an additive extension for an existing TrackTools scene. Keep the original terrain plane, road curves and node groups. Install [v0.8.2](Blender/Dist/WB_TrackTools_Additive_v082.zip) for repeatable ordered curb, grass patch and sidewalk layers, with Move Up/Down and independent width, offset, height and enable settings at original road vertices. Editable profile/path curves and crossing-road lowering remain available. The original commercial node library remains external. The v0.6 JSON-world architecture is superseded; remaining legacy features still need native migration.

The 0.8.1 performance repair keeps enabled spans connected and uses fast viewport cleanup with precise rendering/review controls. See the Blender README and performance evidence for measured before/after timings.
