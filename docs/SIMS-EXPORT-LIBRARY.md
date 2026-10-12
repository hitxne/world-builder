# Local Sims Build/Buy export collection

Goal: make the user's locally available Build/Buy objects browsable and placeable in World Builder. The imported catalog is stored under the application's persistent Assets directory, not committed to the public repository.

Research found Sims 4 Studio mesh export discussions describing .blend output, which requires a Blender OBJ/MTL conversion for the current importer. Source:
https://sims4studio.com/thread/35008/solved-export-mesh

Do not claim verified batch export of every Build/Buy item. Neither full installed-catalog enumeration nor an all-object export API has been validated. Objects may contain separate LODs, swatches and special material systems. Walls/floors/roofs and other procedural game build features are not necessarily individual OBJ objects. OBJ geometry does not reproduce Sims game behaviors or automatic wall apertures.

## Implemented import path

Open Local Asset Library > Import Sims export folder. Select/paste an export directory containing OBJ files with MTL and supported PNG/JPEG textures. Subdirectories are scanned. In Unity, use the native folder chooser; the current Windows player offers selection of an OBJ whose containing folder becomes the import root, or direct entry of the root path.

Import creates one reusable library asset per OBJ, preserving supported geometry/material/texture data and the exported source path. Deterministic IDs skip already imported source paths; changed versions use the existing reimport workflow, not silent replacement. Original files are untouched. Missing/unsupported materials remain explicit warnings in metadata and Sims-import-report.txt; failed files do not stop other imports. Cancellation keeps completed imports. No entire collection is placed into the editable world automatically.

Library name search works across pages with 50 visible entries each. Metadata sidecars avoid repeatedly decoding embedded meshes/textures for imported entries. Legacy library entries without sidecars still require document reads. Folder scan is background work; Unity mesh/material parsing occurs on its main thread and yields between files. A single complex import can still pause the UI; further background parsing and thumbnail catalog work are outstanding.

Limits: 32 MiB per OBJ and 100,000 discovered files per batch. Only owned/authorized local content should be exported or redistributed to other target games, consistent with the master directive. No game assets were accessed in this cloud environment.

Validation performed: source configuration/GUID/input checks, C# syntax parsing and whitespace checks. No real Sims exports, Unity ingestion or Windows library persistence test has run here.

Next required validation: select a representative exported object with textures, bulk-import its folder, inspect warnings and place it in a lot. Cancel/resume a multi-file batch and confirm completed files are skipped; search for an entry beyond the first 200, restart and place again. Full Build/Buy coverage needs a verified local export inventory, with categories, LODs/swatches, actual thumbnails and capability reporting before being marked complete.
