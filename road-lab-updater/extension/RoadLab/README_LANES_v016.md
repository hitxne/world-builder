# RoadLab 0.16 — lane marking integration

Install RoadLab_Addon_v0160.zip using Blender Preferences > Add-ons > Install from Disk. Enable RoadLab. Open RoadLab_Lane_Demo.blend, which has its road selected in Edit Mode. Press T if the left toolbar is hidden; select the Lanes icon (three marked lanes).

## Lane workflow

- In road Edit Mode, activate the Lanes toolbar tool.
- Shift-click adjacent points to collect a street section, then click to open the lane window. Existing multi-point selections can be used directly. Select a junction vertex alone to open its connected approaches.
- The window identifies the junction type and lists its actual connected approach headings. Choose an approach to load its committed lane assignment. Changes to another approach are applied separately.
- Lane rows run from the driver's left to right. Incoming travels along the selected section's source direction, or from a chosen junction arm toward the junction. Reverse approach swaps incoming/outgoing travel direction.
- Expand Road size, Incoming lanes, Outgoing lanes or Markings as needed. The sections start collapsed. Road width remains directly editable; additional width stays shoulder space. Lane lists scroll, and Remove lane deletes the selected row.
- Add/remove incoming or outgoing rows (up to seven in each direction), choose permitted movement symbols, adjust lane widths, median allowance and arrow spacing, then press OK.
- If the lanes exceed the current road width, the separate Expand road & apply action must be approved. Without approval, the road and committed lane assignment stay unchanged.
- Use Remove markings to clear the current section/approach assignment.
- Change driving side only in RoadLab > Settings. The entire map's assigned markings regenerate.

Road markings use the packaged SVG-derived textures, not text-font arrows. Arrow shafts stay centered in their lanes, including asymmetric turn symbols. Incoming/outgoing markings face their respective travel directions. Solid edges, broken lane dividers and opposing-direction yellow lines are generated with the lane configuration. Junction openings are left clear. Surface projection follows the generated road mesh, bank and sculpt elevations. Edited road geometry triggers regeneration through the existing deferred update scheduler.

The demo video shows three actual Blender 5.1 rendered states: left + through lanes, lane 2 changed to right turn, and a global driving-side change. It is a rendered demonstration, not a live mouse recording or performance benchmark.

## Current limits

The lane window and toolbar were registered and activated in Blender 5.1. The popup was invoked in an actual Blender GUI and captured with collapsed and expanded sections. Full manual interaction on your desktop remains a useful final check. The current editor handles POLY roads and existing source vertices. For an ambiguous branching multi-selection, select the junction alone. Section bindings use persistent point IDs; topology changes that break a binding require reselection. Separate coincident spline identities are supported as junction approaches, but a section spanning those identities needs editing per approach.

This release adds lane markings, not a traffic simulator. Junction connector routing, receiving-lane validation across an entire network, detailed turn-pocket tapers, bicycle/HOV facility controls and jurisdiction-specific control placement remain further integration work. The remaining decal assets (stop/yield marks, crosswalks, bicycle symbols and words) are packaged for those future controls; they are not automatically placed on every road. Conservative clearances may leave a larger paint-free area than the final junction design will need. Road material preview/render is required to see texture alpha accurately; Solid mode is insufficient.

Traffic-light timing, signal phases and coordinated junction logic remain notes only. No controller was implemented.
