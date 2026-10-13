# WB Road Lab 0.6 — TrackTools terrain connection

The accompanying WB_RoadLab_v06 download bundle contains `Scenes/WB_Terrain_Preview.blend` to inspect the repaired world immediately. It contains baked terrain and needs no external nodes. It is a viewing copy; use the live scene for sculpting.

Install `Dist/WB_RoadLab_Addon_v06.zip` in Blender 5.1 (Preferences > Add-ons > Install from Disk). Open `Scenes/WB_TrackTools_Terrain.blend` from that bundle. Put your own original TrackTools node library alongside it, named `TT_NodeGroups.blend`, or use **WB Roads > Terrain sculpting > Connect TrackTools node library** and select your existing node library. The commercial node library is intentionally not included in this bundle.

The connection button also works in an existing version 3 WB connected-world scene. It stages a replacement first; missing or incompatible node libraries leave the current world intact. Terrain must be enabled. Direct mesh edits are protected from rebuilding; use the terrain brush for persistent sculpting.

## What changed

The connected terrain now links the original `TERRAIN_GEOMETRY` and `TERRAIN_SHAPE` groups. WB supplies upward road, sidewalk, curb, median and planter faces plus tagged border curves (`parts` and `edgeID`). The original groups perform adaptive refinement, terrain shaping, road cutting and boundary alignment. Their contents are never edited.

This uses TrackTools' native optional **cut terrain** branch, rather than lowering a whole terrain grid beneath every road slab. Elevated bridge faces and the designated elevated portions of connecting ramps are excluded from the ground cutter. Supports sample evaluated terrain or physical median soil, not the unmodified baseline.

The original TrackTools startup uses its continuous-under-road configuration with cutting disabled. That was checked as the baseline. Cutting is enabled in this WB adapter because the WB network contains overlapping separate furniture surfaces and Boolean road joins; continuous terrain produced up to 9 cm of pavement overlap in the complex fixture. The native cutting branch removed those visible overlaps and aligned the exterior boundaries.

The circular Raise, Lower, Smooth and Flatten brushes edit a persistent baseline while the linked TrackTools modifiers preserve road contact. The cursor follows the evaluated terrain. Radius and strength remain adjustable, including Shift+wheel and Ctrl+wheel. Enter commits; Escape cancels. Contact band and terrain blend can be changed before **Apply detail / rebuild terrain**. The demonstration uses a 1 m contact band, 18 m blend, and 1 m baseline grid.

## Validation and limits

Blender 5.1.2 headless: simple raised strip, complex interchange renders, six exposed arterial sidewalk-edge contact samples, all four brush modes, baseline persistence through rebuild and save/reopen, linked native groups, and original library byte hash unchanged. Existing 46 portable tests pass.

At the six unobstructed arterial samples, terrain contact error was below 0.02 mm. Across 16,785 terrain/pavement projected triangle overlaps, the largest positive difference was 0.044 mm (Boolean/float precision), rather than the earlier 9 cm. This is a tolerance measurement, not an exact-zero claim. Samples deliberately avoid ramp and access openings, where the sidewalk has been cut away. See `Evidence/validation.json`; the renders are in the accompanying download bundle.

The modal brush UI has not been exercised in a live graphical session. Very dense terrain and Boolean cuts can take several seconds to evaluate. The comparison scene demonstrates this network; it does not certify every possible road layout or terrain source.

Original commercial TrackTools files remain external dependencies. The original startup and node library were inspected without overwriting them. The editable scene resolves `//TT_NodeGroups.blend` relative to its own folder. Reconnect the library after moving it. The standalone preview is for immediate visual review.

## Repository checks

Run `python -m unittest discover -s Blender/WB_TrackTools/tests` from the repository root. To run the native integration check, set `WB_TT_LIBRARY` to your own TrackTools node file and run `blender --background --factory-startup --python Blender/tests/native_terrain.py`. The test checks road-edge contact, native terrain cutting, all brush modes, rebuild persistence and save/reopen. Run `python Blender/build_addon.py` to rebuild the installable ZIP from source.
