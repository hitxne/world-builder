# Imported appearance, automatic upgrades and contextual building

## Existing imports

After this update, start Play Mode/the app. If the Sims installation was previously saved and Data/Client remains accessible, a one-time background migration runs automatically. It refreshes catalog categories and English STBL names, upgrades the old geometry-only OBJ exports, and reimports changed appearance into existing library IDs. It invalidates old thumbnails and rebuilds the active catalog. Cancelled/failed imports are retried on a later start. Manual organization overrides remain unchanged. The summary reports imported/updated/skipped/failed counts.

Live placed instances refresh their mesh/material components with transforms, parents and identity unchanged. On opening a saved world, linked Sims library appearances are synchronized with the upgraded library. Worlds are marked dirty after live appearance changes; save to keep the current snapshots. Existing world object names that still equal generated resource filenames become readable catalog names; edited instance names are retained.

If no saved installation is available, use Add Sims assets and select the EXE once. Game/source package files remain read-only. Generated export files can be replaced atomically during migration; library identities persist.

## Appearance support and preservation

The shared reader now follows MLOD material references, including MTST default material state, and parses bounded MATD/MTRL/MTNF shader-data records. UV0 (float2, half2, short2 with shader UV scale, normalized short/ushort2) and float3/packed normals are decoded when supported. OBJ retains actual UV and normal indices and separate material groups. DirectX-style UV V is converted to OBJ's bottom-origin convention.

DDS BC1/DXT1, BC2/DXT3 and BC3/DXT5 and documented DST1/DST5 shuffled payloads decode to lossless RGBA PNG for the current base-color renderer. Alpha is preserved and imported Sims materials use alpha clipping. The PNG converter retains only the top mip; original payload retains all original mip data. PNG input is retained unchanged. Cubemaps/volumes, DST3, DX10, RLE2/RLES and other image layouts remain explicitly unsupported for rendering.

Resolved original MATD shader records, all their referenced texture payloads, converted images and the source MLOD payload are stored beside exports and embedded in .wbworld sourceAppearance. Unknown shader parameters/maps survive this snapshot. Standalone OBJ export emits a source bundle alongside ordinary OBJ/MTL/base-color images. No external game installation is required to reopen stored supported appearance or source bundles.

This is a base-color/default-state approximation, not Sims renderer parity. Normal/specular/emission maps and custom Sims shaders are preserved as source data, not automatically interpreted as Unity PBR. Material variants, dynamic states and unmatched dependencies remain unassembled. Missing/conflicting texture dependencies are reported; they cannot be preserved if the resolver cannot identify their payload. Identical duplicate package resources are accepted, conflicting duplicates require validated patch precedence. Source bundles have bounded import limits (16 MB/resource, 48 MB aggregate) and existing 128 MB project limits still apply; this is not a streaming-map storage solution.

## Buy UI

Room/function buttons remain visible alongside real thumbnail cards. A name search and category/page heading show the active context. Click a card to pick up/place it directly; the small ⋯ button opens the read-only 3D preview and organization actions. Assets > Library placement returns to World > Objects. The catalog dock expands only for object browsing. Thumbnails are regenerated after upgrades.

## Roads

World > Roads separates Build roads from Roadside objects. Choose Local street, Avenue or Country road, then drag a Straight road and release to commit one undoable segment. Full-width preview uses the same terrain projection as the committed road. Grid mode snaps to 45-degree angles and existing road endpoints; Alt draws freely. Width/sidewalk controls apply to the next segment. Escape and lost pointer capture cancel unfinished road placement. Curved route retains point-based spline building with Finish route/Enter. Move/rotate/delete and Properties use the common editing tools.

Endpoint snapping does not yet generate intersection junction geometry, merge lanes or resolve overlapping markings. Roadside objects use the imported visual catalog and ordinary object placement. These limits remain separate from the newly simplified gesture/workflow.

## Verification

Actual shared-exporter compilation and synthetic package integration tests cover MTST/MATD links, UVs/normals, pixel values for BC1/BC2/BC3 and DST1/DST5, immutable raw texture/material bytes, names/categories, existing geometry-only export migration, repeat/resume and unchanged source packages. Source/configuration and syntax checks pass. A Unity regression test covers PNG/material-name/opacity/raw-source save/export roundtrip, but has not run here. Unity compilation, native gestures, saved-installation startup migration and visual usability require the Windows Unity environment.

Format references (independent implementation; no s4pi code/library included):
- https://github.com/s4ptacle/Sims4Tools/tree/fff19365a12711879bad26481a393a6fbc62c465/s4pi%20Wrappers/s4piRCOLChunks
- https://github.com/s4ptacle/Sims4Tools/blob/fff19365a12711879bad26481a393a6fbc62c465/s4pi%20Wrappers/ImageResource/DSTResource.cs
- https://github.com/s4ptacle/Sims4Tools/tree/fff19365a12711879bad26481a393a6fbc62c465/s4pi%20Wrappers/MeshChunks

## Deeper road control and junctions

Road settings separate Cross-section, Markings, Elevation, Shape, Connections and Surface. Eight presets cover local streets, two-lane/multi-lane roads, highway, dirt, parking, service and footpath layouts. Width/lane controls are synchronized; shoulders, sidewalks and medians affect real geometry. Banking/elevation offsets survive terrain conformance. Markings use physical dash spacing, separate yellow center/white lane and edge groups. Surface/friction/speed metadata persists.

Edit nodes drags control points; Shape supports numeric positions, insertion/removal, reverse and smooth-vs-straight segments. Grade terrain cuts/fills beneath the profile with a feathered margin, preserves paint and locks road elevation. Grading currently requires upright, uniformly scaled road/terrain transforms.

Junctions have width/depth and corner radius. Road settings > Connections assigns start/end to an existing junction's North/East/South/West side, with separate slide offsets. The usable range accounts for the radius and road width. Opposing roads need not share an alignment or central point. Dragging connected endpoint nodes slides their offset along the corresponding side; moving/resizing a junction updates linked endpoints. Source graph/road metadata is also emitted alongside OBJ as .roads.json.

This provides rounded junction surfaces and independent editable ports, not seamless intersection lane merging, automatic road flares, crosswalks, sidewalk corner transitions, traffic routing or bridge geometry. Native interaction/persistence verification remains pending; pure junction bounds, corner rounding and independent side offsets are tested.
