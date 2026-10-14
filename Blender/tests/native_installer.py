import bpy,addon_utils,pathlib,sys,os
root=pathlib.Path(__file__).parent
result=bpy.ops.preferences.addon_install(filepath=os.environ.get('WB_TEST_ADDON_ZIP',str(root.parent/'Dist/WB_TrackTools_Additive_v082.zip')),overwrite=True)
assert result=={'FINISHED'},result
result=bpy.ops.preferences.addon_enable(module='WB_TrackTools');assert result=={'FINISHED'},result
assert addon_utils.check('WB_TrackTools')[1]
from WB_TrackTools import native_layers as layers
assert bpy.app.timers.is_registered(layers.deferred_upgrade)
assert layers.deferred_upgrade() is None
result=bpy.ops.preferences.addon_disable(module='WB_TrackTools');assert result=={'FINISHED'},result
assert not bpy.app.timers.is_registered(layers.deferred_upgrade)
result=bpy.ops.preferences.addon_enable(module='WB_TrackTools');assert result=={'FINISHED'},result
assert addon_utils.check('WB_TrackTools')[1]
assert bpy.app.timers.is_registered(layers.deferred_upgrade)
assert layers.deferred_upgrade() is None
bpy.ops.preferences.addon_disable(module='WB_TrackTools')
print('ACTUAL_INSTALL_ENABLE_DISABLE_REENABLE_PASS',flush=True)
