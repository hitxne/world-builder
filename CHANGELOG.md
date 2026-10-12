# Changelog

## Operational foundation — unreleased
- Modern mouse input, viewport isolation, startup bootstrap and display presentation.
- Windows import/save/open dialogs; independent one-mesh asset-project persistence.
- OBJ index/geometry validation repairs; Unity tests and Windows build entry point.
- Unity compilation and standalone execution pending. See docs/IMPLEMENTATION.md.

## Usable workspace — unreleased
- Replace IMGUI with UI Toolkit, themed controls, hierarchy and object properties.
- Add picking, numeric transforms, primitives, duplication/deletion and undo/redo.
- Save multi-object worlds with stable IDs, embedded geometry and base colors.
- Export transformed scene OBJ + base-color MTL; preserve imported source files.
- Background catalog scans, real loose-OBJ reference previews and clear package limits.
- Build in a separate generated startup scene to preserve saved user scenes.
- Unity/Windows execution pending; direct Sims/Forza asset rendering is not implemented.

## Game preview adapters — unreleased
- Add bounded read-only Sims DBPF resource indexing and limited MLOD geometry decoder.
- Add plain Forza Grub directory inspection and limited per-part mesh decoder.
- Integrate resource selection and neutral geometry previews into the game browser.
- Export metadata-only game diagnostics without uploading installation resources.
- Add original synthetic adapter tests and format-source/license documentation.
- Real game assets, Unity tests and Windows execution remain unverified.

## Diagnostic follow-up — unreleased
- Recognize Sims delta-package deletion/tombstone records without rejecting the index.
- Sample FullBuild/DeltaBuild separately and car/track ZIP groups separately.
- Inspect standard ZIP directories for mesh names, compression and encryption metadata.
- Report MiniZip signatures and unsupported archive formats explicitly.
- Actual metadata guided changes; game-resource payloads and Unity tests remain unverified.

## Selected archive model preview — unreleased
- Browse model names in ordinary ZIP archives and open one bounded entry in memory.
- Enforce stored/deflate method, encryption flags, declared-size limit and CRC.
- Reuse Forza bundle/part-preview UI with in-memory model resources.
- Preserve valid Sims resource indexes while reporting/refusing invalid payloads.
- Diagnostic v3 records exact invalid payload metadata and zero-size placeholders.
- Cloud source checks passed; Unity tests and actual game previews still pending.

## Integrated world/lot workflow — unreleased
- Editable island sculpting/painting, independent water and original palms.
- Spline roads with sidewalks/markings and editable control points.
- Lots, rooms, walls, floors, roofs, door/window apertures and stairs.
- Persistent parametric source, scene parenting, opening attachments and shared undo.
- Reusable local objects/buildings; textured OBJ/MTL import/reimport/export.
- Recovery autosave, last-project opening and standalone shader retention.
- Actual .NET geometry/container execution passed; Unity/Windows validation pending.

## 2026-10-12 — directive audit and workspace usability

- Audit all master-directive sections and document remaining acceptance gaps.
- Persist panel visibility and sizes, restore defaults and use temporary drawers in narrow windows.
- Add hierarchy name search/parent indentation, tooltips and Top/Front/Side camera views.
- Cancel tools when switching catalog categories; retain terrain-stroke undo when cancelling.
- Show Create World for empty scenes and update starter-workflow instructions.
- Consolidate canonical stylesheet declarations.

Validation: source configuration/GUID/input checks, C# syntax parsing and whitespace checks. Unity type checking, graphics/input and Windows acceptance remain unverified.

## 2026-10-12 — direct object editing and library placement

- Add viewport drag Move/Rotate/Scale with grid-snapped planar movement, local yaw and uniform scaling; release records one shared-history step, Escape restores the original transform.
- Add G/R/S shortcuts when the editable viewport has focus.
- Change library selection to click-to-place instead of automatic placement at the origin; preserve lot parenting and independent copies.
- Reject duplicate/rootless/multiple-root/cyclic library documents before scene insertion.
- Add Unity EditMode regression cases for cancelled parent/child transforms and single-step undo/redo of a committed gesture. Tests are added, not executed here.
- Source configuration, syntax and whitespace checks pass; actual Unity/Windows input and rendering remain unverified.

## 2026-10-12 — usability becomes the blocking priority

- Make UI design and usability the next acceptance gate before new feature expansion.
- Define task-based navigation, placement previews, selection/tool feedback and recovery requirements.
- Replace the feature-first continuation order in the directive audit.
- This is a priority/acceptance update; it does not claim the current interface passed usability testing.

## 2026-10-12 — reported Unity compilation corrections

- Rename the camera positioning method to avoid shadowing the UI Toolkit Position enum (CS0119).
- Use explicit float zero for StyleLength pixel values to disambiguate float/StyleKeyword constructors (CS0121).
- Replace deprecated FindFirstObjectByType bootstrap lookup with FindAnyObjectByType (CS0618).
- Source checks passed; Unity compilation must be confirmed in the installed editor.

## 2026-10-12 — terrain brush sliders and road conformance

- Add brush radius/strength sliders with numeric input.
- Project generated road, sidewalk and marking vertices onto terrain and rebuild colliders after height edits in the same history step.
- Persist the Follow terrain road setting; uncovered spans retain generated geometry.
- Add regression cases for raising/lowering between control points, surface offsets and uncovered spans. Unity integration remains unverified.
- Actual C# geometry/container harness passed 41,541 geometry assertions; Unity runtime validation remains pending.

## 2026-10-12 — runtime base theme correction

- Generate/import a runtime TSS inheriting unity-theme://default through the canonical resource preparation service.
- Assign it to PanelSettings before UIDocument initialization; retain Workspace.uss as the shared application theme layer.
- Build resource preparation validates theme import and retains it through Resources in the Windows player.
- Source checks pass; Unity theme import/rendering still needs local verification.

## 2026-10-12 — Sims-inspired PC build controls

- Research EA Help rotation instructions, the official Build Mode manual and historical EA-community keyboard guidance.
- Add H Hand, E copy picker, K click-delete, R Properties, B walls, comma/period 45-degree rotation, Alt off-grid/free rotation, G snapping and F5 half/quarter spacing.
- Add bracket brush radius, floor shortcuts, camera pan/top view, build/furnish/library shortcuts and Shift repeat placement.
- Right-click rotates pending placement or cancels a construction tool; right-drag pans and middle-drag orbits the camera.
- Show a Controls reference and scope shortcuts away from text input/dialogs. Replace the conflicting G/R/S modeling shortcuts.
- Source checks pass; Unity input/runtime validation remains pending. These are adapted controls, not a complete Sims interface clone.
