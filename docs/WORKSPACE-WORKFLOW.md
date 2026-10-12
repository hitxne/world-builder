# Combined world and lot workflow

The world remains the central canvas. World Build offers Terrain, Roads, Lots, Scenery and Create World categories. Selecting a lot and choosing Lot Build focuses that lot; Structure, Openings, Floors and Furnish categories act on its children. Returning to World Build preserves the lot and its contents in the same scene, history and project.

The interface uses a bottom catalog with category buttons and contextual settings. Scene and Properties buttons toggle side panels to enlarge the viewport. Asset Studio retains reference comparison, import/reimport and primitive authoring. Catalog / Library and Game Assets remain globally accessible.

This borrows the world-space prop/library approach from Forza EventLab and the lot/category approach from The Sims Build Mode. Terrain and road authoring are requirements of this independent editor, not claims about Forza's native terrain editor. No unavailable game asset previews are replaced with invented thumbnails.

The uploaded screenshot showed vertically compressed buttons and overlapping labels. The canonical stylesheet now prevents controls from shrinking, bounds the main viewport and catalog, and gives long content scrollable containers. Runtime pixels remain readable instead of scaling all controls with the game view.

Validation: source configuration/GUID/input checks and whitespace checks pass. Unity compilation, actual layout at different window sizes and pointer interaction must still be verified in Unity 6000.6.5f1 on Windows. This UI change does not complete game resource decoding, controller input, realistic directional lanes/turning lanes, curved walls or drive mode.
