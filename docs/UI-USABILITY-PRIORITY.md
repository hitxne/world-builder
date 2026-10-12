# UI design and usability — blocking priority

This user-directed priority supersedes the feature-first continuation order in earlier milestone notes. Preserve the original mission and existing features. Focus development on making those features understandable, discoverable and practical to use. New construction features, deeper format support and target-game exporters wait until the core workflow passes this gate. Fixes necessary to enable or protect that workflow remain in scope.

## Product workflow

World Build: create terrain → shape/paint → draw roads → define lots → place scenery.

Lot Build: select a lot → build rooms/walls → add openings/roof/stairs → place furnishings → return to the same world.

Asset Studio: inspect/import → edit → save to library → place in world or lot. Routine world building must not require opening the modeling workspace.

Use Forza-inspired world-space placement and Sims-inspired contextual building categories. Keep a large working viewport. Show the next relevant action rather than every setting at once. Preserve independent functioning and read-only game sources.

## Required usability work, in order

1. **Navigation and layout.** Audit the running Unity UI, not only its source. Establish a coherent hierarchy for workspace modes, catalog categories and contextual properties. Eliminate overlaps, clipping, unnecessary scrolling and inaccessible actions. Make a return route and default-layout restore visible.
2. **Tool discoverability and state.** Show active mode, selected object/lot, active tool, floor and snapping. Use plain labels, meaningful disabled explanations and accurate tooltips. Separate selection/manipulation actions from construction choices. Provide a consistent cancel/finish interaction.
3. **Immediate spatial feedback.** Add visible selection feedback and appropriate placement/drawing previews so users can see what a click or drag will produce. Numeric properties supplement direct interaction. Keep preview state separate from committed project data; Escape must leave no accidental object behind.
4. **Catalog usability.** Make supported assets visually identifiable with genuine previews/thumbnails where available, useful categories and search. Show compatibility before import. Unsupported resources must not resemble usable catalog entries. Avoid technical diagnostics as the ordinary user flow.
5. **Task-based validation.** Execute the scenarios below in Unity and the Windows player, fix observed friction, then repeat affected scenarios. Source checks alone cannot pass this gate.

## Acceptance gate

A first-time user must be able to complete these tasks using visible UI labels and feedback, without C# editing, Unity internal panels or conversational instructions:

| Task | Required observable result |
| --- | --- |
| Start a project | Find New/Open and a clear first action; create an island. |
| Shape the world | Find a brush, see its mode/settings, sculpt/paint, cancel and undo. |
| Build roads | Identify start/add-point/finish states before committing a road. |
| Enter a lot | Select/create a lot, enter Lot Build and identify the active lot/floor. |
| Construct a room | Understand placement feedback, commit walls/openings/roof and return to World Build. |
| Place an asset | Find an asset, inspect compatibility, choose a location, cancel or commit and manipulate it. |
| Recover from a mistake | Find Undo/Redo, cancel a tool and restore layout without losing committed work. |
| Continue later | Find Save/Open, understand save status and reopen the same editable scene. |

Check 1280×720 and 1920×1080, a narrow window, applicable Windows DPI scaling, all three themes, mouse/keyboard focus and dialogs. No label or action may overlap another control or disappear outside a reachable scroll area. Critical actions must stay identifiable; saving and cancellation must remain accessible.

Do not assign an invented usability score or report a task as passed without executing it. Record task, environment, observed issue, fix and retest result. The present status is **In progress; runtime usability unverified**.

## Definition of done

A feature counts toward the operational milestone only when the user can sensibly find and use it in the real application, feedback matches its actual effect, cancellation/undo work, errors are recoverable and verification is recorded. Update the canonical UI/theme/input systems; avoid accumulating permanent layout overrides or decorative controls.

The immediate next implementation increment is selection and placement/drawing feedback, alongside repairing any navigation defects found in the running UI. Do not expand the feature catalog to compensate for an unusable interface.
