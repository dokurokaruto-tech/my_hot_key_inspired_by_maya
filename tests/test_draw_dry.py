"""
Dry-run of the overlay draw path and the modal click-handling, headless.

The real `gpu` / `blf` modules can't execute without a GPU context, so they are
mocked *before* the addon is imported; the addon's Python logic (layout math,
hit-testing, selection, texture pipeline, modal state machine) runs for real.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "kennys_animation_picker"))

import bpy  # noqa: E402  (bpy の import は sys.modules['gpu'] を実モジュールで上書きする)

# ---------------------------------------------------------------- fakes -----
class FakeShader:
    def __init__(self, *a, **kw):
        self.calls = []
        self.bound = 0

    def bind(self):
        self.bound += 1
        self.calls.append(("bind",))

    def uniform_float(self, name, value):
        self.calls.append(("uniform_float", name, value))

    def uniform_sampler(self, name, tex):
        self.calls.append(("uniform_sampler", name, tex))


class FakeBatch:
    def __init__(self, mode, content):
        self.mode = mode
        self.content = content
        self.drawn = 0

    def draw(self, shader):
        self.drawn += 1


class FakeTypes:
    GPUShader = FakeShader
    GPUTexture = None  # patched later per-test

    class _Tex:
        pass


class FakeState:
    def __init__(self):
        self.blends = []

    def blend_get(self):
        return 'NONE'

    def blend_set(self, mode):
        self.blends.append(mode)


class FakeGPU:
    def __init__(self):
        self.types = FakeTypes()
        self.state = FakeState()


class FakeBLF:
    def __init__(self):
        self.calls = []

    def size(self, *a):
        self.calls.append(("size", a))

    def dimensions(self, *a):
        return (10.0, 10.0)

    def color(self, *a):
        self.calls.append(("color", a))

    def position(self, *a):
        self.calls.append(("position", a))

    def draw(self, *a):
        self.calls.append(("draw", a))


class FakeBatchModule:
    def __init__(self, batches):
        self.batches = batches

    def batch_for_shader(self, shader, mode, content):
        b = FakeBatch(mode, content)
        self.batches.append(b)
        return b


gpu_fake = FakeGPU()
blf_fake = FakeBLF()
batches = []
sys.modules['gpu'] = gpu_fake
sys.modules['blf'] = blf_fake
sys.modules['gpu_extras'] = type(sys)('gpu_extras')
sys.modules['gpu_extras.batch'] = FakeBatchModule(batches)
sys.modules['gpu_extras.presets'] = type(sys)('gpu_extras.presets')

import kennys_animation_picker as kapp  # noqa: E402 (fake gpu/blf を注入した後に import)

from tests.helpers import make_fake_context, make_test_png, new_test_armature

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


def section(title):
    print("\n== %s ==" % title)


def reset():
    kapp._state = kapp._PickerState()
    st = kapp._state
    st.data.ensure_default()
    kapp._gpu_res.tex_shader = None
    kapp._gpu_res.color_shader = None
    return st


# ================================================================ draw path ==
section("draw overlay (mocked gpu/blf)")

png = make_test_png("/tmp/kapp_draw_bg.png", 128, 96)

st = reset()
st.enabled = True
ctx = make_fake_context()
st.space = ctx.space_data
tab = kapp.current_tab()
tab.bg_image = png
tab.image_scale = 1.0
tab.buttons = [
    kapp.ButtonData("head", "head", "rect", 40, 40, 32, 32, "#88cc44", "HEAD"),
    kapp.ButtonData("handL", "hand_L", "circle", 80, 20, 24, 24, "#ff0000", "L"),
]
st.hover_id = "head"
st.selected_button_id = "handL"
st.edit_mode = True

class FakeTex:
    def __init__(self, **kw):
        self.__dict__.update(kw)

gpu_fake.types.GPUTexture = FakeTex
kapp.draw_picker_overlay(ctx, st)
check("draw completes without exception", True)
check("background texture drawn (TRI_FAN with uvs)", any(
    b.mode == 'TRI_FAN' and 'uvs' in b.content for b in batches))
check("filled rects drawn", any(
    b.mode == 'TRI_FAN' and 'uvs' not in b.content for b in batches))
check("circle drawn (many verts)", any(
    b.mode == 'TRI_FAN' and len(b.content['pos']) > 40 for b in batches))
check("line border drawn", any(b.mode == 'LINE_STRIP' for b in batches))
check("text drawn", any(c[0] == 'draw' for c in blf_fake.calls))
check("blend set", 'ALPHA' in gpu_fake.state.blends)

# 背景なしのプレースホルダ描画
batches.clear()
blf_fake.calls.clear()
st2 = reset()
st2.enabled = True
st2.space = ctx.space_data
kapp.draw_picker_overlay(ctx, st2)
check("placeholder draw ok", True)
check("placeholder rect drawn", len(batches) >= 2)

# オーナーでない空間では描画しない
batches.clear()
st3 = reset()
st3.enabled = True
st3.space = make_fake_context().space_data  # 別空間
kapp.draw_picker_overlay(ctx, st3)
check("skip draw for non-owner space", len(batches) == 0)

# _draw_callback: disabled → no-op
st3.enabled = False
batches.clear()
kapp._draw_callback(st3, ctx)
check("disabled callback no-op", len(batches) == 0)

# ================================================================ modal ======
section("modal click handling (fake events + real armature)")

obj = new_test_armature("Rig2")
st = reset()
st.enabled = True
st.edit_mode = False
st.space = ctx.space_data
tab = kapp.current_tab()
tab.image_scale = 1.0
tab.image_offset_x = 0.0
tab.image_offset_y = 0.0
tab.buttons = [
    kapp.ButtonData("btn_armL", "arm_L", "rect", 10, 10, 40, 40),
    kapp.ButtonData("btn_head", "head", "rect", 100, 100, 40, 40),
]

st.modal_op = "sentinel"  # ラッパーが CANCELLED 時に clearing する (ここでは直接関数をテスト)
reports = []


def handle(ctx, ev):
    return kapp.modal_handle_event(ctx, ev, report=lambda *a: reports.append(a))


class FakeEvent:
    def __init__(self, type, value, rx, ry, wx=None, wy=None, shift=False,
                 ctrl=False, alt=False):
        self.type = type
        self.value = value
        self.mouse_region_x = rx
        self.mouse_region_y = ry
        self.mouse_x = wx if wx is not None else rx
        self.mouse_y = wy if wy is not None else (800 - ry)
        self.shift = shift
        self.ctrl = ctrl
        self.alt = alt


class FakeViewLayer:
    objects = type("objs", (), {"active": None})()


def make_modal_context(arm_obj):
    c = make_fake_context()
    c.object = arm_obj
    c.mode = 'POSE'
    vl = FakeViewLayer()
    vl.objects.active = arm_obj
    c.view_layer = vl
    return c


mctx = make_modal_context(obj)
st.space = mctx.space_data  # オーナー空間を一致させる

# 通常クリック → replace 選択
r = handle(mctx, FakeEvent('LEFTMOUSE', 'PRESS', 30, 30))
check("press inside button -> RUNNING_MODAL", r == {'RUNNING_MODAL'})
r = handle(mctx, FakeEvent('LEFTMOUSE', 'RELEASE', 30, 30))
check("release -> RUNNING_MODAL", r == {'RUNNING_MODAL'})
sel = [p.name for p in obj.pose.bones if p.select]
check("click selects arm_L", sel == ['arm_L'], "got %r" % sel)

# Shift+クリック → トグル (解除)
r = handle(mctx, FakeEvent('LEFTMOUSE', 'PRESS', 30, 30, shift=True))
handle(mctx, FakeEvent('LEFTMOUSE', 'RELEASE', 30, 30, shift=True))
sel = [p.name for p in obj.pose.bones if p.select]
check("shift+click toggles off", sel == [])

# Shift+クリック → トグル (追加) もう一度
handle(mctx, FakeEvent('LEFTMOUSE', 'PRESS', 30, 30, shift=True))
handle(mctx, FakeEvent('LEFTMOUSE', 'RELEASE', 30, 30, shift=True))
sel = sorted(p.name for p in obj.pose.bones if p.select)
check("shift+click toggles on", sel == ['arm_L'])

# Ctrl+クリック → 除外
handle(mctx, FakeEvent('LEFTMOUSE', 'PRESS', 30, 30, ctrl=True))
handle(mctx, FakeEvent('LEFTMOUSE', 'RELEASE', 30, 30, ctrl=True))
sel = [p.name for p in obj.pose.bones if p.select]
check("ctrl+click removes", sel == [])

# ピッカー領域外クリック → PASS_THROUGH (ビューポート操作と競合しない)
r = handle(mctx, FakeEvent('LEFTMOUSE', 'PRESS', 500, 500))
check("outside rect -> PASS_THROUGH", r == {'PASS_THROUGH'})

# サイドバー領域 (WINDOW リージョン外) クリック → PASS_THROUGH
r = handle(mctx, FakeEvent('LEFTMOUSE', 'PRESS', 5, 5, wx=1300, wy=400))
check("sidebar click -> PASS_THROUGH", r == {'PASS_THROUGH'})

# 編集モード: 空き領域クリックで新規ボタン作成
st.edit_mode = True
n_buttons = len(tab.buttons)
handle(mctx, FakeEvent('LEFTMOUSE', 'PRESS', 300, 300))
handle(mctx, FakeEvent('LEFTMOUSE', 'RELEASE', 300, 300))
check("edit mode click creates button", len(tab.buttons) == n_buttons + 1)
new_btn = tab.buttons[-1]
check("new button selected", st.selected_button_id == new_btn.id)
# クリック (300,300) → ボタン中心がクリック位置: x = 300 - 32/2 = 284
check("new button at click pos", abs(new_btn.x - 284.0) < 2.0 and abs(new_btn.y - 284.0) < 2.0,
      "got %r, %r" % (new_btn.x, new_btn.y))

# 編集モード: ドラッグで移動
px, py, _px1, _py1 = kapp.button_region_rect(tab, 1200, 800, new_btn)
handle(mctx, FakeEvent('LEFTMOUSE', 'PRESS', px + 1, py + 1))
handle(mctx, FakeEvent('MOUSEMOVE', 'NOTHING', 350, 350))
r = handle(mctx, FakeEvent('LEFTMOUSE', 'RELEASE', 350, 350))
check("drag moves button", abs(new_btn.x - 334.0) < 2.0 and abs(new_btn.y - 334.0) < 2.0,
      "got %r, %r" % (new_btn.x, new_btn.y))

# 編集モード: 既存ボタンクリック → 選択
handle(mctx, FakeEvent('LEFTMOUSE', 'PRESS', 30, 30))
handle(mctx, FakeEvent('LEFTMOUSE', 'RELEASE', 30, 30))
check("edit click selects existing", st.selected_button_id == "btn_armL")

# ボーンが存在しないボタン → report が出る (クラッシュしない)
tab.buttons.append(kapp.ButtonData("btn_ghost", "no_such_bone", "rect", 10, 200, 40, 40))
st.edit_mode = False
handle(mctx, FakeEvent('LEFTMOUSE', 'PRESS', 30, 230))
handle(mctx, FakeEvent('LEFTMOUSE', 'RELEASE', 30, 230))
check("missing bone reports warning", any("ボーンが見つかりません" in str(r[1]) for r in reports))

# 無効化 → CANCELLED
st.enabled = False
r = handle(mctx, FakeEvent('MOUSEMOVE', 'NOTHING', 30, 30))
check("disabled -> CANCELLED", r == {'CANCELLED'})

# ================================================================ summary ==
print("\n%s passed, %s failed" % (PASS, FAIL))
if FAIL:
    print("failures:", FAILURES)
    sys.exit(1)
