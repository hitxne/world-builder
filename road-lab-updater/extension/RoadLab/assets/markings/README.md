# RoadLab road marking decals 0.1.0

35 reusable markings with transparent PNG textures, grayscale alpha masks and editable SVG sources. manifest.json records dimensions in meters, UV anchors, provenance and tiling recipes.

FDOT templates have drafting gaps removed. Mirrored and composite arrows are identified separately. Striping and crosswalks are parameterized; the yield-ahead outline is interpretive. These are game assets, not certified construction drawings. Verify local placement and dimensions.

Forward is top of PNG / positive UV V. Use physical dimensions and UV anchors from the manifest. RGBA uses straight alpha and retains paint RGB underneath transparency. Import masks as Non-Color. Blend into the road material or place slightly above the surface with an adjustable offset. Tile striping along its recorded axis and clip to junction and lane boundaries. Green bike patches supplement white markings.

Lane arrows, dividers, opposing-direction lines and edges are integrated with the RoadLab 0.16 lane editor. Other facility and control markings await their corresponding features. Traffic-light timing and coordinated junction simulation remain future notes only.

Official reference links and individual source classifications are in manifest.json. Full reference PDFs are not bundled.
