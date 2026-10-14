"""Road Lab update scaffold only; replace with the actual add-on before release."""
import bpy


class ROADLAB_PT_update_info(bpy.types.Panel):
    bl_label = "Road Lab Updates"
    bl_idname = "ROADLAB_PT_update_info"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Road Lab"

    def draw(self, context):
        col = self.layout.column()
        col.label(text="Updates: Preferences > Get Extensions")
        col.label(text="Use the configured Road Lab extension repository")


def register():
    bpy.utils.register_class(ROADLAB_PT_update_info)


def unregister():
    bpy.utils.unregister_class(ROADLAB_PT_update_info)
