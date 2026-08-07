"""
End-to-end install test: installs kennys_animation_picker.zip through
bpy.ops.preferences.addon_install (the same flow as Edit > Preferences >
Add-ons > Install from Disk), enables it, and verifies registration + basic
operations. Run headless with bpy 5.2.0.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy

ZIP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "kennys_animation_picker.zip")
MODULE = "kennys_animation_picker"

PASS = FAIL = 0
FAILURES = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        FAILURES.append(name)
        print("  FAIL %s  %s" % (name, detail))


print("== 1. addon_install (ZIP) ==")
assert os.path.isfile(ZIP), "zip not found: %s" % ZIP
bpy.ops.preferences.addon_install(filepath=ZIP, overwrite=True)
check("install executed", True)

installed_dir = os.path.join(bpy.utils.script_path_user(), "addons", MODULE)
check("installed folder exists", os.path.isdir(installed_dir), installed_dir)
check("installed __init__.py exists",
      os.path.isfile(os.path.join(installed_dir, "__init__.py")))
check("installed README exists",
      os.path.isfile(os.path.join(installed_dir, "README.md")))

print("== 2. addon_enable ==")
mod = bpy.ops.preferences.addon_enable(module=MODULE)
print("    addon_enable result:", mod)
check("addon enabled", MODULE in bpy.context.preferences.addons)

import addon_utils
import importlib
bl_info2 = addon_utils.module_bl_info(importlib.import_module(MODULE))
check("bl_info parsed", bl_info2 is not None)
check("bl_info name", bl_info2.get("name") == "Kenny's Animation Picker")
check("bl_info blender", bl_info2.get("blender") == (5, 2, 0))

print("== 3. registration ==")
check("operator kapp.add_rig", hasattr(bpy.ops, "kapp") and hasattr(bpy.ops.kapp, "add_rig"))
check("operator kapp.save_json", hasattr(bpy.ops.kapp, "save_json"))
check("operator kapp.load_json", hasattr(bpy.ops.kapp, "load_json"))
check("operator kapp.mirror_selection", hasattr(bpy.ops.kapp, "mirror_selection"))
check("modal operator registered", hasattr(bpy.ops.view3d, "kapp_picker_modal"))
check("panel registered", hasattr(bpy.types, "VIEW3D_PT_kapp_picker"))
panel = bpy.types.VIEW3D_PT_kapp_picker
check("panel bl_category Picker", panel.bl_category == "Picker")
check("panel space VIEW_3D", panel.bl_space_type == 'VIEW_3D')
check("panel region UI", panel.bl_region_type == 'UI')
scene = bpy.context.scene
for prop in ("kapp_enabled", "kapp_edit_mode", "kapp_rig_enum", "kapp_tab_enum",
             "kapp_bg_path", "kapp_btn_bone", "kapp_btn_color", "kapp_json_path"):
    check("scene prop %s" % prop, hasattr(scene, prop))

print("== 4. toggle + operators (headless) ==")
import kennys_animation_picker as kapp
scene.kapp_enabled = True
check("state enabled", kapp._state.enabled is True)
check("draw handler added (headless ok)", kapp._state.draw_handle is not None)
scene.kapp_enabled = False
check("state disabled", kapp._state.enabled is False)
check("draw handler removed", kapp._state.draw_handle is None)

r = bpy.ops.kapp.add_rig()
check("add_rig executed", r == {'FINISHED'})
check("two rigs now", len(kapp._state.data.rigs) == 2)
r = bpy.ops.kapp.add_tab()
check("add_tab executed", r == {'FINISHED'})
tab = kapp.current_tab()
check("new tab exists", tab is not None)
tab.buttons.append(kapp.ButtonData("btn01", "head", "rect", 10, 10, 40, 40))
kapp._sync_scene(scene)
r = bpy.ops.kapp.save_json(filepath="/tmp/kapp_inst_test.json")
check("save_json executed", r == {'FINISHED'})
check("json file written", os.path.isfile("/tmp/kapp_inst_test.json"))
r = bpy.ops.kapp.load_json(filepath="/tmp/kapp_inst_test.json")
check("load_json executed", r == {'FINISHED'})
check("loaded rig name", kapp._state.data.rigs[0].rig_name == "Rig")

print("== 5. register/unregister cycle ==")
mod = bpy.ops.preferences.addon_disable(module=MODULE)
check("addon disabled", MODULE not in bpy.context.preferences.addons)
check("props removed", not hasattr(bpy.context.scene, "kapp_enabled"))
mod = bpy.ops.preferences.addon_enable(module=MODULE)
check("re-enabled", MODULE in bpy.context.preferences.addons)
check("props re-registered", hasattr(bpy.context.scene, "kapp_enabled"))

print("\n%s passed, %s failed" % (PASS, FAIL))
if FAIL:
    print("failures:", FAILURES)
    sys.exit(1)
print("INSTALL TEST OK")
