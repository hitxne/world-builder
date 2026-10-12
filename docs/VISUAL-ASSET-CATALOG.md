# Visual building catalog and imported-mesh repair

The imported Sims objects are presented as thumbnail cards, not a text list. World Build > Sims Assets filters the collection; Lot Build > Furnish and Local Library show the reusable asset collection. Search and 12-item pages keep the collection reachable without loading all ~2,300 meshes into the scene.

Cards request genuine rendered mesh thumbnails only as their page is viewed. A separate layer/camera renders each asset, PNGs are cached beside local library files, and detached card textures are released. There are no illustrative stand-ins. Unsupported/failed previews report their limits. Existing resource IDs use compact labels with the full name/provenance in tooltips; actual Sims catalog names and categories still need decoding.

Selecting a card opens a read-only 3D viewer with orbit, pan, zoom, geometry statistics and import warnings. Place in world / active lot arms the existing placement workflow; the actual-model ghost appears in the editable viewport before placement. Preview objects/cameras are isolated from the working scene, picking, saves and exports.

## Reported placement error

An imported mesh with an empty construction object reached procedural regeneration, causing Unknown construction type with a blank kind. WorkspaceProject now distinguishes named construction sources from empty records, normalizes empty records to null on document load and before Model creation, and preserves the stored mesh. Named unknown construction types still produce an error; the repair does not silently accept unsupported procedural data. Existing imported library files do not need re-extraction.

Added Unity regression tests cover legacy empty-construction library save/open preserving triangle geometry and named unknown constructions remaining invalid. Tests have not been executed because Unity is unavailable here. Source configuration/GUID/input checks, C# syntax parsing and whitespace checks passed; native type checking, thumbnail/preview rendering and placement require local verification.

## Local check

Pull with Unity closed, reopen and let resources import. Open Sims Assets or Furnish; thumbnails should populate a page at a time. Inspect an entry in 3D, orbit/zoom, then Place. Confirm the reported blank-type error is gone, Undo restores placement, and changing pages/releases previews does not affect the editable world. In Unity Play Mode, thumbnail generation waits until the end of a rendered Game frame; returning focus to Game View may be necessary if viewing Scene or debugging.

Sims exports currently contain supported geometry only. Missing game textures/materials and unsupported objects remain reported; the UI does not manufacture their appearance. Whole-world chunk streaming and complete Sims Build/Buy catalog assembly remain separate unfinished priorities.
