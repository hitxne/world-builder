# Lane-system implementation research — 2026-10-14

Status: researched design contract, not implemented in RoadLab 0.15.

Primary references read: MUTCD 11th Edition Revision 1 (December 2025), Sections 3B.06–3B.12 and lane-use markings; FDOT 2026 FDM 212.14 and Exhibit 212-1; FDM 211 entrance/exit terminals; TxDOT Roadway Design Manual 4.11.1 stopping sight distance.

- https://mutcd.fhwa.dot.gov/pdfs/11th_Editionr1/mutcd11theditionr1hl.pdf
- https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/roadway/fdm/2026/2026fdm212intersections.pdf
- https://www.fdot.gov/roadway/fdm/default.shtm
- https://www.txdot.gov/manuals/des/rdw/chapter-4--basic-design-criteria/4-11-sight-distance/4-11-1-stopping-sight-distance.html

## Separate design quantities

Store entry taper, full-width deceleration region, queue storage, merge taper, acceleration region, and solid-line approach zone separately. FDOT total deceleration lengths include the taper: subtract the included taper before summing regions; do not double count it. Queue length is demand/control dependent, not solely speed dependent. FDM 212 specifies 50ft approach taper for a single turn lane and 100ft for multiple turn lanes; do not reuse these values for through-lane reductions or freeway ramps.

MUTCD 3B.12 lane reduction: L=WS for speed limit >=45mph; L=WS²/60 below45mph, L/W feet and S mph, S higher of speed limit and85th percentile. Defaults also honor 100ft urban/200ft rural minima and preserve the documented low-speed exception. Speed limits and design/observed speeds are distinct inputs. Unit conversions happen at preset boundary; canonical geometry uses meters.

Stopping sight distance includes reaction plus braking. TxDOT reference uses 2.5s reaction and11.2ft/s² deceleration; downhill changes braking needs. Gameplay vehicle braking/traction remain independent from design presets. A kinematic deceleration estimate is not a substitute for FDOT ramp/turn-bay tables.

## Canonical graph

Road stations measured by arc length; persistent lane IDs independent of vertex indexing; section lane lists include direction, width, role, movement permissions, links and explicit marking intervals. Junction approaches use local travel orientation, not global NW labels. Lane count changes preserve survivor IDs and explicit end-lane destination. Markings, road footprint, curbs and terrain derive from the same section geometry.

Connectors are explicit incoming-to-outgoing lane mappings. Classify permitted left/through/right by actual approach headings and availability, including skewed T intersections. Multiple turning lanes preserve order and do not cross; movements that cross each other become traffic-control conflict records. U-turn paths depend on median opening and vehicle swept-path clearance, not a left-turn checkbox.

## Markings

Broken white: ordinary same-direction separation. Dotted white: noncontinuing/auxiliary transitions; wide dotted lane-drop treatment where specified. Single solid white discourages crossing; double solid white prohibits crossing. Solid approach segment is independently editable, not automatically equated to braking distance. Arrows/ONLY/stop bars/crosswalks and dotted intersection guides use actual lane roles and connectivity. Preserve dash phase across road tessellation/chunks; project paint onto final banked pavement and trim outside pavement/inside conflicting intersections.

## Medians and constraints

Independent station-based left/right median boundaries; width, taper, nose, setback, turn pocket and opening spans. Limit openings by actual U-turn/turn vehicle envelope. Store unavailable space/conflicts as diagnostic output; never silently compress a requested transition to fit or fabricate a destination lane.

## UI and performance

Toolbar Lane tool opens a draft editor with plan preview. Choose road or junction, click approach, edit ordered lanes, allowed movements, end lane, taper/deceleration/storage and median spans. Auto/manual values must be explicit. Apply commits; Cancel restores. Preview uses lightweight lanes/paint curves; only dependent sections/junctions remesh on commit. Blender and Unreal adapters consume the same portable lane graph.

## Acceptance cases

Four-to-three left/right lane reduction; skewed T with no nonexistent movement; dual left turn with ordered connectors; through lane becomes turn-only; highway exit lane versus through-lane merge; median turn pocket and recessed U-turn opening; adjacent transitions competing for length; graded/banked pavement; dotted-to-solid approach zone; source/destination lane mismatch. Validate lanes remain ordered, connectors terminate in real lanes, markings stay on pavement, intervals do not double count taper, and stable IDs survive control-point insertions.
