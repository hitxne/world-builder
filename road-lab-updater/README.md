# RoadLab Blender extension and update repository

The full RoadLab 0.18.12 addon is integrated here, including lane markings and quad terrain. Requires Blender **5.1 or later**.

## Install once

1. Save your project. Disable the older **RoadLab** legacy addon in Preferences > Add-ons, then restart Blender. The legacy addon and extension register the same tools and must not run together. Existing project data is retained.
2. Enable **Allow Online Access** in Preferences > System if it is disabled. Then Preferences > Get Extensions > Repositories > Add Remote Repository. Paste:
   `https://raw.githubusercontent.com/hitxne/world-builder/feature/road-lab-updater/road-lab-updater/dist/stable/index.json`
3. Name it RoadLab and enable **Check for Updates on Startup**. Refresh repositories, find **RoadLab**, and install it from this repository.
4. RoadLab > Updates shows the startup check setting and opens Get Extensions. Blender checks for newer versions; use its Update action to install them. This is not a silent forced updater.

Do not first install this ZIP into a different local repository and then install a second copy from the remote feed. Install from the RoadLab remote repository so Blender can associate the addon with its update source.

## Release workflow

`extension/` is the canonical source for this branch. `extension/RoadLab/` contains the working addon; `extension/updates.py` integrates Blender repository settings. The addon data identifiers remain unchanged so previous .blend scenes keep their authoring data.

For each release, increase **both** `extension/blender_manifest.toml`'s version and `extension/RoadLab/__init__.py`'s addon version. Test compatibility before committing. Blender detects updates only when the feed lists a higher compatible version.

Push source changes to `feature/road-lab-updater`. The GitHub workflow validates/builds the ZIP and commits the generated `dist/stable/index.json` and archive to this branch. The public raw GitHub path hosts both. Generated feed commits do not retrigger the workflow. If branch protection blocks the workflow push, publish the generated files through a reviewed PR instead. No tokens ship in the addon.

Build locally:

```sh
BLENDER=/path/to/blender bash road-lab-updater/tools/build_repository.sh
```

Rollback: disable/remove the extension, then install a previous archived package after backing up the project. Repository checks do not edit project files.

## Marking and stamp update (0.18.0)

With a RoadLab road selected in Object or Edit Mode, choose **Marking Stamp** in the left toolbar (or RoadLab > Marking Stamp > Use Marking Stamp). Entering the tool switches to top-down orthographic view; leaving it restores the previous view. Select a decal, size and rotation in the tool header. Move over the road to preview its footprint; green fits, red does not. Click to place. Undo or Remove last stamp removes a placement. Manual stamps are separate from the automatic lane layout and follow their source road segment through ordinary edits. Stamps whose footprint no longer fits are skipped with a sidebar notice.

Lane window > Markings now exposes arrow spacing, solid approach length, entry-dot length, arrival control at each end, and stop setback. The selected lane's **Lane entry** field distinguishes Continuous from Added lane. Stop and Traffic signals draw a 0.61 m stop bar across arriving lanes at junctions; Yield and Uncontrolled do not. Ordinary lane dividers remain broken away from junctions, become solid in the configured approach section, and use short entry dots for designated added lanes.

The entry setting controls paint, not a generated widening taper. Enabled crosswalks move the stop bar behind the furthest crossing endpoint; the setback control adds clearance. Marking rules are based on FHWA MUTCD 11th Edition, Revision 1, Sections 3A.04, 3B.07, 3B.11, and 3B.19. Traffic-signal timing and NPC simulation remain separate future work.

## Start from a blank scene (0.18.1)

Delete the default cube. Add a mesh plane and scale it to the desired map size (S, 100 makes the default plane 200 m wide). In Object Mode, select the plane, press N, open RoadLab > Scene, and click **Use selected mesh as terrain**. An unmaterialed plane gets the default grass material; existing materials are preserved.

Click **Create Road** in the same Scene panel. It creates a 30 m editable alignment at the 3D cursor, selects the new road, and connects its grading to the designated terrain. Press Tab to edit. Select an endpoint and E to extend; G to move; G then Z to change elevation. Terrain follows after placement. Road defaults holds width and sample spacing. Use Add road branch in Edit Mode for junctions in the same network.

Select the terrain in Object Mode to use Raise, Lower, Flatten and Smooth with adjustable radius and strength. Use Material Preview to see decal textures.

## Approach-only arrows (0.18.2)

Automatic arrows are now drawn only before an actual junction, never on receiving lanes pointing away from that junction. On a segment connecting two junctions, each direction can receive arrows before its own destination junction; the opposite departure half stays clear. Markings > Arrow approach controls the upstream extent (default 35 m; zero disables automatic arrows). Manual stamps remain user-placed. Existing lane assignments inherit the corrected behavior when regenerated.

## Lane window guidance (0.18.2)

The lane window opens with usage instructions when no valid selection exists. In Edit Mode, select one junction location (coincident handles are accepted), or adjacent points along one street. Opening the tool preserves a selected junction. The active edited road takes priority over a stale Scene road assignment. Alt-click with Marking Stamp erases painted markings; Restore automatic markings clears suppression.

Completed releases are always published to the automatic updater on `feature/road-lab-updater`. Standalone ZIPs are supplemental.

## Clear junction controls (0.18.3)

Choose **Edit road from** using direction names computed from the actual connected roads. North is map +Y and East is +X, independent of the viewport. The chosen arm is highlighted orange while the lane window is open. Arriving at junction and Leaving junction replace ambiguous incoming/outgoing headings. Apply saves the chosen arm; reopen to edit another. Guides disappear on Apply, Cancel, or disabling the extension.

## Focused lane workflow (0.18.4)

The lane window has three pages: **Lanes**, **Markings**, and **Road size**. Detail sections start collapsed on each opening. Lanes shows one travel direction at a time, with the lane count, movement choices, widths, and optional entry details. Markings groups arrows, lane lines, and stop lines separately. Road size holds total width, median, section direction, and the confirmed clear action. Junction stop-line controls refer to arrivals at the selected junction; controls for the far end are available by selecting that street section.

Switching junction roads preserves pending edits. Apply validates every edited road before writing any setup and saves them together. If roads need more width, a single expansion confirmation lists the affected roads. Cancel leaves committed road setups unchanged.

## Apply without closing (0.18.5)

**Apply lanes** saves inside the lane editor. The current road, page, open sections, pending drafts, and viewport guide remain available. Width expansion is reviewed and approved inline; changing the request requires reviewing the new dimensions. Invalid changes show an inline message and keep the draft editable. **Done** closes the editor without implicitly saving pending changes. Applied changes remain saved when the editor closes.

## Connected markings and live preview (0.18.6)

Lane and marking edits preview in the viewport without modifying saved lane assignments, pavement, terrain, or manual stamps. Apply commits the draft; Done or Cancel discards changes since the last Apply. The preview is removed before saving a .blend and resumes afterward. A draft that needs wider pavement requests expansion on Apply.

Two-road connection vertices can be selected with the Lane tool. Choose **Continuous street** for joined curved markings or **Stop-controlled** for separated road-end markings and arrival stop lines. The choice is stored at the vertex, survives extension and later branches, and is independent of corner sharpness. This sets marking control; physical sign assets and traffic simulation are separate.

Endpoint extensions inherit an existing street profile when the continuation is unambiguous. New branches at a multi-road junction are not assigned an arbitrary profile. At two-arm bends, paint follows the same rounded side boundaries as the road surface. Differing lane counts receive divider tapers; on straight connections, Markings > Lane lines > Lane merge length controls the transition corridor. Width remains subject to explicit expansion approval. Unsupported median or opposing one-way changes retain a gap with a warning rather than inventing a crossing. These marking transitions are not simulated traffic routing.

## Preserve markings when adding streets (0.18.7)

Adding a branch preserves the existing lane profiles and center, edge, and divider lines. If a new junction makes a saved movement unavailable, only its unsupported directional arrows are suppressed; the lane window flags the movement for review. Applying a new lane setup still validates its movements.

Subdividing a marked source edge transfers its profile and interpolated width to the resulting edges, preserving travel orientation and the controls at the two original endpoints. Collinear subdivisions already affected by earlier versions are repaired when markings regenerate. Ambiguous or removed routes still require explicit reassignment. New branches remain unassigned rather than copying an arbitrary road profile.

## Editable example entry point (0.18.8)

Use **RoadLab > Scene > Load example** for an editable road curve on a connected terrain plane. This opens a separate Blender scene and preserves the previous scene. The curve is selected; Tab enters curve Edit Mode with six authoring points. Move an endpoint with G, then Z to raise it and see terrain grading follow. Terrain remains an editable source plane, with a derived quad grading surface. The asphalt display is generated geometry; the hidden reference mesh is not the editing object.

The older standalone triangulated examples are diagnostic mesh fixtures, now explicitly labeled under **RoadLab Debug > Mesh test fixtures**. They are not the editable road-and-terrain workflow. Road and terrain reference collections are scoped to their scene, so repeated example loads do not add helpers to an earlier scene.

## Crosswalk positions and ramps

In curve Edit Mode, select a junction or adjacent street points and open the Lane tool. Under **Markings > Crosswalk**, enable the crossing, then adjust **A-end position** and **B-end position** independently to skew it. Positive offsets move away from the junction. Amber A/B labels identify the endpoints in the viewport. Preview updates live; Apply saves without closing.

Existing curb and sidewalk layers lower at each endpoint and return to their own profile height over **Ramp run**. Moving either crossing endpoint moves its ramp. Cancelling the lane window restores saved ramps, and temporary previews are excluded from saved files. Add curb and sidewalk layers first on custom roads; the editable example includes both. Optional yellow tactile pads project onto these surfaces, falling back to assigned terrain. Their raised-dot appearance uses a bump shader, not modeled dome geometry.

## Connecting roads with F (0.18.9)

Joining or closing source splines preserves existing point identities and lane assignments, including when Blender reverses point order. New connecting edges inherit matching lane profiles from both ends; differing profiles remain unassigned for review rather than choosing one arbitrarily. Ordinary point movement preserves its settings.

Crosswalk ramp guides sample the finished road edge instead of the source segment height, so lifting a junction preserves ramp and tactile-pad clearance over terrain. Direct road and marking rebuilds guard against re-entry from dependency-graph evaluation.

## Concrete sidewalks and interior connections (0.18.10)

Sidewalks preserve perimeter corners, use corrected polyline offsets, and shade concrete faces flat. A non-destructive **RoadLab Planar Slabs** modifier dissolves nearly coplanar faces (0.1-degree tolerance) while retaining bends and ramp creases. The default editable example drops from 46,384 to 2,021 evaluated sidewalk vertices. This produces planar slab polygons rather than a dense uniform grid; terrain remains quad-based. Curb profiles flatten into crossing grade instead of translating their toe below the terrain. Existing layers upgrade when opening a file or enabling the extension.

With a RoadLab source curve selected in Edit Mode, select two points and press **F** or use **Connect selected points (F)** under Road defaults. Endpoint pairs use Blender's native join. If either point is inside a street, RoadLab adds a connecting spline while preserving the through street and its lane assignments. This shortcut only overrides F for RoadLab core curves. New junction movement permissions remain editable in the Lane tool.

## Surface Bounds (0.18.11)

In **Object Mode**, choose **Surface Bounds** in the left toolbar. Set **Surface** in the tool header to **Sidewalk**, **Curb island**, **Median**, or **Parking lot**. Click outline corners, then press **Enter** or click the first corner to finish. **Backspace** removes a corner; **Esc/right-click** cancels. The new editable mesh plane opens in Edit Mode. Move, subdivide, or extrude its boundary with Blender's normal controls; Geometry Nodes update the generated surface without replacing the source. Concave outlines are supported; the drawing tool rejects crossed outlines.

For a starting square instead, use **RoadLab > Surface Bounds > Create editable plane**. The panel is collapsed by default. Surface height, slab thickness, corner radius and optional curb are controlled there. Islands and medians start with grass and a concrete curb; parking lots start with asphalt. **Follow terrain** samples the assigned terrain and ground road. Flat/sloped planes stay simple; changing ground normals add interior geometry, with **Terrain detail** under the collapsed **Ground and Road** section. Disable Follow terrain to shape elevation by moving the source vertices. Ground and road assignments can be changed per surface.

**Trim overlaps** removes overlap with the assigned ground road and existing enabled curb/sidewalk layers. Trimming uses nearby face bounds, including long planar slabs. Existing road sources and layers remain editable. Bridge-cut road decks are excluded from the road footprint. Save/reopen preserves surface type, unique identity, source plane, targets and node settings.

This feature defines editable surface geometry. Parking stalls, planter-island cutouts, NPC lane connections and automatic crosswalk routing across new pads are separate systems; surface type alone does not generate them.

The 0.18.12 sidewalk preset uses a 0.20 m slab below its 0.1524 m surface rise, so a new pad embeds into grade instead of floating over it. Existing custom thickness settings remain unchanged.

### 0.18.13 — offline PBR surfaces

Grass, asphalt, concrete, sidewalks and gutters use bundled CC0 Poly Haven 1K
base color, roughness and OpenGL normal maps. Maps use world-space meter scale,
box projection and surface-oriented normals without requiring a UV unwrap.
Images are shared and packed into saved scenes; no texture download is needed
at runtime and no displacement subdivision is added. Sidewalks and curbs use
Concrete Floor 02, asphalt uses Asphalt 03, and grass uses Leafy Grass.

Select a road, assigned terrain or Surface Bounds object and open **RoadLab >
Surface materials** to adjust shared texture repeat size in meters. Full material
nodes are editable in Blender's Shader Editor. Original plain RoadLab materials
upgrade on addon enable or file load. Materials with user-authored nodes are
preserved. Use Material Preview or Rendered view to see texture detail.

This release adds PBR surfaces, not the terrain paint brush or irregular
asphalt/grass boundary blend. Those require independent layer masks. Grass is
a flat ground texture; close-up silhouettes will require optional grass instances.
Asset URLs and CC0 license information are in `RoadLab/textures/LICENSE.md`.
