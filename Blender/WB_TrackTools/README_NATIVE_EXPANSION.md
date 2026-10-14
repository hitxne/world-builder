# TrackTools + WB — repeatable layer expansion 0.8.2

Install `WB_TrackTools_Additive_v082.zip`, enable the addon, open your original TrackTools project, and click **WB Roads > TrackTools + WB > Use existing TrackTools scene**. This button also adopts existing WB 0.7 extrusions into the new layer stack. TrackTools remains the authoring system: its original terrain plane, road curve data, and commercial Geometry Nodes groups are retained.

## Installation repair

0.8.2 defers existing-scene upgrades to a cancellable timer after addon registration. This avoids accessing scenes inside Blender’s restricted addon-enable context. Scene loads still run the upgrade handler. Disable/uninstall cancels any pending timer.

## Performance repair

0.8.1 removes the per-segment edge splitting that capped every resampled piece. Enabled spans now remain connected, with caps only at actual disabled gaps. Viewport cleanup uses the faster floating-point Boolean solver. Precise cleanup is lazy: it runs for rendering or when **Precise viewport cleanup (slower)** is enabled in the sidebar. An empty fast result falls back to precise cleanup instead of silently deleting a feature. Fast and precise solvers can differ around difficult coplanar or self-intersecting junctions; enable precise viewport cleanup when reviewing those or exporting evaluated viewport meshes.

The original native terrain remains connected and enabled. A fixed headless Blender 5.1.2 test moves the native road control point four times per configuration. With curb and sidewalk, the median update dropped from 2.93 s in 0.8 to approximately 0.12 s in 0.8.1, about 24 times faster in this scene. These are dependency-graph update times, not a graphical viewport FPS guarantee. The before/after samples are included in `Evidence/native_performance.json`.

Existing layers upgrade automatically when this addon is enabled or their scene is loaded. Their ROAD/profile bindings and existing socket identifiers are retained; the original commercial node groups and road curve data are preserved. Unchanged modifier inputs are no longer retagged, and moving control points no longer rewrites unchanged layer-stack inputs. If the previous addon is already enabled, replace it with this version and restart Blender to load the new Python code.

## Ordered, repeatable layers

Every Add button creates an independent instance with a unique identifier, profile, settings, and generated object. Add **Curb, Grass Patch, Sidewalk, Grass Patch, Sidewalk** in that order for:

**Road → Curb 1 → Grass Patch 1 → Sidewalk 1 → Grass Patch 2 → Sidewalk 2.**

The list runs from the road edge outward, on both native borders. Select a row and use the up/down arrows to reorder it. Starting offsets are calculated from the widths and gaps of preceding enabled layers, independently at each original control vertex. Changing an inner width moves the outer layers. Disabling a layer closes its occupied space. Repeated kinds never share vertex-setting identifiers.

The **Curb layers**, **Grass patch layers**, and **Sidewalk layers** panels contain separate controls for every instance:

- Width: physical width in metres, independent of the profile's original X coordinate.
- Offset / gap: additional lateral space before this layer; zero means touching the preceding layer.
- Z offset: vertical adjustment relative to the road and profile height.
- Enabled at vertices: removes the affected span, rather than hiding all instances of that kind.
- Layer enabled: globally enables/disables just this instance.

In **Object Mode**, these fields apply to all road vertices. In the original road's **Edit Mode**, they apply only to selected control vertices. Click **Read selected** to inspect the first selected point; mixed selections show that point's values. **Disable** and **Restore** affect only the selected vertices for that instance. Values interpolate along the raw source curve. Enabled values use a midpoint threshold, so a transition between enabled and disabled control points ends halfway along that segment. Select consecutive vertices to remove a longer span. The generated feature is capped at disabled spans.

New control vertices currently receive layer defaults when source topology changes; existing vertices at unchanged positions retain their settings. Reordering preserves identifiers and all vertex values. Normal movement of existing points remains live.

## Geometry Nodes and terrain

Each WB feature has a Geometry Nodes modifier using `WB_EXTENSION_BORDER_EXTRUSION`. Its live source is the original ROAD's tagged border output. Editable profile curves and optional custom path curves remain available. Profile height scale and selected-crossing lowering are retained. With ordered vertex controls enabled, **Width** in the layer panel is authoritative; the legacy profile width scale and setback inputs are for standalone node use.

WB vertex settings live on WB-owned helper objects. The raw road curve is shared read-only into a helper so custom attributes can interpolate without repurposing the original radius or tilt fields. Original ROAD and TERRAIN node groups are never rewritten.

The native terrain's target collection is extended to include the generated WB surfaces and boundary curves. An object-only target is wrapped in a WB-owned collection retaining the original target. Original terrain modifiers and blend settings remain active. A separate road-only reference collection prevents WB features from referencing themselves through the terrain target collection.

**Junction cleanup** resolves intersecting sweep volumes and clips material over native asphalt through WB-only boolean nodes. Acute corners and unusual multi-road layouts still need visual review; this is not a claim that every possible junction has been validated. **Crossing road**, **Lower at crossing**, and **Transition length** remain explicit controls on each feature modifier.

## Validation and package

Blender 5.1.2 headless integration checks verify the requested five-layer stack's non-overlapping lateral ranges, width propagation, reordering, independent repeated IDs, selected-vertex width/offset/height, span disabling, empty output when all vertices are disabled, and live source-curve edits. The existing native integration also passes: original source hashes and modifier stacks preserved, profile/custom-path edits live, and selected crossing top within 0.04 mm. The layer checks pass in both fast and precise viewport modes; a 0.8 node-group adoption test retains existing road/profile bindings and verifies visible output after upgrading. The 46 portable geometry tests pass. Sidebar classes register successfully; mouse interaction has not been manually tested in a graphical Blender session.

`Evidence/RepeatedLayers.png` is an actual Blender render of the tested stack, with terrain hidden for visibility and a plain asphalt material on a temporary render copy because the supplied texture file was unavailable. `Nodes/WB_Native_Expansion_Nodes.blend` contains only our expansion group, with no commercial node dependencies. The original TrackTools scene and node library are intentionally not redistributed.

Native migration of the legacy JSON parking, median, sculpt-brush, and bridge-support examples remains separate work. Existing legacy examples are hidden in native TrackTools scenes.
