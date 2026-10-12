# Sims-inspired PC build controls

## Research and adaptation

EA Help documents right-click and comma/period rotation in 45-degree increments, left-click placement and Alt mouse rotation:
https://help.ea.com/en/articles/the-sims/the-sims-4/how-to-rotate-sims-4/

EA's official console manual identifies selection/editing tools, floor/top-view controls, search and room/function catalogs. This validates workflow roles, not PC keyboard bindings:
https://eaassets-a.akamaihd.net/eahelp/manuals/the-sims-4-xbox-one-anz.pdf

Historical keyboard mappings were cross-checked against the EA-hosted community build guide. This is community guidance rather than an official current PC specification:
https://forums.ea.com/discussions/the-sims-4-creative-corner-en/building-tips-and-tutorials-ruthless-kk-build-guide-link-too-/810063

World Builder adapts those patterns to its supported independent editing features. G now controls snapping instead of Move; R opens contextual Properties instead of Rotate. Unsupported Sims features (wall cutaway, object slots, household inventory, paint flooding and Live Mode) have no fake mappings.

## Application mappings

Click the editable viewport to focus it. Global save/undo/redo, Escape and catalog function keys are also available outside the viewport, but never while typing or in a modal dialog.

| Input | World Builder action |
| --- | --- |
| Left click | Select, place or construct with the active tool |
| H | Hand: drag to move an object |
| E | Toggle copy picker: click a source, then click to place an independent copy |
| K | Toggle click-delete tool; Undo restores deleted objects |
| R | Open contextual Properties, including materials |
| B | Enter the selected/active lot and choose Wall |
| Comma / period | Rotate selected or pending object by −45 / +45 degrees |
| Right click | Rotate pending placement 45 degrees; otherwise cancel an active construction tool |
| Alt while placing/moving | Temporarily bypass grid snapping; lot boundary checks remain |
| Alt while dragging Rotate | Free yaw rotation; otherwise rotation snaps to 45 degrees |
| Shift while placing a library/copy object | Keep the same placement source and angle for another copy |
| G | Toggle grid snapping; currently no visible grid overlay |
| F5 | Alternate 0.5 m and 0.25 m snapping |
| Brackets | Decrease/increase brush radius by 1 m |
| Page Up / Page Down | Change active lot floor, between 0 and 5 |
| F2 / F3 | Active lot Furnish / Structure catalog; requires a lot |
| F4 | Local library |
| T | Top orthographic view |
| W/A/S/D or arrows | Pan editable camera while viewport has focus |
| Right drag / middle drag | Pan / orbit camera |
| Mouse wheel | Zoom |
| F | Frame selection |
| Enter | Finish the road being drawn |
| Delete | Delete selected object |
| Escape | Cancel tool, uncommitted transform or pending placement |
| Ctrl+S / Ctrl+Z / Ctrl+Y | Save / Undo / Redo |

Differences are intentional: R exposes this app's Properties rather than a dedicated Sims swatch picker; F4 opens a local library rather than the online Gallery; G toggles snapping rather than a visual grid. Wall construction still uses the current two-click workflow. Placement ghost feedback and click-pick-up/drop manipulation remain outstanding usability work.

## Verification

Executed configuration/GUID/input source checks, C# syntax parsing and whitespace checks. No installed Unity runtime is available here: keyboard focus, Alt/Shift modifiers, camera behavior, dialogs and placement must still be exercised locally.

Manual checks: type shortcut letters into Search and confirm they do not edit the scene; focus the viewport and test each mapping. Copy an object, rotate it before placement, Shift-place twice and cancel. Check fresh IDs and one Undo per placed copy. Repeat with a library building and active lot. Confirm G/F5/Alt snapping, floor changes and bracket slider updates. Use K to delete, Undo to restore and right-click/Escape to exit the tool.
