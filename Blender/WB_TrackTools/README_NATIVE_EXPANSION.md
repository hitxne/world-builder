# WB TrackTools additive Geometry Nodes expansion — 0.7

This is the first migration to the correct TrackTools-native workflow. Open your original working TrackTools project. Keep its original road curves, terrain plane, collections and Geometry Nodes modifiers. Install the v0.7 addon ZIP, enable it, then use **WB Roads > TrackTools + WB > Use existing TrackTools scene**.

The addon binds to the existing native `ROAD` curve modifier and `TERRAIN_SHAPE` plane. It does not replace either object, apply their modifiers, rewrite their node groups, create a parallel JSON world, or save over the original TrackTools files. The native width, resolution, crossfall and terrain blend controls continue to edit the existing modifiers.

Choose **Add curb**, **Add sidewalk**, or **Add grass strip**. Each adds its own Geometry Nodes extrusion object and editable profile curve in WB-owned collections. No extrusion is enabled until you add it. The original ROAD output's tagged border curves are used as the live path. Geometry is generated on demand by `WB_EXTENSION_BORDER_EXTRUSION`.

Select an extrusion to expose its node inputs:

- Enabled: independently show or disable its output.
- Profile curve: edit the curve's vertices to shape its cross section.
- Path curve / Use custom path: optionally use your own curve vertices instead of the native border curves.
- Profile width scale, profile height scale, setback and height offset.
- Crossing road, Lower at crossing and Transition length: choose a native crossing road and enable lowering. Ray hits set the sidewalk top to the native crossing surface; the nearby transition blends smoothly. The cross-section thickness is retained. Elevated crossing roads do not force a downward depression.
- Material: available in the Geometry Nodes modifier.

The **Edit extrusion profile vertices** button selects the profile curve and enters Edit Mode. You can also use the Outliner. Profile objects are initially hidden from the viewport and render so they do not appear as loose scene geometry. Changing the road curve, native ROAD settings, profile vertices or crossing curve updates the extrusion without rebuilding a JSON graph.

The standalone `WB_Native_Expansion_Nodes.blend` contains only our expansion group. It has no commercial node dependencies. You may append that group and use its exposed object inputs directly without the sidebar.

Validation on Blender 5.1.2: original source-file hashes unchanged; native source datablocks and modifier stacks unchanged; +1 m road-curve edit moves the extrusion +1 m; editable profile vertex changes appear in output; enable toggle removes/restores output; sidewalk crossing top within 0.04 mm of the selected native road. The modal Edit Mode UI has not been manually exercised in a graphical Blender session.

Scope: this first additive pass covers native binding and optional curb/sidewalk/grass extrusions with a selected crossing road. It does not migrate the previous JSON world's junctions, parking lots, median openings, brush or bridge support tools into native node controls yet. Legacy examples are hidden in a native TrackTools scene to avoid replacing the authoring workflow. Multiple crossing roads require separate extrusion controls in this pass. Terrain collection targeting remains under your original TrackTools controls; the addon does not rewrite those connections.
