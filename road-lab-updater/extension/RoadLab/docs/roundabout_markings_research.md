# Roundabout markings — implementation rules, 2026-10-14

Read: MUTCD 11th Edition Revision 1, 3D.01–3D.06 and3C.09; 2026 FDOT FDM213; current FDOT Standard Plans index711-001 reference. MUTCD figures were inspected as text; exact arrow outlines/dimensions need template extraction and verification before production meshes.

Sources:
- https://mutcd.fhwa.dot.gov/pdfs/11th_Editionr1/mutcd11theditionr1hl.pdf
- https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/roadway/fdm/2026/2026fdm213modroundabout.pdf
- https://fdot.gov/design/standardplans/current

Mandatory rules are distinct from guidance and optional markings. Marking presets are jurisdiction-specific, never a universal mirrored US law profile.

## Lane graph drives paint

Approach, circulation and departure markings agree with explicit entry-to-exit lane assignments. Drivers select a lane before entry and retain a designated path to departure. Never infer lane use from a decorative concentric ring. MUTCD3D.02 prohibits continuous concentric circulating lane lines. Multi-lane channelization follows departure paths, with appropriate spiral/path guidance.

Multi-lane approaches require lane lines. A through lane becoming mandatory-turn at the roundabout uses dotted white lane-drop treatment under3B.07. Circulating arrows, if used in a multi-lane roundabout, use normal lane-use arrows. On single-lane approaches, the guidance is not to use lane-use arrows. Do not reuse the conventional intersection editor's always-visible turn symbols as roundabout approach defaults.

## Entry/exit edges

Outer white line: solid next to splitter islands, wide dotted across entering lanes. Do not put edge lines/extensions across exits. Optional yellow inner-edge line belongs on the circulating inner edge, with a truck apron modeled separately. Paint cannot make apron/island surfaces into ordinary traffic lanes.

Yield line is optional under national MUTCD3D.04 and consists of the3B.19 yield-line triangles, not a solid stop bar. Entry YIELD sign/control and NPC priority are separate from optional painted yield line. Optional YIELD/YIELD AHEAD words/symbols are separate controls. Yield control is always encoded in traffic graph even if paint disabled.

## Arrow templates

Approach arrows may be normal or curved-stem and may include a central-island circle/oval. Approach arrow style should agree with lane-use signs. MUTCD prohibits lane-use arrows between the crosswalk and wide dotted entry line. Florida213.10 specifies standard left-turn arrow with circular dot in leftmost lane on multi-lane approaches and references711-001 plus213-3/4/5 layouts. Do not choose fishhook solely as aesthetic style or use left/right as direct turns into opposite circulating traffic.

## Pedestrians

No crosswalk to/from central island. Mark pedestrian facilities at entrances/exits, normally >=20ft (6.096m) from circulating roadway edge per3C.09 guidance. This is the current reference distance; do not use the older25ft-from-yield-line wording interchangeably. Splitter islands provide refuge. Crosswalk conflict nodes and approach yielding must be distinct from circulating-vehicle entry priority.

## Validation before release

Validate: no line across exit; dotted entry gaps; triangle orientation; single-lane arrow suppression; no arrows between crosswalk and entry edge; paint stays on pavement and off apron/island; no continuous concentric multi-lane lines; upstream signs match paint; all designated exit paths terminate at real receiving lanes. Geometry tests must include skewed three/five/six-approach layouts and reversed circulation. Marking templates and traffic-side behavior use separate locale profiles.

Status: portable single-lane annulus/path prototype exists; production road-surface joins, markings, pedestrian geometry and Blender UI remain unimplemented. Two-lane roundabouts require ordered per-destination circulation paths; never simply add a concentric lane.
