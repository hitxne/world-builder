# Lane editor plan audit — 2026-10-14

Audit sources: lane_logic.py, junction_layout.py, roundabout.py, map_settings.py, current interactive lane preview and research contracts. Status is a plan revision, not implemented multimodal support.

## Critical gaps before Blender lane-editor implementation

1. Typed cross-section: Lane currently stores ID/width/movements only. Need stable lane ID, facility type, permitted users, travel direction, longitudinal extent and explicit destination links. Separate vehicle, bicycle and pedestrian graph layers with conflict links. Vehicle types/steering position are independent of map traffic side.
2. Incoming and outgoing lanes need the same rich model. Preview outgoing width is hardcoded3.5m and exits have count only. Zero-lane directions and one-way/exit-only/entry-only approaches must be possible. Width validation must account for carriageways, shoulders, bike strips, buffers, curbs and medians, distinguishing pavement width from overall corridor width. Proposed cap:7 motor travel lanes per direction, bicycle/path facilities separate; confirm product scope before changing public cap semantics.
3. Bicycle facilities: conventional, painted-buffer, physically separated/raised, two-way separated, contraflow and shared-use paths. Shared-lane markings are a treatment of a motor lane, not an extra bike lane. Lane start/end/mode-transition nodes must not strand cyclists or connect bicycles to car-only facilities. Buffers/separators are explicit strips, never double-counted as rideable width.
4. Bicycle intersections: motor turns crossing bicycle routes, protected corners/setbacks, optional configured mixing zones, bicycle boxes/two-stage turn boxes, bike signal references and clear yielding rules. White symbols, dotted extensions, green conflict paint and NPC links derive from permitted users and real destination facilities. Green paint supplements required striping, not a replacement. Do not add two-stage boxes without the relevant signal/locale conditions.
5. Roundabout cycling: do not generate an ordinary painted bicycle ring inside unsignalized circulation with entry/exit conflicts. MUTCD9E.05 permits separated bicycle facilities. Support explicit upstream transition to shared motor circulation or perimeter separated bicycle path with bicycle crossings; never assume every rider must dismount. Keep pedestrian routes/refuges distinct from cycling paths and apron/island surfaces.
6. Lane transitions: missing explicit mapping for additions/drops, which lane ends, receiving lane, taper location/length, turn-bay deceleration/storage and adjacent transition compatibility. Splits/exits are not ordinary merges. Preserve survivor IDs and user movements through edits.
7. Traffic controls: permitted turn does not mean protected turn. Need junction control type, movement conflict sets, yield/stop nodes and traffic-signal group references. UI must handle grade-separated crossings, skewed5/6-leg layouts and approach bearings; compass templates are inadequate for multi-leg connections.
8. Validation: destination count/order alone is insufficient. Need swept vehicle/bicycle envelopes, curb/island clearance, non-intersecting parallel-turn paths, entry deflection, grade/crossfall, visibility, ramp conflict and crossing clearances. Retain uncertainty diagnostics; never advertise universal legal compliance.
9. Map configuration: jurisdiction/design profile must be independent from driving side. Current layout_for_map derives US_FL from right-side traffic; replace this during canonical schema implementation. Right-side traffic does not imply Florida law. Whole-network side conversion is a staged, undoable transaction with validation, not an immediate Boolean repaint.
10. Data lifecycle: persistent lane/approach IDs, schema migrations, save/reload, edit undo/redo, copy/paste section templates, import/export and localized dirty-region recalculation. Preview drafts and global setting changes must be isolated; cancellation must restore geometry/data, not only visible fields.

## Additional facility types to allow in schema

Bus/HOV/restricted lanes, bus bays, parallel/angled parking/loading, turn pockets, two-way left-turn lanes, paved shoulders, bike separators and traffic islands. Markings may be decals/mesh; width usage and connectivity exist independent of visible rendering. Reserve curb drainage/door-zone clearances and furniture setbacks; these are not NPC travel lanes.

## UI revision

Road sections: ordered cross-section strips, Add vehicle lane / Add bike facility / Add buffer / Add parking; every travel lane has type, width, direction and permitted movements. Junctions: actual selected geometry, approaches, matched receiving lanes and visible conflicts; context controls show only relevant settings. RoadLab Settings: map driving side and independent jurisdiction preset. Maintain current explicit confirmation before expanding physical road width. Add capacity check before adding any strip, not only car lanes.

## Prioritized delivery

A. Portable typed schema + persistence + full inbound/outbound representation + one-way roads and corridor width accounting.
B. Selected Blender junction/section adapter and compact draft editor; stage Apply/Cancel; no auto-overwrite of user lanes.
C. Conventional/buffered bicycle facility and ordinary motor lanes with direction/markings/continuity.
D. Protected/raised/two-way/contraflow bicycle facilities and controlled intersection conflict logic.
E. Production roundabout road joins + dedicated lane assignments + pedestrian/cycle crossings.
F. Specialized restricted lanes, bus bays, parking and export adapters.

## Required additional cases

One-way motor road with opposite-direction bike facility; two-way raised bike path; bike lane next to parking door zone; right-turn lane crossing a bike lane; bike lane ending before roundabout; protected bicycle perimeter; absent receiving bike lane; independent inbound/outbound widths; adding bike buffer with insufficient corridor width; same topology after source vertex insertion and save/reload; handedness conversion with cycling/parking offsets. Test geometry and semantic routing, not only paint strings.

Primary references:
- 2026 FDOT FDM223: https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/roadway/fdm/2026/2026fdm223bikes.pdf
- 2026 FDOT FDM213: https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/roadway/fdm/2026/2026fdm213modroundabout.pdf
- MUTCD11 Revision1 Chapters9E/3H: https://mutcd.fhwa.dot.gov/pdfs/11th_Editionr1/mutcd11theditionr1hl.pdf
