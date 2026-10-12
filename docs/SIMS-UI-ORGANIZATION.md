# Sims-inspired interface organization — 2026-10-12

## Research

EA's official Build Mode manual separates search, construction, objects by room/function, library and object-editing tools. It describes categories for exterior architecture and room/function-based browsing for furnishing:
https://eaassets-a.akamaihd.net/eahelp/manuals/the-sims-4-xbox-one-anz.pdf

EA Help describes entering the options menu, then categorized Game Options, with graphics and Other settings distinct from the building interface:
https://help.ea.com/en/articles/the-sims/the-sims-4/system-requirements/

This implements the organizational principles in World Builder's independent workflows. It is not a pixel-identical copy or a claim of full Sims functionality. An attempted linked settings screenshot was inaccessible; settings structure is grounded in EA's text/manual rather than claimed screenshot inspection.

## Current flow

| Context | Visible choices | Action flow |
| --- | --- | --- |
| Empty project | Create island / Open project | Start card → size setup → editable world |
| World | Terrain / Roads / Lots / Objects | Category → tool or asset → viewport action |
| Lot | Build / Doors & Windows / Floors & Stairs / Buy objects | Active lot → category → construction or placement |
| Assets | Import / Primitives / Library | Source/reference + editable view → model action |
| Buy objects / Library | Actual thumbnail cards, search, all/by-room/by-type filters, pages | Card → read-only 3D inspection → Place |
| Menu | Project / Asset library / Add Sims assets / Settings / Advanced tools | Choose task group before secondary actions |
| Settings | Appearance / Workspace / Editing / Graphics / Controls | Category navigation → relevant settings only |

Visible project bar is Menu, Save, Undo and Redo. Editing toolbar remains consistent for Select, Move, Rotate, Copy and Delete; asset mode also exposes Scale. Properties and view controls remain available without filling the screen with advanced panels. Side panels collapse once for the new minimal layout; saved panel widths are preserved. Cancel is contextual, and detailed settings move out of the ordinary tool catalog. The active mode/category breadcrumb and one action/status line replace repeated paragraphs of instructions.

Lot mode is unavailable until a selected/active lot exists. Selecting a descendant now resolves its ancestor lot, not only an immediate parent. Imported object preview and placement remain isolated from project data.

## Categories and settings are functional

Room/type labels belong to local library metadata; no room/type is inferred from unnamed MLOD resource IDs. Organize asset assigns a readable name, room and type; filters then use those assignments. Original paths/warnings and meshes are preserved. A newly imported catalog is therefore Unclassified until metadata is assigned or actual game catalog decoding is implemented.

Appearance uses the canonical three themes and persisted UI scale. Workspace controls panel visibility/layout. Editing exposes snapping/grid/wall height. Graphics uses the configured Unity quality levels, not invented graphical capability switches. Controls documents the actual supported bindings. The schema does not add nonfunctional audio, household, cheat, inventory or Live Mode options.

## Verification

Configuration/GUID/input checks, C# syntax parsing and whitespace checks executed. Unity API compilation, DPI/layout checks, thumbnail rendering, input/interaction testing, setting persistence and Windows acceptance remain pending. No extra geometry harness run was needed for this UI-only increment.

Manual acceptance: start empty, create/open a world, find each World category, create/select a lot, enter Lot, build and furnish, inspect an asset in the separate Assets view, return without losing the scene, change an appearance/editing setting and reopen, categorize a test asset and find it through room/type filtering, and verify Undo/cancel/Save remain reachable. Check the actual UI at small and normal desktop widths before claiming usability acceptance.
