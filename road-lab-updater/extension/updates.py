"""Native Blender repository setup and update UI; no custom code downloader."""
import bpy

REPOSITORY_URL = 'https://raw.githubusercontent.com/hitxne/world-builder/feature/road-lab-updater/road-lab-updater/dist/stable/index.json'


def repository(context):
    return next((r for r in context.preferences.extensions.repos
                 if r.remote_url.rstrip('/') == REPOSITORY_URL.rstrip('/')), None)


class ROADLAB_OT_configure_updates(bpy.types.Operator):
    bl_idname = 'roadlab.configure_updates'
    bl_label = 'Connect update repository'
    bl_description = 'Add the RoadLab repository to Blender and check for updates at startup'

    def execute(self, context):
        repo = repository(context)
        if repo is None:
            bpy.ops.preferences.extension_repo_add(name='RoadLab', remote_url=REPOSITORY_URL,
                                                  use_sync_on_startup=True)
            repo = repository(context)
        repo.use_sync_on_startup = True
        bpy.ops.wm.save_userpref()
        self.report({'INFO'}, 'RoadLab repository connected. Install RoadLab from Get Extensions to receive its updates.')
        return {'FINISHED'}


class ROADLAB_OT_open_updates(bpy.types.Operator):
    bl_idname = 'roadlab.open_updates'
    bl_label = 'Open updates'
    bl_description = 'Open Blender Get Extensions; refresh repositories to check available versions'

    def execute(self, context):
        bpy.ops.screen.userpref_show('INVOKE_DEFAULT', section='EXTENSIONS')
        return {'FINISHED'}


class ROADLAB_PT_updates(bpy.types.Panel):
    bl_label = 'Updates'
    bl_idname = 'ROADLAB_PT_updates'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RoadLab'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        repo = repository(context)
        if repo:
            self.layout.prop(repo, 'use_sync_on_startup', text='Check at startup')
            from .RoadLab import bl_info
            self.layout.label(text='Installed version: ' + '.'.join(map(str, bl_info['version'])))
            self.layout.operator('roadlab.open_updates', icon='FILE_REFRESH')
        else:
            self.layout.operator('roadlab.configure_updates', icon='URL')
        self.layout.label(text='Apply updates in Get Extensions')


classes = (ROADLAB_OT_configure_updates, ROADLAB_OT_open_updates, ROADLAB_PT_updates)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
