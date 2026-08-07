"""
Logic / integration tests for Kenny's Animation Picker, run headless on
bpy 5.2.0 (PyPI wheel).  Plain asserts + summary; exit code 0 on success.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kennys_animation_picker"))
import kennys_animation_picker as kapp

from tests.helpers import make_test_png, new_test_armature

PASS = 0
FAIL = 0
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


def section(title):
    print("\n== %s ==" % title)


# ---------------------------------------------------------------- helpers ---
def reset_state():
    kapp._state = kapp._PickerState()
    kapp._state.data.ensure_default()
    kapp._gpu_res.tex_shader = None
    kapp._gpu_res.color_shader = None
    return kapp._state


# ---------------------------------------------------------------- bl_info ---
section("bl_info")
check("bl_info name", kapp.bl_info["name"] == "Kenny's Animation Picker")
check("bl_info blender 5.2.0", kapp.bl_info["blender"] == (5, 2, 0))
check("bl_info category Animation", kapp.bl_info["category"] == "Animation")
check("bl_info version", kapp.bl_info["version"] == (1, 0, 0))

# ---------------------------------------------------------------- mirror ----
section("mirror_bone_name (standard naming auto-detection)")
cases = [
    ("arm_L", "arm_R"),
    ("arm_R", "arm_L"),
    ("head.L", "head.R"),
    ("head.R", "head.L"),
    ("leg.l", "leg.r"),
    ("leg.r", "leg.l"),
    ("hand_L.001", "hand_R.001"),
    ("hand_R.001", "hand_L.001"),
    ("earLeft", "earRight"),
    ("earRight", "earLeft"),
    ("jaw", None),
    ("spine", None),
    ("", None),
    ("tongue", None),
    ("head", None),
    ("thumb_L.003", "thumb_R.003"),
]
for src, exp in cases:
    got = kapp.mirror_bone_name(src)
    check("mirror(%s) -> %s" % (src, exp), got == exp, "got %r" % got)

# ---------------------------------------------------------------- JSON ------
section("JSON round-trip")
st = reset_state()
st.data.rigs = [
    kapp.RigData("Anby", [
        kapp.TabData("front", "/tmp/picker_front.jpg", "BL", 1.0, 5.0, -3.0, 0.8,
                     [kapp.ButtonData("head", "head", "rect", 100, 50, 40, 40, "#88cc44", "HEAD"),
                      kapp.ButtonData("handL", "hand_L", "circle", 10, 20, 30, 30, "#ff0000", "")]),
        kapp.TabData("back", "/tmp/picker_back.jpg", "TR", 0.5, 0.0, 0.0, 1.0, []),
    ]),
    kapp.RigData("Rig2", [kapp.TabData("front", "", "BL", 1.0, 0, 0, 1.0,
                                       [kapp.ButtonData("b1", "bone1")])]),
]
j = st.data.to_json()
check("to_json is str", isinstance(j, str))
d2 = kapp.PickerData.from_json(j)
check("round-trip rig count", len(d2.rigs) == 2)
check("round-trip rig name", d2.rigs[0].rig_name == "Anby")
check("round-trip tab count", len(d2.rigs[0].tabs) == 2)
tab0 = d2.rigs[0].tabs[0]
check("round-trip bg path", tab0.bg_image == "/tmp/picker_front.jpg")
check("round-trip anchor", tab0.anchor == "BL")
check("round-trip offsets", (tab0.image_offset_x, tab0.image_offset_y) == (5.0, -3.0))
check("round-trip opacity", abs(tab0.image_opacity - 0.8) < 1e-6)
check("round-trip buttons", len(tab0.buttons) == 2)
b0 = tab0.buttons[0]
check("round-trip button fields", (b0.id, b0.bone, b0.shape, b0.x, b0.y, b0.w, b0.h, b0.color) ==
      ("head", "head", "rect", 100.0, 50.0, 40.0, 40.0, "#88cc44"))
check("round-trip circle shape", tab0.buttons[1].shape == "circle")
check("round-trip label", tab0.buttons[0].label == "HEAD")

# 簡易フォーマット (開発指示書の例) の読み込み
simple = '''{
  "rig_name": "Anby",
  "background_image": "C:/path/to/picker_front.jpg",
  "buttons": [
    {"id": "head", "bone": "head", "shape": "rect", "x": 100, "y": 50, "w": 40, "h": 40, "color": "#88cc44"}
  ]
}'''
d3 = kapp.PickerData.from_json(simple)
check("simple format: 1 rig", len(d3.rigs) == 1)
check("simple format: rig name", d3.rigs[0].rig_name == "Anby")
check("simple format: tab 'front'", d3.rigs[0].tabs[0].name == "front")
check("simple format: bg path", d3.rigs[0].tabs[0].bg_image == "C:/path/to/picker_front.jpg")
check("simple format: 1 button", len(d3.rigs[0].tabs[0].buttons) == 1)
check("simple format: button bone", d3.rigs[0].tabs[0].buttons[0].bone == "head")

# 不正 JSON
try:
    kapp.PickerData.from_json("{not json")
    check("invalid json raises", False)
except ValueError:
    check("invalid json raises", True)

# ---------------------------------------------------------------- layout ----
section("layout math (hit-test / coordinates)")
st = reset_state()
st.img_size = (256.0, 256.0)
tab = st.data.rigs[0].tabs[0]
tab.image_scale = 1.0
tab.image_offset_x = 100.0
tab.image_offset_y = 50.0
tab.buttons = [
    kapp.ButtonData("a", "arm_L", "rect", 10, 10, 40, 40),
    kapp.ButtonData("b", "arm_R", "circle", 100, 100, 40, 40),
]
RW, RH = 1200, 800
ox, oy = kapp.tab_origin(tab, RW, RH)
check("origin BL", (ox, oy) == (100.0, 50.0))
x0, y0, x1, y1 = kapp.picker_rect(tab, RW, RH)
check("picker rect", (x0, y0, x1, y1) == (100.0, 50.0, 356.0, 306.0))

# ボタン a: 画像 (10,10)-(50,50) → region (110,60)-(150,100)
check("hit a center", kapp.hit_test(tab, RW, RH, 130, 80) == "a")
check("hit a corner inside", kapp.hit_test(tab, RW, RH, 111, 61) == "a")
check("miss (gap)", kapp.hit_test(tab, RW, RH, 160, 80) is None)
# ボタン b: circle 画像 (100,100) w=40 → region rect (200,150)-(240,190), 中心 (220,170)
check("hit b center", kapp.hit_test(tab, RW, RH, 220, 170) == "b")
check("circle corner (outside ellipse)", kapp.hit_test(tab, RW, RH, 239, 189) is None)
check("circle edge", kapp.hit_test(tab, RW, RH, 240, 170) == "b")
check("outside picker rect", kapp.hit_test(tab, RW, RH, 400, 400) is None)

# region_to_image
img = kapp.region_to_image(tab, RW, RH, 130, 80)
check("region_to_image", img is not None and abs(img[0] - 30) < 1e-6 and abs(img[1] - 30) < 1e-6)
check("region_to_image outside", kapp.region_to_image(tab, RW, RH, 10, 10) is None)

# アンカー変更
tab.anchor = "TR"
ox, oy = kapp.tab_origin(tab, RW, RH)
check("origin TR", (round(ox), round(oy)) == (1200 - 100 - 256, 800 - 50 - 256))

# ---------------------------------------------------------------- image ----
section("background texture (Image datablock + GPUTexture)")

class _FakeGPUTexture:
    _created = []

    def __init__(self, **kw):
        self.__dict__.update(kw)
        _FakeGPUTexture._created.append(kw)

_orig_gpu_texture = kapp.gpu.types.GPUTexture
kapp.gpu.types.GPUTexture = _FakeGPUTexture

png = make_test_png("/tmp/kapp_test_bg.png", 64, 48)
tab.bg_image = png
tex, size = kapp.load_background_texture(tab)
check("texture created", tex is not None)
check("img size from file", size == (64.0, 48.0))
check("img_size cached", st.img_size == (64.0, 48.0))
tex2, size2 = kapp.load_background_texture(tab)
check("texture cached (same key)", tex2 is tex)
# パス欠落
tab.bg_image = "/nonexistent/missing.png"
tex3, size3 = kapp.load_background_texture(tab)
check("missing file -> None", tex3 is None)
tab.bg_image = ""
kapp.gpu.types.GPUTexture = _orig_gpu_texture  # 復元

# ---------------------------------------------------------------- selection -
section("bone selection on real armature (Blender 5.2 PoseBone.select)")
obj = new_test_armature()
arm = obj.data
pb = obj.pose.bones
check("pose bones exist", len(pb) == 17)
check("PoseBone.select exists (5.2 API)",
      "select" in [p.identifier for p in bpy.types.PoseBone.bl_rna.properties])

def selected_names():
    return sorted(p.name for p in pb if p.select)

# replace selection
ctx = bpy.context
res = kapp.apply_click_selection(ctx, obj, "arm_L", "replace")
check("click replace ok", res is True)
sel = selected_names()
check("replace selects only arm_L", sel == ["arm_L"], "got %r" % sel)
check("active bone set", obj.data.bones.active is not None and obj.data.bones.active.name == "arm_L")

# shift/toggle
kapp.apply_click_selection(ctx, obj, "arm_R", "toggle")
sel = selected_names()
check("toggle adds arm_R", sel == ["arm_L", "arm_R"])
kapp.apply_click_selection(ctx, obj, "arm_L", "toggle")
sel = selected_names()
check("toggle removes arm_L", sel == ["arm_R"])

# ctrl/remove
kapp.apply_click_selection(ctx, obj, "arm_R", "remove")
sel = selected_names()
check("remove clears", sel == [])

# select_all / invert / deselect_all via utility
kapp.apply_utility(ctx, obj, "select_all")
check("select all", len(selected_names()) == len(pb))
kapp.apply_utility(ctx, obj, "invert")
check("invert (all->none)", len(selected_names()) == 0)
kapp.apply_utility(ctx, obj, "select_all")
kapp.apply_utility(ctx, obj, "deselect_all")
check("deselect all", len(selected_names()) == 0)

# mirror selection
kapp.apply_click_selection(ctx, obj, "arm_L", "replace")
kapp.apply_utility(ctx, obj, "mirror")
sel = selected_names()
check("mirror adds arm_R", sel == ["arm_L", "arm_R"])

kapp.apply_utility(ctx, obj, "deselect_all")
kapp.apply_click_selection(ctx, obj, "hand_L.001", "replace")
kapp.apply_utility(ctx, obj, "mirror")
check("mirror with digits suffix", pb["hand_R.001"].select)

kapp.apply_utility(ctx, obj, "deselect_all")
kapp.apply_click_selection(ctx, obj, "earLeft", "replace")
kapp.apply_utility(ctx, obj, "mirror")
check("mirror Left/Right", pb["earRight"].select)

kapp.apply_utility(ctx, obj, "deselect_all")
kapp.apply_click_selection(ctx, obj, "head", "replace")
kapp.apply_utility(ctx, obj, "mirror")
sel = selected_names()
check("mirror with no counterpart leaves selection", sel == ["head"])

# ---------------------------------------------------------------- state -----
section("state / scene-prop sync")
kapp.unregister_properties()
kapp.register_properties()
st = reset_state()
scene = bpy.context.scene
# 構造変更 → sync
st.data.rigs.append(kapp.RigData("Second", [kapp.TabData("front")]))
st.active_rig = 1
kapp._sync_scene(scene)
check("sync rig enum", scene.kapp_rig_enum == "RIG_1")
check("sync rig name", scene.kapp_rig_name == "Second")
tab = st.data.rigs[1].tabs[0]
btn = kapp.ButtonData("btn01", "arm_L", "rect", 12, 34, 56, 78, "#112233", "L")
tab.buttons.append(btn)
st.selected_button_id = "btn01"
kapp._sync_scene(scene)
check("sync button fields", (scene.kapp_btn_id, scene.kapp_btn_bone, scene.kapp_btn_x,
                             scene.kapp_btn_y, scene.kapp_btn_w, scene.kapp_btn_h) ==
      ("btn01", "arm_L", 12.0, 34.0, 56.0, 78.0))
check("sync color hex->rgb", tuple(round(c, 2) for c in scene.kapp_btn_color) == (0.07, 0.13, 0.2))

# UI コールバック経由でボタン編集 (kapp_btn_bone 更新)
scene.kapp_btn_bone = "forearm_R"
check("update callback writes to state", btn.bone == "forearm_R")
scene.kapp_btn_x = 99.0
check("update callback x", abs(btn.x - 99.0) < 1e-6)
scene.kapp_btn_color = (1.0, 0.0, 0.0)
check("update callback color", btn.color == "#ff0000")
scene.kapp_btn_shape = "circle"
check("update callback shape", btn.shape == "circle")

# ---------------------------------------------------------------- toggle ----
section("enable/disable (draw handler lifecycle, headless)")
st = reset_state()
scene.kapp_enabled = True
check("enabled flag", st.enabled is True)
check("draw handler registered", st.draw_handle is not None)
scene.kapp_enabled = False
check("disabled flag", st.enabled is False)
check("draw handler removed", st.draw_handle is None)

# ---------------------------------------------------------------- summary --
print("\n%s passed, %s failed" % (PASS, FAIL))
if FAIL:
    print("failures:", FAILURES)
    sys.exit(1)
