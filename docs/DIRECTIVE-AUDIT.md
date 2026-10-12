# Master directive audit — 2026-10-12

Reviewed the full 1,529-line WORLD BUILDER MASTER ENGINEERING & IMPLEMENTATION DIRECTIVE supplied as Pasted text(20261012-144703).txt, including its final acceptance scenario. This supersedes older milestone notes where they describe an earlier repository state. The independent world/lot editor and preserved Asset Creator are the product; game package diagnostics are supporting integrations.

## Compliance and acceptance

| Directive sections | Status | Source evidence / remaining gap |
| --- | --- | --- |
| 1–2: platform, branch, canonical systems, source preservation | In progress | Unity target 6000.6.5f1, development branch and shared theme/history/document/geometry services. No installed-game writes or commercial assets included. Unity compatibility is not verified. Large runtime partials still need modular service boundaries. |
| 3: operational application | In progress | Import, editing, native saves, terrain/road/building source and export exist. No verified Windows executable or end-to-end acceptance run. |
| 4–5: architecture, input, bootstrap/render setup | Implemented, untested | New input boundary, isolated cameras, bootstrap/build scene. Unity APIs, shaders/package compatibility and clean checkout startup need Unity execution. |
| 6: desktop UI/themes | In progress | UI Toolkit, shared three-theme tokens and bottom catalog. This update adds persistent panel sizing/visibility, restore, responsive drawers, hierarchy search, tooltips and camera presets. Free docking, drag/drop, contextual menus and configurable shortcuts remain pending. |
| 7: game asset browser | In progress | Paths, scanners, subset adapters/capability reporting exist. Synthetic container code is tested; real installed-game mesh/material/texture coverage and unified metadata/thumbnail catalog are unverified/incomplete. |
| 8: Asset Creator | In progress | Isolated split views, selection, numeric transforms, primitives, duplicate/delete, OBJ/MTL import/export/reimport. Gizmos, modeling tools, grouping, linked instance conflict previews, glTF and complete axis/unit controls remain pending. |
| 9: materials | In progress | Shared starter palette, base color, metallic/smoothness, supported albedo and terrain paint. Full PBR maps, UV controls and optimization tools remain pending. |
| 10: library | In progress | Local reusable object/lot files, stable IDs, search and independent placement. Thumbnail catalog, tags/favorites, source filters and drag placement remain pending. |
| 11: world | In progress | Editable seeded heightfield, sculpt/paint, independent flat ocean and palms. Rich generation parameters, biomes/scatter, canals/connectivity and streaming remain pending. |
| 12: roads | In progress | Editable spline control points/width, sidewalks/markings, collider and surface metadata. Directional lane counts/turning lanes, intersections, banking, terrain cut/fill and validated driving remain pending. |
| 13: buildings | In progress | Lot-local walls, rectangular rooms, floors/foundations, roof, apertures/frames and stairs. Curved walls, ceilings, railings, advanced alignment and starter architecture catalog remain pending. |
| 14: productivity | In progress | Shared history, hierarchy/parent IDs, search, selected emphasis, numeric transforms and focus. Multiselection, collections/layers, lock/visibility, gizmos and context menus remain pending. |
| 15: persistence | In progress | Atomic self-contained .wbworld snapshot, geometry/material/texture/source recipes and parent identity, recovery/last project. Folder-based asset references, migration, complete workspace/project state and recovery integration tests remain pending. |
| 16: export | In progress | OBJ/MTL and supported textures. No validated Assetto Corsa native track, GTA V or CarX exporter; generic export does not meet those targets. |
| 17–18: graphics/performance | In progress | Sun, original geometry/materials and viewport resources. Realism, sky/time/fog/quality controls, optimization and measured Windows baselines remain pending. |
| 19: Windows release | Implemented, untested | Release/development build scripts and companion-files ZIP packaging. Windows/Unity execution and release artifact are unavailable here. |
| 20–22: testing/phases/done | In progress | Earlier actual .NET geometry/container harness executed; Unity NUnit sources exist. No phase is accepted merely on source presence. Current UI is implemented, untested in Unity. |
| 23–24: repository/reporting | In progress | Reviewable development increments, README/audit and truthful test limits. Main remains unmerged; draft PR #1. |
| 25: Florida Island Test acceptance | Implemented, untested | Source workflow exists for island/brushes/road/building/import/transforms/save/reopen/export. Independent Windows launch and full scenario remain unverified. |
| 26: execution | In progress | Actual source changes committed; continuation below. This is not a World Builder 1.0 acceptance claim. |

## Defects corrected in this update

- Category changes now cancel the previous construction tool, preventing a hidden tool from continuing to affect the scene. Explicit Cancel Tool is accessible alongside Escape.
- Cancelling a sculpt stroke records its already-applied edits through shared history rather than dropping the undo step.
- Panel sizes/visibility persist via one layout boundary. Restore Default Layout is available. Narrow windows expose panels as temporary drawers rather than leaving the inspector inaccessible.
- Catalog height adapts to window height, retaining viewport space. Long content remains scrollable.
- Search filters the scene hierarchy by name and parent depth is visible. Camera presets expose orthographic Top/Front/Side.
- Empty worlds initially show Create World. README now matches the relocated starter action.
- Repeated stylesheet selectors were consolidated rather than layering additional permanent overrides. All surfaces use canonical theme variables.

## Verification for this increment

Executed: tools/validate-source.py, C# tree-sitter syntax parsing of all Assets scripts, git diff --check, and local/remote committed-tree comparison after push. Syntax parsing is not C# type checking. No Unity build, runtime layout/input/physics check, NUnit run or Windows player smoke test was executed. Existing .NET test results describe earlier geometry/container work; they do not validate this UI increment.

## Remaining acceptance run and continuation

In Unity 6000.6.5f1: EditMode > Run All. Play at 1280x720 and 1920x1080, then narrow the window: check catalog scrolling, hierarchy search, Scene/Properties drawers, saved sizes and restore. Switch every category while a construction tool is active: the active tool must return to Select. Sculpt, Escape, Undo, Redo. Verify Top/Front/Side. Run the full section 25 Florida Island Test scenario, including textured import and save/reopen/export.

Build via World Builder > Build Windows Development; launch the packaged executable outside Unity and repeat the core scenario. Resolve actual compilation/render/input defects before accepting any operational milestone. Next independent engineering priorities are gizmo-based object manipulation and an asynchronous searchable asset catalog with real preview capability metadata; realistic lane/intersection construction and Assetto Corsa preparation follow the stable core.

## Follow-up audit: direct editing and library placement

Sections 8.2, 10 and 14 still lacked direct manipulation despite numeric transforms. Library selection also placed every asset at the origin, contrary to the intended choose-and-place workflow. This increment adds actual viewport drag transforms and click placement, integrated with the existing document/history/lot parent boundary.

Transform controls are planar Move, local-yaw Rotate and uniform Scale, not full three-axis gizmos. Clicking a child of an already selected building moves that building as a unit. Lot movement checks object origins, not full mesh bounds. Library placement uses each asset's existing pivot; it does not automatically lower bounding boxes onto the ground or display a ghost preview. Asset Studio placement returns to World Build; lot placement retains the active lot.

Category/tool changes cancel uncommitted transforms. Invalid library IDs, root counts and cycles are rejected in staging before scene insertion. Two EditMode tests exercise cancel with child transforms and commit with document-history undo/redo; no Unity runtime is available to execute them here.

Additional manual checks: choose a saved building, cancel placement (no new object), select it again and click terrain (one copy at the chosen point). Place furniture inside a lot. Drag Move/Rotate/Scale, release, Undo/Redo, then drag and Escape (original transform restored). Try Rotate/Scale in Front view and Move in Top view. Change category during a gesture and verify cancellation. These checks remain pending; production gizmos and thumbnails remain unfinished.
