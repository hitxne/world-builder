# Operational foundation increment — 2026-10-12

Base: `526fde3`, development branch: `development/world-builder-operational`.

## Audit
The repository contained one runtime script, one scene-generation editor script,
package manifest, editor-version record, README and ignore rules. There was no
committed scene, test suite, render-pipeline asset, project format or Windows build.
The two cameras shared scene geometry; OBJ relative indices were cached incorrectly;
legacy input was incompatible with new-input-only configurations. Browser scanning
is still bounded but synchronous. IMGUI is still the prototype shell.

## Implemented, untested in Unity
- Central modern mouse input boundary; safe absent-device/unfocused handling.
- Pointer capture starts only inside a viewport. Browser blocks camera interaction.
- Independent layer masks for reference/edit panes. A zero-culling display camera
  presents the GUI without drawing world geometry again. Single workspace light.
- Runtime bootstrap when a loaded scene has no application component.
- Windows Unicode open/save dialogs and editor dialogs; cancelling leaves work alone.
- Separate OBJ parser: face-relative indices, inline comments, bounds checks,
  non-finite coordinate rejection, empty-model rejection and missing-normal fallback.
- One-mesh `.wbasset` project persistence stores geometry, UVs, normals and transforms,
  with atomic manifest replacement and previous-save backup. Reopening does not need
  the imported source file. This is an interim asset format, not the world format.
- EditMode regression tests and explicit Windows x64 build entry point.
- Stable metadata added for source assets that previously lacked `.meta` files.

## Verification actually executed here
`python3 tools/validate-source.py` and `git diff --check`.
No Unity editor, C# compiler, Windows runtime or game installation is available.
Unity compilation, package resolution, EditMode tests, graphics and file dialogs
have NOT been executed. Phase 0 exit condition is therefore still pending.

The recorded `6000.0.35f1` editor and HDRP `17.0.3` remain unchanged: no installed
`6000.6.5f1` exists here to validate migration. No HDRP pipeline asset is configured
in the repository. Shader resolution and rendering require local verification.

## Windows validation
Run from PowerShell with the actual installed Unity executable:

```powershell
$unity = 'C:\Program Files\Unity\Hub\Editor\6000.6.5f1\Editor\Unity.exe'
$project = 'G:\Documents\Unity Projects\world-builder'
& $unity -batchmode -nographics -projectPath $project -runTests -testPlatform EditMode -testResults "$project\test-results.xml" -logFile "$project\test.log"
& $unity -batchmode -quit -projectPath $project -executeMethod WorldBuilderBuild.WindowsRelease -logFile "$project\build.log"
```

Use the installed editor version if that path differs. Review test XML and logs;
a process exit alone is not evidence of passing tests. Build generates the starter
scene; save existing scene work first. Windows Build Support is required. Package
all of `Builds/Windows`, not just the executable. Do not commit runtime game assets.

Smoke test: launch; import an OBJ; cancel/reopen the native picker; orbit both panes;
verify isolation; open browser and confirm camera input stops; save `.wbasset`;
rename source OBJ; reopen project; verify geometry persists; overwrite save and
check `.bak`; resize; exit. Inspect HDRP materials and the display warning locally.

## Next implementation priorities
1. Run Unity tests and Windows smoke tests; validate target-editor/HDRP migration.
2. Replace IMGUI with UI Toolkit and canonical themes; project dirty-state/recovery,
   hierarchy, selection, numeric transforms and command-based undo/redo.
3. OBJ/MTL textures, export and Blender round-trip; importer memory limits and resource
   lifecycle management. Current imports retain prototype geometry-only semantics.
4. Async game catalog with cancellation and explicit capabilities; native folder picker.
5. Multi-object world manifest, asset identity/library, terrain, water, roads and buildings.
6. Assetto Corsa preparation and validator, then actual game validation.

No full operational application, proprietary asset decoding or game export is claimed.
