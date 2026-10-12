# Shared assets and safe source updates

## What changed

World and library document saves now use a version 2 JSON manifest. Mesh arrays, decoded textures and retained source resources live in adjacent, SHA-256-addressed `.blob` files. Equal payloads share files; instance IDs, transforms, catalog metadata and procedural construction remain in the manifest. Procedural meshes rebuild from their construction data. Version 1 inline documents still open and upgrade on their next save.

A saved `example.wbworld` requires its `example.wbworld.assets` directory. Copy and back up both together. Library items share `LibraryResources` beside their manifests; copy that directory with the library. Existing library items convert when saved or upgraded, rather than being silently rewritten all at once.

Payload files are immutable and append-only. A save writes payloads before atomically replacing the manifest, keeping the previous manifest as `.bak`. Old payloads remain available for that backup. No persistent asset garbage collection is implemented. Missing or corrupt payloads stop loading with an error rather than quietly dropping objects. Limits remain: 128 MB manifest, 128 MB per payload, 512 MB unique payload load budget and 2,000 objects. These are safety limits, not huge-map support.

Undo snapshots reference a private session asset cache. Mesh references are memoized by mesh object, so transform edits avoid copying mesh arrays repeatedly. Current mesh editing replaces owned meshes; future in-place vertex editing must invalidate this memoization. Every 20 recorded operations, unreachable session blobs are removed while preserving undo, redo and the saved-state references. Persistent project/library assets are never pruned by this process. History remains bounded to 20 states and 32 MB of manifest strings; this is not delta-command history.

## Local edits survive source updates

Imported assets record source geometry and appearance baselines. Automatic appearance updates compare these before replacing mesh data. Compatible position/normal edits and material color/texture edits are retained. Incompatible edited topology or material slot counts retain the existing mesh and report a manual-remapping conflict. Updated raw source resources remain attached. Instance identity and transforms remain independent of source appearance.

Explicit OBJ reimport retains source provenance and baselines, preventing automatic appearance synchronization from immediately reverting the reimported mesh. Unknown provenance is treated conservatively. Independent UV-only edits are not yet detected by the baseline; do not treat automatic updates as a complete mesh-merge system.

## Construction and navigation

Lot, wall, room, floor and roof tools now drag and release to commit one operation. Releasing outside the viewport or losing pointer capture cancels the preview. Zero-area rectangles do not build. Curved roads retain their control-point workflow. Escape closes a modal first; each modal has an explicit close button. Opening a modal cancels active construction. Autosave waits until active construction/manipulation gestures finish.

## Verification and remaining work

The project-storage test harness executes the actual storage, migration and update source against a test-only serialization/Unity value-type shim. It verifies shared payloads, incremental saves, backup reopening, legacy documents, procedural source rebuilding, reference-based undo/redo, conflict preservation, corrupt payload rejection and path validation. This does **not** verify Unity compilation or Unity JsonUtility behavior.

Native Unity 6000.6.5f1 compilation, mouse/keyboard usability, materials, imported game assets and the Windows standalone acceptance scene remain unverified. Huge-map chunk streaming, GPU resource sharing/instancing, floating origin and production frame/memory budgets remain unfinished. This update addresses persistence duplication and overwrite risk; it does not complete the whole product directive.
