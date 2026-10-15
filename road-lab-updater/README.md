# RoadLab Blender extension and update repository

The full RoadLab 0.18.3 addon is integrated here, including lane markings and quad terrain. Requires Blender **5.1 or later**.

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

The entry setting controls paint, not a generated widening taper. Crosswalk geometry is not yet used to calculate stop setback automatically; position the stop bar with the setback control when adding a crosswalk. Marking rules are based on FHWA MUTCD 11th Edition, Revision 1, Sections 3A.04, 3B.07, 3B.11, and 3B.19. Traffic-signal timing and NPC simulation remain separate future work.

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
