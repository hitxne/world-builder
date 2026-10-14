# Selected-point editing — RoadLab 0.14

Select control points in Edit Mode and open RoadLab → Selected points. Road geometry shows width and a reset arrow; move points with G then Z for elevation.

The Corners section appears only for bends/junctions with applicable corners. Choose NW/NE/SW/SE (only relevant directions are shown), then edit Radius or Lift. Inner and outer corners are labeled. Lift adds a smooth local elevation offset relative to the source curve; it is independent of whole-point movement. Mixed values show the selected range. Reset all selected corners clears both radius and lift overrides.

Use Object Mode and Blender's left toolbar for Raise, Lower, Flatten, Smooth, Widen, Bank and Slice. Normal Slice starts a disconnected terrain span; Alt + Slice reconnects it on the same spline. See README_CORE_v014.md for installation, tool usage and current limits.
