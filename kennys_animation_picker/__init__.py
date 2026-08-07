# =============================================================================
#  Kenny's Animation Picker
#  ----------------------------------------------------------------------------
#  AnimSchool Picker 風のボーン選択ツール (Blender 5.2.x 用)
#
#  - 3D ビューポート上にインタラクティブ・オーバーレイとして表示
#    (SpaceView3D.draw_handler_add + gpu / gpu_extras / blf)
#  - 背景画像は外部ファイルパス参照方式 (JSON にパスを保存、埋め込みはしない)
#  - クリック可能なボタンで pose bone を選択
#    Shift+クリック = 追加選択 (トグル) / Ctrl+クリック = 除外選択
#  - 複数リグ / 複数タブ (front / back 等) の切替
#  - 全選択・反転選択・左右ミラー選択 (.L/.R 等の標準命名規則の自動検出)
#  - セーブデータは外部 JSON ファイル
#
#  レガシーアドオン形式 (bl_info + __init__.py)。
#  非推奨の bgl は使用せず、gpu + gpu_extras + blf のみを使用。
# =============================================================================

bl_info = {
    "name": "Kenny's Animation Picker",
    "author": "Kenny",
    "version": (1, 0, 0),
    "blender": (5, 2, 0),
    "location": "View3D > N-Panel > Picker",
    "description": "AnimSchool Picker風のボーン選択ツール (viewport overlay bone picker)",
    "category": "Animation",
}

import bpy
import os
import re
import json
import math
import traceback

import gpu
import blf
from gpu_extras.batch import batch_for_shader

# =============================================================================
# 定数 / デフォルト値
# =============================================================================

# 背景画像がない場合に使う仮想ピッカー領域サイズ (px)
DEFAULT_VIRTUAL_W = 640.0
DEFAULT_VIRTUAL_H = 640.0

# 新規作成ボタンのスクリーン上のサイズ (px)
DEFAULT_BUTTON_SCREEN_SIZE = 32.0

# JSON フォーマットバージョン
FORMAT_VERSION = 1

TOOL_NAME = "Kenny's Animation Picker"

# =============================================================================
# データモデル (JSON にシリアライズ可能)
# =============================================================================

_HEX_RE = re.compile(r'^#?([0-9a-fA-F]{6})$')


def _hex_to_rgba(hex_color, alpha=1.0):
    """'#88cc44' 等を (r, g, b, a) の 0..1 float タプルにする。"""
    m = _HEX_RE.match(hex_color or "")
    if not m:
        return (0.5, 0.5, 0.5, alpha)
    h = m.group(1)
    return (int(h[0:2], 16) / 255.0,
            int(h[2:4], 16) / 255.0,
            int(h[4:6], 16) / 255.0,
            alpha)


def _rgba_to_hex(rgba):
    """(r, g, b, a) 0..1 float → '#rrggbb'。"""
    return '#%02x%02x%02x' % (
        max(0, min(255, int(round(rgba[0] * 255.0)))),
        max(0, min(255, int(round(rgba[1] * 255.0)))),
        max(0, min(255, int(round(rgba[2] * 255.0)))))


class ButtonData:
    """ピッカー上の1ボタン。座標は背景画像(ピクセル)基準、原点は画像左下。"""

    __slots__ = ("id", "bone", "shape", "x", "y", "w", "h", "color", "label")

    def __init__(self, button_id="", bone="", shape="rect",
                 x=0.0, y=0.0, w=40.0, h=40.0, color="#88cc44", label=""):
        self.id = button_id
        self.bone = bone
        self.shape = shape if shape in ("rect", "circle") else "rect"
        self.x = float(x)
        self.y = float(y)
        self.w = float(w)
        self.h = float(h)
        self.color = color if _HEX_RE.match(color or "") else "#88cc44"
        self.label = label

    # -- JSON ---------------------------------------------------------------
    def to_dict(self):
        return {
            "id": self.id,
            "bone": self.bone,
            "shape": self.shape,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "w": round(self.w, 3),
            "h": round(self.h, 3),
            "color": self.color,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, d):
        d = d or {}
        return cls(
            button_id=str(d.get("id", "")),
            bone=str(d.get("bone", "")),
            shape=str(d.get("shape", "rect")),
            x=float(d.get("x", 0.0)),
            y=float(d.get("y", 0.0)),
            w=float(d.get("w", 40.0)),
            h=float(d.get("h", 40.0)),
            color=str(d.get("color", "#88cc44")),
            label=str(d.get("label", "")),
        )


class TabData:
    """front / back 等の1タブ。背景画像の設定とボタン群を持つ。"""

    __slots__ = ("name", "bg_image", "anchor", "image_scale",
                 "image_offset_x", "image_offset_y", "image_opacity", "buttons")

    def __init__(self, name="front", bg_image="", anchor="BL",
                 image_scale=1.0, image_offset_x=0.0, image_offset_y=0.0,
                 image_opacity=1.0, buttons=None):
        self.name = name
        self.bg_image = bg_image
        self.anchor = anchor if anchor in ("BL", "TL", "BR", "TR") else "BL"
        self.image_scale = float(image_scale)
        self.image_offset_x = float(image_offset_x)
        self.image_offset_y = float(image_offset_y)
        self.image_opacity = max(0.0, min(1.0, float(image_opacity)))
        self.buttons = list(buttons) if buttons else []

    def to_dict(self):
        return {
            "name": self.name,
            "background_image": self.bg_image,
            "anchor": self.anchor,
            "image_scale": round(self.image_scale, 4),
            "image_offset_x": round(self.image_offset_x, 3),
            "image_offset_y": round(self.image_offset_y, 3),
            "image_opacity": round(self.image_opacity, 4),
            "buttons": [b.to_dict() for b in self.buttons],
        }

    @classmethod
    def from_dict(cls, d):
        d = d or {}
        buttons = [ButtonData.from_dict(b) for b in d.get("buttons", [])]
        return cls(
            name=str(d.get("name", "front")),
            bg_image=str(d.get("background_image", "")),
            anchor=str(d.get("anchor", "BL")),
            image_scale=float(d.get("image_scale", 1.0)),
            image_offset_x=float(d.get("image_offset_x", 0.0)),
            image_offset_y=float(d.get("image_offset_y", 0.0)),
            image_opacity=float(d.get("image_opacity", 1.0)),
            buttons=buttons,
        )


class RigData:
    """1リグ = 複数タブ (front/back 等) の集合。"""

    __slots__ = ("rig_name", "tabs")

    def __init__(self, rig_name="Rig", tabs=None):
        self.rig_name = rig_name
        self.tabs = list(tabs) if tabs else []

    def to_dict(self):
        return {
            "rig_name": self.rig_name,
            "tabs": [t.to_dict() for t in self.tabs],
        }

    @classmethod
    def from_dict(cls, d):
        d = d or {}
        return cls(
            rig_name=str(d.get("rig_name", "Rig")),
            tabs=[TabData.from_dict(t) for t in d.get("tabs", [])],
        )


class PickerData:
    """アドオン全体のピッカーデータ (複数リグ)。"""

    __slots__ = ("format_version", "rigs")

    def __init__(self, rigs=None, format_version=FORMAT_VERSION):
        self.format_version = format_version
        self.rigs = list(rigs) if rigs else []

    # -- JSON ---------------------------------------------------------------
    def to_dict(self):
        return {
            "format_version": self.format_version,
            "tool": TOOL_NAME,
            "pickers": [r.to_dict() for r in self.rigs],
        }

    @classmethod
    def from_dict(cls, d):
        """厳密でないフォーマットも受け付ける寛容なパーサ。"""
        d = d or {}
        rigs = []
        raw_pickers = d.get("pickers")
        if isinstance(raw_pickers, list):
            for r in raw_pickers:
                if isinstance(r, dict):
                    rigs.append(RigData.from_dict(r))
        else:
            # 旧・簡易形式:
            #   {"rig_name": "...", "background_image": "...", "buttons": [...]}
            # 単一リグ + 単一タブとして解釈する。
            simple = {k: v for k, v in d.items()
                      if k in ("rig_name", "background_image", "anchor",
                               "image_scale", "image_offset_x",
                               "image_offset_y", "image_opacity",
                               "buttons", "tab_name")}
            if simple.get("rig_name") or "buttons" in simple:
                tab = {
                    "name": str(simple.get("tab_name", "front")),
                    "background_image": str(simple.get("background_image", "")),
                    "anchor": str(simple.get("anchor", "BL")),
                    "image_scale": simple.get("image_scale", 1.0),
                    "image_offset_x": simple.get("image_offset_x", 0.0),
                    "image_offset_y": simple.get("image_offset_y", 0.0),
                    "image_opacity": simple.get("image_opacity", 1.0),
                    "buttons": simple.get("buttons", []),
                }
                rig = {"rig_name": str(simple.get("rig_name", "Rig")),
                       "tabs": [tab]}
                rigs.append(RigData.from_dict(rig))

        if not rigs:
            rigs = [RigData()]
        return cls(rigs=rigs)

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, text):
        try:
            d = json.loads(text)
        except Exception:
            raise ValueError("JSON のパースに失敗しました")
        return cls.from_dict(d)

    def ensure_default(self):
        """常に最低1リグ・1タブを保証する。"""
        if not self.rigs:
            self.rigs = [RigData()]
        for r in self.rigs:
            if not r.tabs:
                r.tabs = [TabData()]


# =============================================================================
# 左右ミラー命名規則の自動検出
# =============================================================================

# 優先順位: .L/.R (Blender 標準) → _L/_R → _l/_r → Left/Right → left/right
# 置換文字列はセパレータ込み (例: "_L" -> "_R")。
_MIRROR_PATTERNS = [
    (re.compile(r'^(?P<base>.*)\.L(?P<digits>\.\d+)?$'), ".R"),
    (re.compile(r'^(?P<base>.*)\.R(?P<digits>\.\d+)?$'), ".L"),
    (re.compile(r'^(?P<base>.*)\.l(?P<digits>\.\d+)?$'), ".r"),
    (re.compile(r'^(?P<base>.*)\.r(?P<digits>\.\d+)?$'), ".l"),
    (re.compile(r'^(?P<base>.*)_L(?P<digits>\.\d+)?$'), "_R"),
    (re.compile(r'^(?P<base>.*)_R(?P<digits>\.\d+)?$'), "_L"),
    (re.compile(r'^(?P<base>.*)_l(?P<digits>\.\d+)?$'), "_r"),
    (re.compile(r'^(?P<base>.*)_r(?P<digits>\.\d+)?$'), "_l"),
    (re.compile(r'^(?P<base>.*)Left(?P<digits>\.\d+)?$'), "Right"),
    (re.compile(r'^(?P<base>.*)Right(?P<digits>\.\d+)?$'), "Left"),
    (re.compile(r'^(?P<base>.*)left(?P<digits>\.\d+)?$'), "right"),
    (re.compile(r'^(?P<base>.*)right(?P<digits>\.\d+)?$'), "left"),
]


def mirror_bone_name(name):
    """ボーン名から左右ミラー名を返す。対応する規則が無ければ None。

    例:  arm_L  -> arm_R
         head.L -> head.R
         leg_L.001 -> leg_R.001
         forearmLeft -> forearmRight
    """
    if not name:
        return None
    for rx, repl in _MIRROR_PATTERNS:
        m = rx.match(name)
        if m:
            return m.group("base") + repl + (m.group("digits") or "")
    return None


# =============================================================================
# ランタイム状態 (シングルトン)
# =============================================================================


class _PickerState:
    __slots__ = ("data", "active_rig", "active_tab", "enabled", "edit_mode",
                 "hover_id", "selected_button_id", "pressed", "press_pos",
                 "dragging_id", "space", "draw_handle", "modal_op",
                 "cancel_requested", "tex_key", "texture", "img_size",
                 "json_path", "_syncing")

    def __init__(self):
        self.data = PickerData()
        self.data.ensure_default()
        self.active_rig = 0
        self.active_tab = 0
        self.enabled = False
        self.edit_mode = False
        self.hover_id = None
        self.selected_button_id = None
        self.pressed = False
        self.press_pos = None
        self.dragging_id = None
        self.space = None            # SpaceView3D (オーナー)
        self.draw_handle = None
        self.modal_op = None         # 実行中の modal operator インスタンス
        self.cancel_requested = False
        self.tex_key = None          # (path, mtime) -> GPUTexture キャッシュ
        self.texture = None
        self.img_size = None
        self.json_path = ""
        self._syncing = False


_state = _PickerState()


def get_state():
    return _state


def current_rig():
    st = _state
    if 0 <= st.active_rig < len(st.data.rigs):
        return st.data.rigs[st.active_rig]
    return None


def current_tab():
    rig = current_rig()
    if rig is None:
        return None
    if not rig.tabs:
        rig.tabs.append(TabData())
    if 0 <= st_active_tab() < len(rig.tabs):
        return rig.tabs[st_active_tab()]
    return rig.tabs[0]


def st_active_tab():
    return _state.active_tab


def current_button(button_id=None):
    """アクティブタブ内のボタンを取得。button_id 省略時は選択中ボタン。"""
    tab = current_tab()
    if tab is None:
        return None
    bid = button_id if button_id is not None else _state.selected_button_id
    for b in tab.buttons:
        if b.id == bid:
            return b
    return None


# =============================================================================
# 画像パス解決 & GPU テクスチャ
# =============================================================================

def resolve_bg_path(tab, base_dir=None):
    """外部パス参照: 絶対パス or JSON/Blend ファイル基準の相対パスを解決。"""
    p = (tab.bg_image or "").strip()
    if not p:
        return None
    if os.path.isabs(p):
        return p if os.path.isfile(p) else None
    candidates = []
    if base_dir:
        candidates.append(os.path.join(base_dir, p))
    blend = bpy.data.filepath
    if blend:
        candidates.append(os.path.join(os.path.dirname(blend), p))
    candidates.append(os.path.join(os.getcwd(), p))
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def load_background_texture(tab, base_dir=None):
    """Image データブロック (外部パス) + gpu.types.GPUTexture を生成。

    ファイルの変更時刻でキャッシュを無効化し、変更時のみ再生成する。
    画像は読み込めない場合 None を返す (呼び出し側でプレースホルダ表示)。
    """
    st = _state
    path = resolve_bg_path(tab, base_dir)
    if not path:
        return None, None
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None, None

    key = (path, mtime)
    if st.tex_key == key and st.texture is not None and st.img_size is not None:
        return st.texture, st.img_size

    img = bpy.data.images.load(path, check_existing=True)
    w, h = img.size
    if not w or not h:
        return None, None

    # pixels: 左上原点の RGBA float 列 -> 左下原点の RGBA8 bytes に変換
    pixels = img.pixels  # w*h*4 個の float
    buf = bytearray(w * h * 4)
    row_bytes = w * 4
    i = 0
    for row in range(h):          # 画像の上から下へ
        src_row = (h - 1 - row)   # テクスチャの下 (v=0) に画像の下が来るよう反転
        base = src_row * row_bytes
        for col in range(row_bytes):
            v = pixels[base + col]
            if v <= 0.0:
                buf[i] = 0
            elif v >= 1.0:
                buf[i] = 255
            else:
                buf[i] = int(v * 255.0)
            i += 1

    tex = gpu.types.GPUTexture(size=(w, h), format='RGBA8', data=bytes(buf))
    st.tex_key = key
    st.texture = tex
    st.img_size = (float(w), float(h))
    return tex, st.img_size


# =============================================================================
# レイアウト計算 (テスト可能な純ロジック)
# =============================================================================

def tab_image_size(tab):
    """表示する画像/仮想領域の (w, h) を返す。"""
    st = _state
    if st.img_size is not None:
        return st.img_size
    return (DEFAULT_VIRTUAL_W, DEFAULT_VIRTUAL_H)


def _safe_scale(tab):
    return max(tab.image_scale, 0.01)


def tab_origin(tab, region_w, region_h):
    """アンカーとオフセットから、画像領域の左下原点 (region px) を返す。"""
    iw, ih = tab_image_size(tab)
    s = _safe_scale(tab)
    sw = iw * s
    sh = ih * s
    ox = tab.image_offset_x
    oy = tab.image_offset_y
    if tab.anchor == "TL":
        return (ox, region_h - oy - sh)
    if tab.anchor == "BR":
        return (region_w - ox - sw, oy)
    if tab.anchor == "TR":
        return (region_w - ox - sw, region_h - oy - sh)
    return (ox, oy)  # BL


def picker_rect(tab, region_w, region_h):
    """画像領域の (x0, y0, x1, y1) を region px で返す。"""
    iw, ih = tab_image_size(tab)
    ox, oy = tab_origin(tab, region_w, region_h)
    s = _safe_scale(tab)
    return (ox, oy, ox + iw * s, oy + ih * s)


def region_to_image(tab, region_w, region_h, mx, my):
    """region px → 画像座標 (画像px, 原点左下)。領域外は None。"""
    x0, y0, x1, y1 = picker_rect(tab, region_w, region_h)
    if not (x0 <= mx <= x1 and y0 <= my <= y1):
        return None
    s = _safe_scale(tab)
    return ((mx - x0) / s, (my - y0) / s)


def button_region_rect(tab, region_w, region_h, btn):
    """ボタンの region px 矩形 (x0, y0, x1, y1)。"""
    ox, oy = tab_origin(tab, region_w, region_h)
    s = _safe_scale(tab)
    return (ox + btn.x * s, oy + btn.y * s,
            ox + (btn.x + btn.w) * s, oy + (btn.y + btn.h) * s)


def hit_test(tab, region_w, region_h, mx, my):
    """(mx, my) がヒットするボタン id を返す。無ければ None。"""
    if tab is None:
        return None
    x0, y0, x1, y1 = picker_rect(tab, region_w, region_h)
    if not (x0 <= mx <= x1 and y0 <= my <= y1):
        return None
    # 後に描画されたボタンが上に来る → 逆順で判定
    for btn in reversed(tab.buttons):
        bx0, by0, bx1, by1 = button_region_rect(tab, region_w, region_h, btn)
        if mx < bx0 or mx > bx1 or my < by0 or my > by1:
            continue
        if btn.shape == "circle":
            cx = (bx0 + bx1) * 0.5
            cy = (by0 + by1) * 0.5
            rx = (bx1 - bx0) * 0.5
            ry = (by1 - by0) * 0.5
            if rx > 0.0 and ry > 0.0:
                dx = (mx - cx) / rx
                dy = (my - cy) / ry
                if dx * dx + dy * dy > 1.0:
                    continue
        return btn.id
    return None


# =============================================================================
# シーン表示まわり (3D view の再描画)
# =============================================================================

def redraw_3d(context):
    screen = getattr(context, "screen", None)
    if screen is None:
        try:
            screen = bpy.context.screen
        except Exception:
            return
    if screen is None:
        return
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


# =============================================================================
# シェーダ / 描画 (gpu + gpu_extras + blf。bgl は不使用)
# =============================================================================

_TEX_VERT = """
in vec2 pos;
in vec2 uvs;
out vec2 uvs_flat;
void main() {
    gl_Position = vec4(pos, 0.0, 1.0);
    uvs_flat = uvs;
}
"""

_TEX_FRAG = """
uniform sampler2D image;
uniform vec4 color;
in vec2 uvs_flat;
out vec4 fragColor;
void main() {
    vec4 tex = texture(image, uvs_flat);
    fragColor = tex * color;
}
"""

_COLOR_VERT = """
in vec2 pos;
void main() {
    gl_Position = vec4(pos, 0.0, 1.0);
}
"""

_COLOR_FRAG = """
uniform vec4 color;
out vec4 fragColor;
void main() {
    fragColor = color;
}
"""


class _GpuResources:
    """シェーダ等の GPU リソースを遅延生成・保持する。"""

    __slots__ = ("tex_shader", "color_shader")

    def __init__(self):
        self.tex_shader = None
        self.color_shader = None

    def get_tex_shader(self):
        if self.tex_shader is None:
            self.tex_shader = gpu.types.GPUShader(_TEX_VERT, _TEX_FRAG)
        return self.tex_shader

    def get_color_shader(self):
        if self.color_shader is None:
            self.color_shader = gpu.types.GPUShader(_COLOR_VERT, _COLOR_FRAG)
        return self.color_shader


_gpu_res = _GpuResources()


def _ndc(region_w, region_h, x, y):
    return (x / (region_w * 0.5) - 1.0, y / (region_h * 0.5) - 1.0)


def _draw_rect_ndc(region_w, region_h, x0, y0, x1, y1):
    """region px 矩形 → NDC 頂点 (反時計回り quad)。"""
    ax, ay = _ndc(region_w, region_h, x0, y0)
    bx, by = _ndc(region_w, region_h, x1, y0)
    cx, cy = _ndc(region_w, region_h, x1, y1)
    dx, dy = _ndc(region_w, region_h, x0, y1)
    return [ax, ay, bx, by, cx, cy, dx, dy]


def _draw_filled_rect(region_w, region_h, x0, y0, x1, y1, rgba):
    if x1 - x0 < 0.5 or y1 - y0 < 0.5:
        return
    shader = _gpu_res.get_color_shader()
    coords = _draw_rect_ndc(region_w, region_h, x0, y0, x1, y1)
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": coords})
    shader.bind()
    shader.uniform_float("color", rgba)
    batch.draw(shader)


def _draw_circle(region_w, region_h, cx, cy, rx, ry, rgba, segments=48):
    if rx < 0.5 or ry < 0.5:
        return
    shader = _gpu_res.get_color_shader()
    ncx, ncy = _ndc(region_w, region_h, cx, cy)
    # rx/ry は NDC に変換 (x と y でスケールが異なるので個別変換)
    rx0, _ = _ndc(region_w, region_h, cx + rx, cy)
    _, ry0 = _ndc(region_w, region_h, cx, cy + ry)
    rx = rx0 - ncx
    ry = ry0 - ncy
    coords = [(ncx, ncy)]
    for i in range(segments + 1):
        a = i / segments * math.pi * 2.0
        coords.append((ncx + math.cos(a) * rx, ncy + math.sin(a) * ry))
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": coords})
    shader.bind()
    shader.uniform_float("color", rgba)
    batch.draw(shader)


def _draw_line_rect(region_w, region_h, x0, y0, x1, y1, rgba):
    shader = _gpu_res.get_color_shader()
    coords = _draw_rect_ndc(region_w, region_h, x0, y0, x1, y1)
    coords = coords + coords[0:2]  # 閉じる
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": coords})
    shader.bind()
    shader.uniform_float("color", rgba)
    batch.draw(shader)


def _draw_image_texture(region_w, region_h, tab, tex):
    """背景画像をテクスチャ付き quad で描画。"""
    x0, y0, x1, y1 = picker_rect(tab, region_w, region_h)
    shader = _gpu_res.get_tex_shader()
    pos = _draw_rect_ndc(region_w, region_h, x0, y0, x1, y1)
    uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": pos, "uvs": uvs})
    shader.bind()
    shader.uniform_sampler("image", tex)
    shader.uniform_float("color", (1.0, 1.0, 1.0, tab.image_opacity))
    batch.draw(shader)


def _draw_text(region_w, region_h, x, y, size, rgba, text, centered=False):
    if not text:
        return
    try:
        blf.size(0, size, 72)
        if centered:
            tw, th = blf.dimensions(0, text)
            x -= tw * 0.5
            y -= th * 0.5
        blf.color(0, rgba[0], rgba[1], rgba[2], rgba[3])
        blf.position(0, x, y, 0)
        blf.draw(0, text)
    except Exception:
        pass


def _button_display_label(btn):
    return (btn.label or btn.id or btn.bone) or "?"


def draw_picker_overlay(context, state):
    """POST_PIXEL ドローハンドラ本体。エラーはログに残し描画を継続する。"""
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    if area is None or region is None:
        return
    if region.type != 'WINDOW':
        return
    # オーナー空間のときだけ描画
    if state.space is not None:
        try:
            if context.space_data is None or context.space_data != state.space:
                return
        except ReferenceError:
            return

    region_w = region.width
    region_h = region.height
    if region_w <= 0 or region_h <= 0:
        return

    tab = current_tab()
    if tab is None:
        return

    prev_blend = gpu.state.blend_get()
    gpu.state.blend_set('ALPHA')
    try:
        _draw_overlay_content(region_w, region_h, tab, state)
    finally:
        try:
            gpu.state.blend_set(prev_blend)
        except Exception:
            pass


def _draw_overlay_content(region_w, region_h, tab, state):
    """描画本体 (ブレンド状態は呼び出し側で設定済み)。"""
    tex, img_size = load_background_texture(tab)

    if tex is not None:
        _draw_image_texture(region_w, region_h, tab, tex)
    else:
        # プレースホルダ: 半透明グレーのピッカー領域
        x0, y0, x1, y1 = picker_rect(tab, region_w, region_h)
        _draw_filled_rect(region_w, region_h, x0, y0, x1, y1, (0.12, 0.12, 0.14, 0.55))
        _draw_line_rect(region_w, region_h, x0, y0, x1, y1, (1.0, 1.0, 1.0, 0.35))
        _draw_text(region_w, region_h,
                   (x0 + x1) * 0.5, (y0 + y1) * 0.5 + 14, 14,
                   (1.0, 1.0, 1.0, 0.7),
                   "No background image", centered=True)
        _draw_text(region_w, region_h,
                   (x0 + x1) * 0.5, (y0 + y1) * 0.5 - 8, 12,
                   (1.0, 1.0, 1.0, 0.45),
                   "Edit Mode > Background: Load", centered=True)

    # 領域の境界線 (常時)
    x0, y0, x1, y1 = picker_rect(tab, region_w, region_h)
    _draw_line_rect(region_w, region_h, x0, y0, x1, y1, (1.0, 1.0, 1.0, 0.22))

    # ボタン描画
    st = state
    for btn in tab.buttons:
        bx0, by0, bx1, by1 = button_region_rect(tab, region_w, region_h, btn)
        r, g, b, _a = _hex_to_rgba(btn.color)
        # ホバー / 選択中は明るく
        highlight = 0.0
        if btn.id == st.hover_id:
            highlight = 0.18
        if st.edit_mode and btn.id == st.selected_button_id:
            highlight = 0.32
        if btn.shape == "circle":
            _draw_circle(region_w, region_h,
                         (bx0 + bx1) * 0.5, (by0 + by1) * 0.5,
                         (bx1 - bx0) * 0.5, (by1 - by0) * 0.5,
                         (min(1.0, r + highlight), min(1.0, g + highlight),
                          min(1.0, b + highlight), 0.9))
        else:
            _draw_filled_rect(region_w, region_h, bx0, by0, bx1, by1,
                              (min(1.0, r + highlight), min(1.0, g + highlight),
                               min(1.0, b + highlight), 0.9))
        # 枠線
        if st.edit_mode and btn.id == st.selected_button_id:
            _draw_line_rect(region_w, region_h, bx0, by0, bx1, by1, (1.0, 1.0, 1.0, 0.95))
        else:
            _draw_line_rect(region_w, region_h, bx0, by0, bx1, by1,
                            (0.0, 0.0, 0.0, 0.55))
        # ラベル
        label = _button_display_label(btn)
        lsize = max(9, min(16, int((by1 - by0) * 0.5)))
        _draw_text(region_w, region_h, (bx0 + bx1) * 0.5, (by0 + by1) * 0.5,
                   lsize, (1.0, 1.0, 1.0, 0.95), label, centered=True)


def _draw_callback(state, context):
    """draw_handler_add のコールバック。"""
    if not state.enabled:
        return
    try:
        draw_picker_overlay(context, state)
    except Exception:
        traceback.print_exc()


# =============================================================================
# ボーン選択ヘルパ (Blender 5.2: PoseBone.select が標準)
# =============================================================================

def get_target_armature(context):
    """ピッカー操作の対象アーマチュアを探す。"""
    obj = getattr(context, "object", None)
    if obj is not None and obj.type == 'ARMATURE':
        return obj
    for o in getattr(context, "selected_objects", ()) or ():
        if o.type == 'ARMATURE':
            return o
    view_layer = getattr(context, "view_layer", None)
    if view_layer is not None and view_layer.objects.active is not None \
            and view_layer.objects.active.type == 'ARMATURE':
        return view_layer.objects.active
    for o in bpy.data.objects:
        if o.type == 'ARMATURE':
            return o
    return None


def set_bone_selected(arm, name, value):
    """5.2 では PoseBone.select / EditBone.select。旧版フォールバック付き。"""
    pb = arm.pose.bones.get(name)
    if pb is not None and hasattr(pb, "select"):
        pb.select = bool(value)
        return True
    bone = arm.data.bones.get(name)
    if bone is not None and hasattr(bone, "select"):
        bone.select = bool(value)
        return True
    return False


def is_bone_selected(arm, name):
    pb = arm.pose.bones.get(name)
    if pb is not None and hasattr(pb, "select"):
        return bool(pb.select)
    bone = arm.data.bones.get(name)
    if bone is not None and hasattr(bone, "select"):
        return bool(bone.select)
    return False


def deselect_all_bones(arm):
    for pb in arm.pose.bones:
        if hasattr(pb, "select"):
            pb.select = False
    for eb in arm.data.bones:
        if hasattr(eb, "select"):
            eb.select = False
    try:
        arm.data.bones.active = None
    except Exception:
        pass


def ensure_pose_mode(context, arm):
    """可能ならポーズモードに切り替え、結果を返す。"""
    if context.mode == 'POSE' and context.object is arm:
        return True
    try:
        if context.object is not arm:
            bpy.context.view_layer.objects.active = arm
        if context.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        return context.mode == 'POSE'
    except Exception:
        return False


def apply_click_selection(context, arm, bone_name, action):
    """ボタンクリックによる選択。

    action: 'replace' (通常クリック) / 'toggle' (Shift+クリック)
            / 'remove' (Ctrl+クリック)
    """
    if not bone_name:
        return False
    if not ensure_pose_mode(context, arm):
        return False
    bone = arm.data.bones.get(bone_name)
    if bone is None:
        return False

    if action == 'replace':
        deselect_all_bones(arm)
        set_bone_selected(arm, bone_name, True)
        arm.data.bones.active = bone
        return True

    if action == 'remove':
        set_bone_selected(arm, bone_name, False)
        return True

    # toggle (Shift+クリック)
    cur = is_bone_selected(arm, bone_name)
    set_bone_selected(arm, bone_name, not cur)
    if not cur:
        arm.data.bones.active = bone
    return True


def apply_utility(context, arm, what):
    """what: 'select_all' / 'deselect_all' / 'invert' / 'mirror'"""
    if arm is None:
        return False
    if what == 'select_all':
        for pb in arm.pose.bones:
            set_bone_selected(arm, pb.name, True)
        return True
    if what == 'deselect_all':
        deselect_all_bones(arm)
        return True
    if what == 'invert':
        for pb in arm.pose.bones:
            set_bone_selected(arm, pb.name, not is_bone_selected(arm, pb.name))
        return True
    if what == 'mirror':
        selected = [pb.name for pb in arm.pose.bones if is_bone_selected(arm, pb.name)]
        for name in selected:
            m = mirror_bone_name(name)
            if m and arm.pose.bones.get(m) is not None:
                set_bone_selected(arm, m, True)
        return True
    return False


# =============================================================================
# 状態変更ヘルパ (シーンpropsとの同期を含む)
# =============================================================================

def _sync_scene(scene):
    """state → scene props (再帰ガード付き)。"""
    st = _state
    if st._syncing or scene is None:
        return
    st._syncing = True
    try:
        scene.kapp_enabled = st.enabled
        scene.kapp_edit_mode = st.edit_mode

        rigs = st.data.rigs
        st.active_rig = max(0, min(st.active_rig, len(rigs) - 1))
        scene.kapp_rig_enum = 'RIG_%d' % st.active_rig
        rig = rigs[st.active_rig]
        scene.kapp_rig_name = rig.rig_name
        if not rig.tabs:
            rig.tabs.append(TabData())
        st.active_tab = max(0, min(st.active_tab, len(rig.tabs) - 1))
        scene.kapp_tab_enum = 'TAB_%d' % st.active_tab
        tab = rig.tabs[st.active_tab]
        scene.kapp_tab_name = tab.name

        scene.kapp_bg_path = tab.bg_image
        scene.kapp_anchor = tab.anchor
        scene.kapp_img_scale = tab.image_scale
        scene.kapp_img_ox = tab.image_offset_x
        scene.kapp_img_oy = tab.image_offset_y
        scene.kapp_img_opacity = tab.image_opacity

        btn = current_button()
        if btn is not None:
            scene.kapp_btn_id = btn.id
            scene.kapp_btn_bone = btn.bone
            scene.kapp_btn_label = btn.label
            scene.kapp_btn_x = btn.x
            scene.kapp_btn_y = btn.y
            scene.kapp_btn_w = btn.w
            scene.kapp_btn_h = btn.h
            scene.kapp_btn_shape = btn.shape
            scene.kapp_btn_color = _hex_to_rgba(btn.color)[:3]
    finally:
        st._syncing = False


def ensure_texture_loaded(tab):
    """ヒットテスト前に現在タブのテクスチャ/画像サイズを確定させる。"""
    st = _state
    path = resolve_bg_path(tab)
    want_key = None
    if path and os.path.isfile(path):
        try:
            want_key = (path, os.path.getmtime(path))
        except OSError:
            pass
    if st.tex_key == want_key:
        return
    load_background_texture(tab)


def _set_enabled(scene, value):
    """ピッカーの ON/OFF。ドローハンドラと modal operator を管理する。"""
    st = _state
    if value:
        st.enabled = True
        if st.draw_handle is None:
            st.draw_handle = bpy.types.SpaceView3D.draw_handler_add(
                _draw_callback, (st,), 'WINDOW', 'POST_PIXEL')
        if st.modal_op is not None:
            # 旧モーダルが残っていれば次イベントで終了させ、新しく開始する
            st.cancel_requested = True
        try:
            bpy.ops.view3d.kapp_picker_modal('INVOKE_DEFAULT')
        except Exception as e:
            print("[Kenny's Animation Picker] modal start failed: %s" % e)
    else:
        st.enabled = False
        if st.draw_handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(st.draw_handle, 'WINDOW')
            except Exception:
                pass
            st.draw_handle = None
        if st.modal_op is not None:
            st.cancel_requested = True  # modal は次のイベントで自己終了
    redraw_3d(bpy.context)


# =============================================================================
# プロパティ (N-Panel 用) と update コールバック
# =============================================================================

def _rig_items(self, context):
    st = _state
    if not st.data.rigs:
        return [('RIG_0', '(none)', "")]
    return [('RIG_%d' % i, r.rig_name, "") for i, r in enumerate(st.data.rigs)]


def _tab_items(self, context):
    st = _state
    rig = current_rig()
    if rig is None or not rig.tabs:
        return [('TAB_0', '(none)', "")]
    return [('TAB_%d' % i, t.name, "") for i, t in enumerate(rig.tabs)]


def _u_enabled(self, context):
    scene = getattr(context, "scene", None)
    if scene is None:
        scene = self
    if _state._syncing:
        return
    _set_enabled(scene, bool(self.kapp_enabled))


def _u_edit(self, context):
    st = _state
    if st._syncing:
        return
    st.edit_mode = bool(self.kapp_edit_mode)
    redraw_3d(context)


def _u_rig(self, context):
    st = _state
    if st._syncing:
        return
    try:
        idx = int(str(self.kapp_rig_enum).split('_')[1])
    except Exception:
        return
    if 0 <= idx < len(st.data.rigs):
        st.active_rig = idx
        st.active_tab = 0
        st.selected_button_id = None
        _sync_scene(getattr(context, "scene", None))
    redraw_3d(context)


def _u_tab(self, context):
    st = _state
    if st._syncing:
        return
    try:
        idx = int(str(self.kapp_tab_enum).split('_')[1])
    except Exception:
        return
    rig = current_rig()
    if rig is not None and 0 <= idx < len(rig.tabs):
        st.active_tab = idx
        st.selected_button_id = None
        _sync_scene(getattr(context, "scene", None))
    redraw_3d(context)


def _u_rig_name(self, context):
    st = _state
    if st._syncing:
        return
    rig = current_rig()
    if rig is not None:
        rig.rig_name = self.kapp_rig_name


def _u_tab_name(self, context):
    st = _state
    if st._syncing:
        return
    tab = current_tab()
    if tab is not None:
        tab.name = self.kapp_tab_name


def _u_bg(self, context):
    st = _state
    if st._syncing:
        return
    tab = current_tab()
    if tab is not None and tab.bg_image != self.kapp_bg_path:
        tab.bg_image = self.kapp_bg_path
        st.tex_key = None  # テクスチャ再生成
        st.texture = None
        st.img_size = None
    redraw_3d(context)


def _u_anchor(self, context):
    st = _state
    if st._syncing:
        return
    tab = current_tab()
    if tab is not None:
        tab.anchor = self.kapp_anchor
    redraw_3d(context)


def _u_scale(self, context):
    st = _state
    if st._syncing:
        return
    tab = current_tab()
    if tab is not None:
        tab.image_scale = self.kapp_img_scale
    redraw_3d(context)


def _u_ox(self, context):
    st = _state
    if st._syncing:
        return
    tab = current_tab()
    if tab is not None:
        tab.image_offset_x = self.kapp_img_ox
    redraw_3d(context)


def _u_oy(self, context):
    st = _state
    if st._syncing:
        return
    tab = current_tab()
    if tab is not None:
        tab.image_offset_y = self.kapp_img_oy
    redraw_3d(context)


def _u_opacity(self, context):
    st = _state
    if st._syncing:
        return
    tab = current_tab()
    if tab is not None:
        tab.image_opacity = self.kapp_img_opacity
    redraw_3d(context)


def _u_btn_id(self, context):
    st = _state
    if st._syncing:
        return
    btn = current_button()
    if btn is not None:
        btn.id = self.kapp_btn_id
        st.selected_button_id = btn.id
    redraw_3d(context)


def _u_btn_bone(self, context):
    st = _state
    if st._syncing:
        return
    btn = current_button()
    if btn is not None:
        btn.bone = self.kapp_btn_bone
    redraw_3d(context)


def _u_btn_label(self, context):
    st = _state
    if st._syncing:
        return
    btn = current_button()
    if btn is not None:
        btn.label = self.kapp_btn_label
    redraw_3d(context)


def _u_btn_x(self, context):
    st = _state
    if st._syncing:
        return
    btn = current_button()
    if btn is not None:
        btn.x = self.kapp_btn_x
    redraw_3d(context)


def _u_btn_y(self, context):
    st = _state
    if st._syncing:
        return
    btn = current_button()
    if btn is not None:
        btn.y = self.kapp_btn_y
    redraw_3d(context)


def _u_btn_w(self, context):
    st = _state
    if st._syncing:
        return
    btn = current_button()
    if btn is not None:
        btn.w = max(1.0, self.kapp_btn_w)
    redraw_3d(context)


def _u_btn_h(self, context):
    st = _state
    if st._syncing:
        return
    btn = current_button()
    if btn is not None:
        btn.h = max(1.0, self.kapp_btn_h)
    redraw_3d(context)


def _u_btn_shape(self, context):
    st = _state
    if st._syncing:
        return
    btn = current_button()
    if btn is not None:
        btn.shape = self.kapp_btn_shape
    redraw_3d(context)


def _u_btn_color(self, context):
    st = _state
    if st._syncing:
        return
    btn = current_button()
    if btn is not None:
        btn.color = _rgba_to_hex(self.kapp_btn_color)
    redraw_3d(context)


def register_properties():
    from bpy.props import (BoolProperty, StringProperty, FloatProperty,
                           FloatVectorProperty, EnumProperty)
    cls = bpy.types.Scene
    cls.kapp_enabled = BoolProperty(
        name="Picker Enabled", default=False, update=_u_enabled)
    cls.kapp_edit_mode = BoolProperty(
        name="Edit Mode", default=False, update=_u_edit)
    cls.kapp_rig_enum = EnumProperty(
        name="Rig", items=_rig_items, update=_u_rig)
    cls.kapp_tab_enum = EnumProperty(
        name="Tab", items=_tab_items, update=_u_tab)
    cls.kapp_rig_name = StringProperty(name="Rig Name", update=_u_rig_name)
    cls.kapp_tab_name = StringProperty(name="Tab Name", update=_u_tab_name)
    cls.kapp_bg_path = StringProperty(
        name="Background Image", subtype='FILE_PATH', update=_u_bg)
    cls.kapp_anchor = EnumProperty(
        name="Anchor", default='BL', update=_u_anchor,
        items=[('BL', "Bottom-Left", ""), ('TL', "Top-Left", ""),
               ('BR', "Bottom-Right", ""), ('TR', "Top-Right", "")])
    cls.kapp_img_scale = FloatProperty(
        name="Scale", default=1.0, min=0.01, max=100.0, update=_u_scale)
    cls.kapp_img_ox = FloatProperty(name="Offset X", default=0.0, update=_u_ox)
    cls.kapp_img_oy = FloatProperty(name="Offset Y", default=0.0, update=_u_oy)
    cls.kapp_img_opacity = FloatProperty(
        name="Opacity", default=1.0, min=0.0, max=1.0, update=_u_opacity)
    cls.kapp_btn_id = StringProperty(name="Button ID", update=_u_btn_id)
    cls.kapp_btn_bone = StringProperty(name="Bone", update=_u_btn_bone)
    cls.kapp_btn_label = StringProperty(name="Label", update=_u_btn_label)
    cls.kapp_btn_x = FloatProperty(name="X", default=0.0, update=_u_btn_x)
    cls.kapp_btn_y = FloatProperty(name="Y", default=0.0, update=_u_btn_y)
    cls.kapp_btn_w = FloatProperty(name="W", default=40.0, min=1.0, update=_u_btn_w)
    cls.kapp_btn_h = FloatProperty(name="H", default=40.0, min=1.0, update=_u_btn_h)
    cls.kapp_btn_shape = EnumProperty(
        name="Shape", default='rect', update=_u_btn_shape,
        items=[('rect', "Rectangle", ""), ('circle', "Circle", "")])
    cls.kapp_btn_color = FloatVectorProperty(
        name="Color", subtype='COLOR_GAMMA', size=3,
        default=(0.53, 0.80, 0.27), min=0.0, max=1.0, update=_u_btn_color)
    cls.kapp_json_path = StringProperty(
        name="JSON File", subtype='FILE_PATH', default="")


def unregister_properties():
    cls = bpy.types.Scene
    for name in ("kapp_enabled", "kapp_edit_mode", "kapp_rig_enum",
                 "kapp_tab_enum", "kapp_rig_name", "kapp_tab_name",
                 "kapp_bg_path", "kapp_anchor", "kapp_img_scale",
                 "kapp_img_ox", "kapp_img_oy", "kapp_img_opacity",
                 "kapp_btn_id", "kapp_btn_bone", "kapp_btn_label",
                 "kapp_btn_x", "kapp_btn_y", "kapp_btn_w", "kapp_btn_h",
                 "kapp_btn_shape", "kapp_btn_color", "kapp_json_path"):
        if hasattr(cls, name):
            delattr(cls, name)


# =============================================================================
# オペレーター
# =============================================================================

def _poll_armature(context):
    return get_target_armature(context) is not None


def _make_id(prefix, existing):
    i = 1
    while True:
        cand = "%s%02d" % (prefix, i)
        if cand not in existing:
            return cand
        i += 1


class KAPP_OT_add_rig(bpy.types.Operator):
    bl_idname = "kapp.add_rig"
    bl_label = "Add Rig"
    bl_description = "ピッカーにリグを追加"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = _state
        names = [r.rig_name for r in st.data.rigs]
        st.data.rigs.append(RigData(rig_name=_make_id("Rig", names)))
        st.active_rig = len(st.data.rigs) - 1
        st.active_tab = 0
        st.selected_button_id = None
        _sync_scene(context.scene)
        redraw_3d(context)
        return {'FINISHED'}


class KAPP_OT_remove_rig(bpy.types.Operator):
    bl_idname = "kapp.remove_rig"
    bl_label = "Remove Rig"
    bl_description = "アクティブなリグを削除"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = _state
        if len(st.data.rigs) <= 1:
            self.report({'WARNING'}, "最低1つのリグが必要です")
            return {'CANCELLED'}
        del st.data.rigs[st.active_rig]
        st.active_rig = max(0, st.active_rig - 1)
        st.active_tab = 0
        st.selected_button_id = None
        _sync_scene(context.scene)
        redraw_3d(context)
        return {'FINISHED'}


class KAPP_OT_add_tab(bpy.types.Operator):
    bl_idname = "kapp.add_tab"
    bl_label = "Add Tab"
    bl_description = "アクティブなリグにタブ (front/back 等) を追加"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = _state
        rig = current_rig()
        if rig is None:
            return {'CANCELLED'}
        names = [t.name for t in rig.tabs]
        rig.tabs.append(TabData(name=_make_id("tab", names)))
        st.active_tab = len(rig.tabs) - 1
        st.selected_button_id = None
        _sync_scene(context.scene)
        redraw_3d(context)
        return {'FINISHED'}


class KAPP_OT_remove_tab(bpy.types.Operator):
    bl_idname = "kapp.remove_tab"
    bl_label = "Remove Tab"
    bl_description = "アクティブなタブを削除"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = _state
        rig = current_rig()
        if rig is None or len(rig.tabs) <= 1:
            self.report({'WARNING'}, "最低1つのタブが必要です")
            return {'CANCELLED'}
        del rig.tabs[st.active_tab]
        st.active_tab = max(0, st.active_tab - 1)
        st.selected_button_id = None
        _sync_scene(context.scene)
        redraw_3d(context)
        return {'FINISHED'}


class KAPP_OT_load_bg_image(bpy.types.Operator):
    bl_idname = "kapp.load_bg_image"
    bl_label = "Load Background Image"
    bl_description = "背景画像 (jpeg/png) を外部パス参照で読み込む"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default='*.png;*.jpg;*.jpeg;*.jpe;*.bmp;*.tga;*.tif;*.tiff', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        path = self.filepath
        if not path or not os.path.isfile(path):
            self.report({'ERROR'}, "画像ファイルが見つかりません: %s" % path)
            return {'CANCELLED'}
        tab = current_tab()
        if tab is None:
            return {'CANCELLED'}
        st = _state
        tab.bg_image = path
        st.tex_key = None
        st.texture = None
        st.img_size = None
        _sync_scene(context.scene)
        redraw_3d(context)
        self.report({'INFO'}, "背景画像を読み込みました: %s" % path)
        return {'FINISHED'}


class KAPP_OT_clear_bg_image(bpy.types.Operator):
    bl_idname = "kapp.clear_bg_image"
    bl_label = "Clear Background"
    bl_description = "背景画像をクリア"

    def execute(self, context):
        st = _state
        tab = current_tab()
        if tab is not None:
            tab.bg_image = ""
        st.tex_key = None
        st.texture = None
        st.img_size = None
        _sync_scene(context.scene)
        redraw_3d(context)
        return {'FINISHED'}


class KAPP_OT_fit_image(bpy.types.Operator):
    bl_idname = "kapp.fit_image"
    bl_label = "Fit Image to Viewport"
    bl_description = "背景画像をビューポートに収まるよう拡大縮小・位置調整"

    def execute(self, context):
        st = _state
        tab = current_tab()
        if tab is None:
            return {'CANCELLED'}
        if st.img_size is None:
            # 先に読み込んでサイズを確定させる
            load_background_texture(tab)
        if st.img_size is None:
            self.report({'WARNING'}, "背景画像がありません")
            return {'CANCELLED'}
        region = None
        for r in context.area.regions:
            if r.type == 'WINDOW':
                region = r
                break
        if region is None or region.width <= 0 or region.height <= 0:
            return {'CANCELLED'}
        iw, ih = st.img_size
        scale = min((region.width * 0.85) / iw, (region.height * 0.85) / ih)
        tab.image_scale = max(0.01, scale)
        tab.image_offset_x = 0.0
        tab.image_offset_y = 0.0
        _sync_scene(context.scene)
        redraw_3d(context)
        return {'FINISHED'}


class KAPP_OT_select_button(bpy.types.Operator):
    bl_idname = "kapp.select_button"
    bl_label = "Select Button"
    bl_description = "編集対象のボタンを選択"

    button_id: bpy.props.StringProperty()

    def execute(self, context):
        st = _state
        st.selected_button_id = self.button_id
        _sync_scene(context.scene)
        redraw_3d(context)
        return {'FINISHED'}


class KAPP_OT_add_button_center(bpy.types.Operator):
    bl_idname = "kapp.add_button_center"
    bl_label = "Add Button"
    bl_description = "ピッカー中央にボタンを追加 (編集モードではオーバーレイ上をクリックでも追加できます)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = _state
        tab = current_tab()
        if tab is None:
            return {'CANCELLED'}
        iw, ih = tab_image_size(tab)
        s = tab.image_scale or 1.0
        btn = ButtonData(
            button_id=_make_id("btn", [b.id for b in tab.buttons]),
            bone="", shape="rect",
            x=(iw - DEFAULT_BUTTON_SCREEN_SIZE / s) * 0.5,
            y=(ih - DEFAULT_BUTTON_SCREEN_SIZE / s) * 0.5,
            w=DEFAULT_BUTTON_SCREEN_SIZE / s,
            h=DEFAULT_BUTTON_SCREEN_SIZE / s)
        tab.buttons.append(btn)
        st.selected_button_id = btn.id
        _sync_scene(context.scene)
        redraw_3d(context)
        return {'FINISHED'}


class KAPP_OT_duplicate_button(bpy.types.Operator):
    bl_idname = "kapp.duplicate_button"
    bl_label = "Duplicate Button"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = _state
        tab = current_tab()
        src = current_button()
        if tab is None or src is None:
            return {'CANCELLED'}
        new = ButtonData.from_dict(src.to_dict())
        new.id = _make_id("btn", [b.id for b in tab.buttons])
        new.x += 10.0 / (tab.image_scale or 1.0)
        new.y += 10.0 / (tab.image_scale or 1.0)
        tab.buttons.append(new)
        st.selected_button_id = new.id
        _sync_scene(context.scene)
        redraw_3d(context)
        return {'FINISHED'}


class KAPP_OT_delete_button(bpy.types.Operator):
    bl_idname = "kapp.delete_button"
    bl_label = "Delete Button"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = _state
        tab = current_tab()
        if tab is None or st.selected_button_id is None:
            return {'CANCELLED'}
        for i, b in enumerate(tab.buttons):
            if b.id == st.selected_button_id:
                del tab.buttons[i]
                break
        st.selected_button_id = None
        _sync_scene(context.scene)
        redraw_3d(context)
        return {'FINISHED'}


# -- 選択ユーティリティ ------------------------------------------------------

class KAPP_OT_select_all(bpy.types.Operator):
    bl_idname = "kapp.select_all"
    bl_label = "Select All"
    bl_description = "全ボーンを選択"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_armature(context)

    def execute(self, context):
        arm = get_target_armature(context)
        if arm is None:
            return {'CANCELLED'}
        ensure_pose_mode(context, arm)
        apply_utility(context, arm, 'select_all')
        return {'FINISHED'}


class KAPP_OT_deselect_all(bpy.types.Operator):
    bl_idname = "kapp.deselect_all"
    bl_label = "Deselect All"
    bl_description = "選択を解除"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_armature(context)

    def execute(self, context):
        arm = get_target_armature(context)
        if arm is None:
            return {'CANCELLED'}
        ensure_pose_mode(context, arm)
        apply_utility(context, arm, 'deselect_all')
        return {'FINISHED'}


class KAPP_OT_invert_selection(bpy.types.Operator):
    bl_idname = "kapp.invert_selection"
    bl_label = "Invert Selection"
    bl_description = "選択を反転"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_armature(context)

    def execute(self, context):
        arm = get_target_armature(context)
        if arm is None:
            return {'CANCELLED'}
        ensure_pose_mode(context, arm)
        apply_utility(context, arm, 'invert')
        return {'FINISHED'}


class KAPP_OT_mirror_selection(bpy.types.Operator):
    bl_idname = "kapp.mirror_selection"
    bl_label = "Mirror Selection (L/R)"
    bl_description = "選択ボーンの左右ミラーを自動検出 (.L/.R 等) して追加選択"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_armature(context)

    def execute(self, context):
        arm = get_target_armature(context)
        if arm is None:
            return {'CANCELLED'}
        ensure_pose_mode(context, arm)
        before = [pb.name for pb in arm.pose.bones if is_bone_selected(arm, pb.name)]
        apply_utility(context, arm, 'mirror')
        after = [pb.name for pb in arm.pose.bones if is_bone_selected(arm, pb.name)]
        added = [n for n in after if n not in before]
        if added:
            self.report({'INFO'}, "ミラー選択: %s" % ", ".join(added[:8]))
        else:
            self.report({'INFO'}, "ミラー対象のボーンがありません")
        return {'FINISHED'}


# -- JSON セーブ / ロード ----------------------------------------------------

class KAPP_OT_save_json(bpy.types.Operator):
    bl_idname = "kapp.save_json"
    bl_label = "Save Picker JSON"
    bl_description = "ピッカー設定を外部 JSON ファイルに書き出し"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default='*.json', options={'HIDDEN'})

    def invoke(self, context, event):
        st = _state
        if not self.filepath:
            base = st.json_path
            if not base:
                if bpy.data.filepath:
                    base = os.path.splitext(bpy.data.filepath)[0] + "_picker.json"
                else:
                    base = "picker.json"
            self.filepath = base
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        st = _state
        path = self.filepath
        if not path.endswith(".json"):
            path += ".json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(st.data.to_json())
        except Exception as e:
            self.report({'ERROR'}, "保存に失敗: %s" % e)
            return {'CANCELLED'}
        st.json_path = path
        context.scene.kapp_json_path = path
        self.report({'INFO'}, "保存しました: %s" % path)
        return {'FINISHED'}


class KAPP_OT_load_json(bpy.types.Operator):
    bl_idname = "kapp.load_json"
    bl_label = "Load Picker JSON"
    bl_description = "外部 JSON ファイルからピッカー設定を読み込み"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default='*.json', options={'HIDDEN'})

    def invoke(self, context, event):
        st = _state
        if not self.filepath and st.json_path:
            self.filepath = st.json_path
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        st = _state
        path = self.filepath
        if not os.path.isfile(path):
            self.report({'ERROR'}, "ファイルが見つかりません: %s" % path)
            return {'CANCELLED'}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = PickerData.from_json(f.read())
        except Exception as e:
            self.report({'ERROR'}, "読み込みに失敗: %s" % e)
            return {'CANCELLED'}
        data.ensure_default()
        st.data = data
        st.active_rig = 0
        st.active_tab = 0
        st.selected_button_id = None
        st.json_path = path
        st.tex_key = None
        st.texture = None
        st.img_size = None
        context.scene.kapp_json_path = path
        _sync_scene(context.scene)
        redraw_3d(context)
        self.report({'INFO'}, "読み込みました: %s" % path)
        return {'FINISHED'}


# -- モーダル (クリック処理) ---------------------------------------------------

def event_in_window_region(context, event):
    """マウスが WINDOW リージョン内にあるか (サイドバー等と区別する)。"""
    region = getattr(context, "region", None)
    if region is None:
        return False
    mx = event.mouse_x
    my = event.mouse_y
    if mx < region.x or mx > region.x + region.width:
        return False
    if my < region.y or my > region.y + region.height:
        return False
    return True


def _update_drag(context, event, region):
    st = _state
    tab = current_tab()
    if tab is None or st.dragging_id is None:
        return
    btn = current_button(st.dragging_id)
    if btn is None:
        return
    img = region_to_image(tab, region.width, region.height,
                          event.mouse_region_x, event.mouse_region_y)
    if img is None:
        return
    ix, iy = img
    btn.x = ix - btn.w * 0.5
    btn.y = iy - btn.h * 0.5
    if st.selected_button_id == btn.id:
        _sync_scene(getattr(context, "scene", None))
    redraw_3d(context)


def _create_button_at(context, event, region):
    st = _state
    tab = current_tab()
    if tab is None:
        return
    img = region_to_image(tab, region.width, region.height,
                          event.mouse_region_x, event.mouse_region_y)
    if img is None:
        return
    ix, iy = img
    s = _safe_scale(tab)
    size = DEFAULT_BUTTON_SCREEN_SIZE / s
    btn = ButtonData(
        button_id=_make_id("btn", [b.id for b in tab.buttons]),
        bone="", shape="rect",
        x=ix - size * 0.5, y=iy - size * 0.5,
        w=size, h=size)
    tab.buttons.append(btn)
    st.selected_button_id = btn.id
    _sync_scene(getattr(context, "scene", None))
    redraw_3d(context)


def modal_handle_event(context, event, report=None):
    """モーダルイベント処理の本体 (テスト可能な純関数)。

    ピッカー領域内のクリックのみ処理し、それ以外は PASS_THROUGH するため
    ビューポートの回転・パン等と競合しない。
    """
    st = _state
    if report is None:
        report = lambda *a, **k: None  # noqa: E731

    if not st.enabled or st.cancel_requested:
        return {'CANCELLED'}

    if context.area is None or context.area.type != 'VIEW_3D':
        return {'PASS_THROUGH'}
    region = context.region
    if region is None or region.type != 'WINDOW':
        return {'PASS_THROUGH'}

    # オーナー空間が破棄された場合など
    try:
        if st.space is not None and context.space_data != st.space:
            return {'PASS_THROUGH'}
    except ReferenceError:
        return {'CANCELLED'}

    in_window = event_in_window_region(context, event)

    # ヒットテストに使う画像サイズを最新化 (描画前にテクスチャ生成)
    tab_now = current_tab()
    if in_window and tab_now is not None:
        try:
            ensure_texture_loaded(tab_now)
        except Exception:
            pass

    if event.type == 'MOUSEMOVE':
        if in_window:
            st.hover_id = hit_test(current_tab(), region.width, region.height,
                                   event.mouse_region_x, event.mouse_region_y)
            if st.dragging_id is not None:
                _update_drag(context, event, region)
        else:
            st.hover_id = None
        return {'PASS_THROUGH'}

    if event.type == 'LEFTMOUSE':
        if event.value == 'PRESS':
            if not in_window:
                return {'PASS_THROUGH'}
            tab = current_tab()
            if tab is None:
                return {'PASS_THROUGH'}
            hit = hit_test(tab, region.width, region.height,
                           event.mouse_region_x, event.mouse_region_y)
            if st.edit_mode:
                st.pressed = True
                st.press_pos = (event.mouse_region_x, event.mouse_region_y)
                if hit is not None:
                    st.selected_button_id = hit
                    st.dragging_id = hit
                    _sync_scene(getattr(context, "scene", None))
                    redraw_3d(context)
                else:
                    st.dragging_id = None
                return {'RUNNING_MODAL'}
            if hit is not None:
                st.pressed = True
                st.press_pos = (event.mouse_region_x, event.mouse_region_y)
                return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}

        if event.value == 'RELEASE':
            if not st.pressed:
                return {'PASS_THROUGH'}
            st.pressed = False
            if st.dragging_id is not None:
                st.dragging_id = None
                return {'RUNNING_MODAL'}
            tab = current_tab()
            hit = hit_test(tab, region.width, region.height,
                           event.mouse_region_x, event.mouse_region_y)
            if st.edit_mode:
                if hit is None:
                    # 空き領域クリック → 新規ボタン作成
                    _create_button_at(context, event, region)
                else:
                    st.selected_button_id = hit
                    _sync_scene(getattr(context, "scene", None))
                    redraw_3d(context)
            else:
                if hit is not None:
                    btn = current_button(hit)
                    if btn is not None:
                        arm = get_target_armature(context)
                        if arm is None:
                            report({'WARNING'}, "アーマチュアが見つかりません")
                        else:
                            if event.ctrl:
                                action = 'remove'
                            elif event.shift:
                                action = 'toggle'
                            else:
                                action = 'replace'
                            if not apply_click_selection(context, arm, btn.bone, action):
                                report({'WARNING'}, "ボーンが見つかりません: %s" % btn.bone)
            return {'RUNNING_MODAL'}

    return {'PASS_THROUGH'}


class KAPP_OT_picker_modal(bpy.types.Operator):
    """ピッカーのクリックを処理する modal operator (実処理は modal_handle_event)。"""
    bl_idname = "view3d.kapp_picker_modal"
    bl_label = "Kenny's Animation Picker Modal"

    def invoke(self, context, event):
        st = _state
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'ERROR'}, "3Dビューから実行してください")
            return {'CANCELLED'}
        st.space = context.area.spaces.active
        st.modal_op = self
        st.cancel_requested = False
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        st = _state
        result = modal_handle_event(context, event, report=self.report)
        if result == {'CANCELLED'} and st.modal_op is self:
            st.modal_op = None
        return result


# =============================================================================
# N-Panel
# =============================================================================

class VIEW3D_PT_kapp_picker(bpy.types.Panel):
    bl_label = "Picker"
    bl_idname = "VIEW3D_PT_kapp_picker"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Picker"

    def draw(self, context):
        st = _state
        sc = context.scene
        layout = self.layout

        col = layout.column(align=True)
        col.prop(sc, "kapp_enabled", text="Enable Picker", icon='PLAY')
        col.prop(sc, "kapp_edit_mode", text="Edit Mode", icon='EDITMODE_HLT')
        col.separator()

        # --- リグ / タブ ---
        box = layout.box()
        box.label(text="Rig / Tab", icon='ARMATURE_DATA')
        row = box.row(align=True)
        row.prop(sc, "kapp_rig_enum", text="")
        row.operator("kapp.add_rig", text="", icon='ADD')
        row.operator("kapp.remove_rig", text="", icon='X')
        box.prop(sc, "kapp_rig_name", text="Name")
        row = box.row(align=True)
        row.prop(sc, "kapp_tab_enum", text="")
        row.operator("kapp.add_tab", text="", icon='ADD')
        row.operator("kapp.remove_tab", text="", icon='X')
        box.prop(sc, "kapp_tab_name", text="Name")
        box.separator()

        # --- 背景画像 ---
        box = layout.box()
        box.label(text="Background Image", icon='IMAGE_DATA')
        box.prop(sc, "kapp_bg_path", text="")
        row = box.row(align=True)
        row.operator("kapp.load_bg_image", text="Load Image", icon='FILE_FOLDER')
        row.operator("kapp.clear_bg_image", text="", icon='X')
        box.prop(sc, "kapp_anchor", text="Anchor")
        box.prop(sc, "kapp_img_scale", text="Scale")
        row = box.row(align=True)
        row.prop(sc, "kapp_img_ox", text="X")
        row.prop(sc, "kapp_img_oy", text="Y")
        box.prop(sc, "kapp_img_opacity", text="Opacity", slider=True)
        box.operator("kapp.fit_image", text="Fit Image to Viewport", icon='FIT_ALL')

        # --- ボタン ---
        box = layout.box()
        box.label(text="Buttons", icon='RESTRICT_SELECT_OFF')
        tab = current_tab()
        if tab is not None and tab.buttons:
            colb = box.column(align=True)
            for btn in tab.buttons:
                row = colb.row(align=True)
                op = row.operator("kapp.select_button",
                                  text="%s  (%s)" % (btn.id, btn.bone),
                                  depress=(btn.id == st.selected_button_id))
                op.button_id = btn.id
                row.label(text=btn.shape, icon='MESH_CIRCLE' if btn.shape == 'circle' else 'MESH_PLANE')
        else:
            box.label(text="No buttons yet", icon='INFO')
        row = box.row(align=True)
        row.operator("kapp.add_button_center", text="Add Button", icon='ADD')
        row.operator("kapp.duplicate_button", text="", icon='DUPLICATE')
        row.operator("kapp.delete_button", text="", icon='TRASH')

        # 選択中ボタンの編集
        btn = current_button()
        if btn is not None:
            box.separator()
            box.label(text="Selected Button: %s" % btn.id, icon='DOT')
            box.prop(sc, "kapp_btn_id", text="ID")
            box.prop(sc, "kapp_btn_bone", text="Bone")
            box.prop(sc, "kapp_btn_label", text="Label")
            row = box.row(align=True)
            row.prop(sc, "kapp_btn_x", text="X")
            row.prop(sc, "kapp_btn_y", text="Y")
            row = box.row(align=True)
            row.prop(sc, "kapp_btn_w", text="W")
            row.prop(sc, "kapp_btn_h", text="H")
            box.prop(sc, "kapp_btn_shape", text="Shape")
            box.prop(sc, "kapp_btn_color", text="Color")

        # --- 選択ユーティリティ ---
        box = layout.box()
        box.label(text="Selection", icon='RESTRICT_SELECT_OFF')
        row = box.row(align=True)
        row.operator("kapp.select_all", text="Select All", icon='SELECT_ALL')
        row.operator("kapp.deselect_all", text="Clear", icon='X')
        row = box.row(align=True)
        row.operator("kapp.invert_selection", text="Invert", icon='ARROW_LEFTRIGHT')
        row.operator("kapp.mirror_selection", text="Mirror L/R", icon='MOD_MIRROR')

        # --- JSON ---
        box = layout.box()
        box.label(text="Save / Load JSON", icon='FILE_SCRIPT')
        box.prop(sc, "kapp_json_path", text="")
        row = box.row(align=True)
        row.operator("kapp.save_json", text="Save...", icon='EXPORT')
        row.operator("kapp.load_json", text="Load...", icon='IMPORT')


# =============================================================================
# 登録
# =============================================================================

_CLASSES = (
    KAPP_OT_add_rig,
    KAPP_OT_remove_rig,
    KAPP_OT_add_tab,
    KAPP_OT_remove_tab,
    KAPP_OT_load_bg_image,
    KAPP_OT_clear_bg_image,
    KAPP_OT_fit_image,
    KAPP_OT_select_button,
    KAPP_OT_add_button_center,
    KAPP_OT_duplicate_button,
    KAPP_OT_delete_button,
    KAPP_OT_select_all,
    KAPP_OT_deselect_all,
    KAPP_OT_invert_selection,
    KAPP_OT_mirror_selection,
    KAPP_OT_save_json,
    KAPP_OT_load_json,
    KAPP_OT_picker_modal,
    VIEW3D_PT_kapp_picker,
)


def _on_load_post(dummy):
    """ファイル読み込み後はピッカーを安全な初期状態に戻す。"""
    st = _state
    st.enabled = False
    st.edit_mode = False
    st.modal_op = None
    st.space = None
    st.tex_key = None
    st.texture = None
    st.img_size = None
    if st.draw_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(st.draw_handle, 'WINDOW')
        except Exception:
            pass
        st.draw_handle = None
    for scene in bpy.data.scenes:
        if hasattr(scene, "kapp_enabled"):
            try:
                scene.kapp_enabled = False
            except Exception:
                pass


def register():
    register_properties()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)


def unregister():
    st = _state
    st.enabled = False
    if st.draw_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(st.draw_handle, 'WINDOW')
        except Exception:
            pass
        st.draw_handle = None
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    unregister_properties()


if __name__ == "__main__":
    register()
