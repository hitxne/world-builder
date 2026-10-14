# Standards and reference study — checked 2026-10-13

Sources are official publications. The implementation is a visualization/editor pilot. Listed chapters identify relevant design work; listing a chapter does not mean every criterion has been implemented.

| Publication | Edition / exact topic | Used here |
|---|---|---|
| FDOT Design Manual | 2026; Chapters 210 Arterials/Collectors, 212 Intersections, 214 Driveways, 222 Pedestrian Facilities, 223 Bicycle Facilities, 230 Signing/Pavement Marking, 260 Bridge Structures | Design-context routing; full numerical criteria import pending |
| FDOT Standard Plans | FY 2026–27; 520-001 Curb/Gutter, 522-001 Concrete Sidewalk, 522-002 Detectable Warnings/Sidewalk Curb Ramps, 711-001 Pavement Markings (current index shows interim 711-001-1) | Reference selection; WB curb profile and stripe patterns are illustrative, not replicas of certified plan details |
| FDOT Standard Specifications | FY 2026–27, effective July 1 2026; work quality/material provisions for road and bridge construction | Publication identified; material compliance not implemented |
| FHWA MUTCD | 11th Edition with Revision 1, December 2025; pavement marking requirements | Current edition identified; full marking rules and figures not encoded |
| Access Board final PROWAG | R304.2.1 running slope; R304.2.6 flare slope; R304.4.1 blended transitions; R305.1.1–R305.1.4 dome dimensions/spacing/surface size | Coarse 1:12 running-slope warning; custom depressed-ramp topology; nominal dome 23 mm base, 12 mm top, 5.1 mm high, 60 mm pitch, 610 mm panel depth |

Official URLs:
- https://www.fdot.gov/roadway/fdm/default.shtm
- https://www.fdot.gov/design/standardplans/current
- https://www.fdot.gov/programmanagement/Implemented/SpecBooks/
- https://mutcd.fhwa.dot.gov/kno_11th_Editionr1.htm
- https://www.access-board.gov/prowag/technical.html

Important implementation distinctions: PROWAG blended transitions have a 1:20 slope reference, whereas perpendicular curb ramp runs generally use 1:12 with specified exceptions. The pilot's ramp_type is custom-depressed; it must not be mislabeled as a compliant blended transition. Width, landing, bypass, flare, grade-break, tile-location and clearance checks are incomplete. Selecting 6 inches of curb reveal or 12 feet of lane width is a configurable example, not a universal Florida requirement. The current warning system is not a compliance checker.

## User reference observations translated into editable entities
- Four corner controls remain NW | NE / SW | SE. Physical corner identity follows its adjacent approaches rather than a global smoothing value.
- Ramp endpoints must face each other and retain independent openings, shoulders, run and overrides.
- A left-turn pocket can consume median width without shifting the opposing outer boundary.
- The grass/curb median can terminate independently of the pocket end; a pulled-back nose leaves pavement for a U-turn.
- A through/outside lane may continue directly into a ramp; an incoming ramp may create a receiving lane. Opposing turn lanes need separate connections into the ramp.
- Side-road/driveway openings are staggered along an arterial; outside turn pockets and a bike corridor must remain independent of the median.
- The highway example uses paired elevated decks over a separate lower road. Geometric crossing alone must not create lane connections. Street view additionally calls for abutments, embankments, column exclusion zones and clearance validation; those are not completed here.
- Parking lots have independently editable polygon boundaries, internal planter islands, different stall-row angles/dimensions, circulation aisles and road access points. Truck/loading and retail configurations require different presets. Multiple entrances and shared neighboring circulation are acknowledged but not fully implemented.

No dimensions were inferred as surveyed measurements from screenshots. The test layouts illustrate these relationships rather than reconstructing those exact locations.
