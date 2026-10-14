# Roundabout sidewalks — 2026-10-14

Primary sources read:
- FDOT2026 FDM213.3.5,213.8.1–213.8.3, Exhibit213-1: https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/roadway/fdm/2026/2026fdm213modroundabout.pdf
- Final PROWAG R306.4 and R304/R305: https://www.access-board.gov/prowag/technical.html
- MUTCD11 Revision1,3C.09: https://mutcd.fhwa.dot.gov/pdfs/11th_Editionr1/mutcd11theditionr1hl.pdf

## Shape and continuity

Sidewalks form an outer pedestrian perimeter, joining each approach sidewalk through arcs and entry/exit corners. They do not cross the circulating roadway to the central island. A simple concentric sidewalk ring is insufficient: every approach interrupts that ring and needs separate crossing paths with refuge links. Use the finished pavement/curb boundary and explicit crossing stations, not only centerline offsets. Keep sidewalk width, buffer width, curb profile, walkway elevation and crossing ramps independently editable.

## Florida profile

When approach pedestrian facilities exist/planned, provide sidewalks consistent with FDM222/approach widths and crosswalks at every leg. A5ft buffer from back of curb is desired, typically >=2ft. With bicycle ramps, desired sidewalk width10ft, minimum8ft; do not apply this width to every ordinary sidewalk. Refuges in splitter islands need6ft minimum clear between curb faces and10ft crosswalk width through island. Keep these two different dimensions separate.

FDM213.3.5 references approximately20ft upstream of yield line for the crosswalk; MUTCD3C.09 references minimum20ft from circulating edge. Store reference anchors explicitly, not one ambiguous setback. Florida offset enhanced crossings have separate incoming/outgoing setbacks (213.8.3); preserve each half-crossing configuration. Angled crossings align each half perpendicular to respective entry/exit curb, with the angle point in the refuge. Straight crossings support continuity of major shared-use paths.

## Ramps/accessibility

Generate paired curb ramps/blended transitions, landings, detectable warning patches, and level/cut-through refuge route. A crossing removes/lowers curb locally and reshapes adjacent sidewalk; it does not lower the entire sidewalk sector. Terrain must follow the entire road/curb/grass/walk footprint while protecting landing and ramp constraints. R304 slope/width limits depend on ramp type and route context; apply named presets, not a generic bevel.

Final PROWAG306.4 edge detection: non-curb-attached routes have >=24in landscape/nonprepared separation between crossings; curb-attached routes use a continuous detectable vertical street-side edge between crossings. Detectable warning tiles are not a substitute for perimeter edge detection. Multi-lane crossing segments require one of the listed enhanced treatments: pedestrian signal, PHB, pedestrian-actuated RRFB or raised crossing. Keep guideline applicability/adoption in locale settings rather than claim universal statutory compliance. Do not rely on older proposed-PROWAG signal-only wording.

## Data and validation

Separate pedestrian graph from vehicle graph. Entry and exit crossings are distinct conflict links, connected through refuge and perimeter walk paths. No direct island route, no walkable truck apron. Validate ramp alignment, continuous walkable width, refuge clearance, cross slopes, curb discontinuity only at crossings, grass/walk edges with no overlaps, terrain seam elevation, and buffer/edge detection continuity. Test three-to-six-arm roundabouts, acute/skewed approaches, independently disabled sidewalks and incoming/outgoing setback differences.

Status: researched design requirements. Sidewalk geometry and crossing generation for roundabouts are not implemented yet.
