# Using the editing workspace

Development branch: `development/world-builder-operational`. Unity target: `6000.6.5f1`.

Open the project in Unity and press Play. The runtime creates the workspace in an
empty scene; it also works in the existing starter scene. Ordinary edits now take
place in the Game view rather than Unity's Inspector.

1. Add a Plane as ground and Cube/Sphere/Cylinder objects from the left sidebar.
2. Select an object in the hierarchy or left-click its surface in the editable view.
3. Enter Position, Rotation (degrees) and Scale in Properties. Press Enter or leave
   a field to commit. Choose one of the base-color swatches.
4. Right-drag to orbit, middle-drag to pan, wheel to zoom. Frame Selected/All centers
   the camera. The projection button toggles perspective/orthographic.
5. Duplicate/Delete, Undo/Redo operate on scene edits. History retains up to 20
   snapshots within a 32 MB history budget; very large edits can evict history early.
6. Import OBJ adds an independent editable object and shows its reference copy.
7. Save writes `.wbworld` with all active meshes, IDs, transforms and base colors.
   Open reconstructs the scene without the original OBJ. Old `.wbasset` files can
   be opened using the file dialog's All files filter.
8. Export writes world-space OBJ and a companion MTL with base colors for Blender.
   Keep both files together. This is general interchange, not a game track export.
9. New/Open/standalone Quit prompt before discarding dirty work. Save As creates a
   new project. Unity's Stop button ends runtime editing: save `.wbworld` first.
10. To run outside Unity, use World Builder > Build Windows Release. Ship the entire
    Builds/Windows directory. The build generates a separate bootstrap scene and
    does not replace the user's AssetCreator scene.

## Game asset previews — current capability
The browser keeps existing Sims/Forza installation preferences and scans folders
in a background task. Loose OBJ files have real reference previews. Sims `.package`
files are listed with an explicit unavailable-preview status. The installed Sims
objects inside those packages cannot currently be viewed. Forza proprietary model
resources cannot currently be viewed either. Installation detection is not mesh
support. An authorized external OBJ export can be imported and edited; source
MTL textures are not yet supported. No game files are modified.

Direct game viewing remains blocked on implementing and testing a documented mesh,
material and texture adapter against actual game resources. Do not report this
milestone as completing that request. Next priority is a Sims object-preview
pipeline, then verified Forza capabilities; no game asset dumps belong in Git.

## Validation status
Implemented: UI Toolkit runtime shell, centralized dark/light/high-contrast USS
palette, object hierarchy and picking, numeric transforms, primitives, duplicate/
delete, snapshot undo/redo, multi-object persistence, base-color assignment, OBJ/MTL
export, responsive dual viewports and asynchronous file discovery.

Executed in cloud: source/configuration validator, C# grammar parsing and whitespace
checks. Unity APIs were not type-checked, Unity tests were not executed and no Windows
player was built here. User previously reported the preceding foundation opens
successfully in their editor; this new workspace still needs local validation.

Added EditMode cases: multiple-object/identity persistence, history branching,
exported transform round-trip. Existing OBJ/project regression cases remain.

Remaining: visual transform gizmos, textured OBJ/MTL import, mesh editing, docking,
terrain sculpting/island generation, water, splines, architectural tools, persistent
asset library, direct proprietary game previews and validated game export.
