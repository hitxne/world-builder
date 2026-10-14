# Terrain edit contract — version 1

Source: editable terrain mesh and object transform, with metre units and right-handed local Z-up coordinates. Edits: `roadlab_terrain_field`, the portable sparse 1 m displacement schema used by `road_heightfield.py`. Adaptive criteria: detail spacing and height tolerance. Derived data: road-contact seams, adaptive samples, triangulated cavities and merged flat polygons.

`adaptive_terrain.py` uses standard Python math only. Terrain brush falloff, raise/lower/flatten/smooth and field sampling reuse the engine-independent road height-field kernel. `terrain_patch.py` and terrain constrained triangulation use Blender geometry APIs and still need an Unreal implementation. Persist source and edit data, regenerate output topology, and explicitly convert units/basis for Unreal. No Unreal adapter is included in this build.
