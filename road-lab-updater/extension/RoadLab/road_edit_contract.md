# RoadLab authoring/edit contract — version 1

The Blender UI is an adapter. Future Unreal tools should consume authored edits, not Blender-generated helper objects. `road_edit_export.authoring_state()` exports defaults, local curve points with IDs and width/radius/lift overrides, a sparse elevation field, terrain-contact cuts, and the object transform.

`road_heightfield.py` and `road_paths.py` depend only on Python's math/json standard library. Their sampling, falloff, raise/lower/flatten/smooth, banking, closest-path projection and cut-span rules are the reference math for a later Unreal implementation. No Unreal adapter is included yet. The topology compiler still uses Blender's geometry library and must be ported or replaced in the engine.

All stored distances are metres in right-handed road-local coordinates with Z up. An Unreal adapter must explicitly convert metres to centimetres and its coordinate basis, including winding. Radius/width edits, deformation edits, bridge-contact masks and terrain meshing are separate operations. Preserve the editable curve and source terrain and regenerate derived surfaces.

Grid samples store displacements from the compiled curve + corner-lift surface. Bilinear sampling reconstructs sculpt displacement; raise/lower use a compact circular quadratic falloff, while flatten/smooth use exponential time-based blending. Banking applies a clamped lateral slope under the same circular falloff. Ground-contact cut spans are stored as projected road-local anchor positions on a spline. Contact face masks are derived data.

Blender point identity is currently maintained through index order during movement and coordinate matching when counts change. This is not a fully robust topology-ID model for arbitrary reordering or duplicate-point operations. Strengthen it before a bidirectional Unreal round-trip.
