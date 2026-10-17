# Responsive terrain sculpting — 0.18.18

Terrain Raise, Lower, Flatten and Smooth now keep a preview session open across
multiple strokes. Release the mouse to stop painting, make more strokes, then
press Enter or right-click to compile the detailed terrain. Switching tools also
applies the session. Escape discards the whole preview session.

The brush keeps the sparse height field in memory, applies changed samples, and
updates nearby existing preview vertices through a spatial index. It does not
serialize the whole field or compile terrain and road markings for every sample.
The background scheduler defers rebuilds throughout the session. Sparse faces
receive local preview subdivision, capped at 60,000 vertices for additional
refinement; the original authoring mesh is preserved. Existing previews can
already exceed that cap. Initial preview creation still copies and indexes the
existing mesh, so setup cost scales with the starting mesh.

Terrain and road brushes have tool-selected hover footprint rings. Cursor
raycasts reuse cached geometry; source-mesh geometry updates invalidate the hover
cache. Road sculpt picking also reuses its BVH until compiled road geometry changes.
Road deformation, widening and banking still use their existing rebuild paths;
this release does not make those operations local preview edits.

Road-contact weights keep terrain preview vertices pinned at the road seam.
Height queries start just above the reference mesh instead of 100 km above it,
avoiding float precision drift during local subdivision.

## Validation and limits

The new Blender regression covers 100 local updates, untouched distant geometry,
source-mesh preservation, raycast agreement, sparse-plane interior deformation,
road seam preservation, scheduler deferral, preview-to-commit agreement, and the
operator's apply/cancel paths.

On a headless Blender 5.1 run using an AMD EPYC CPU, the synthetic 10,201-vertex
preview had roughly 0.4 ms median brush calculation time. Preparing an interior
preview on a 1 km four-vertex plane took roughly 8–12 ms in isolated runs.
These measure calculation time, not viewport frames or input-to-display latency.
Shared host load can produce larger outliers. No GPU is exposed in this runtime.

Interactive hover behavior, frame rate, GPU load and large-world performance
still require validation in a normal Blender session on the user's machines.
Detailed compilation remains synchronous when applying the session. Automatic
idle refinement, cancellable compilation, chunk streaming and local road rebuilds
are not implemented in this release.
