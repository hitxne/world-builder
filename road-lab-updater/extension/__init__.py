"""RoadLab extension entry point; Blender's extension manager owns updates."""
from . import RoadLab, updates


def register():
    RoadLab.register()
    updates.register()


def unregister():
    updates.unregister()
    RoadLab.unregister()
