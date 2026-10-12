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
