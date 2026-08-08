bl_info = {
    "name": "My Hot Key Inspired by Maya",
    "author": "dokurokaruto",
    "version": (1, 0, 3),
    "blender": (3, 6, 0),
    "location": "Keymap / 3D View / Graph Editor",
    "description": (
        "Maya風のホットキー・ナビゲーション・"
        "Micro Manipulator・Hotbox を提供するアドオン"
    ),
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}


import bpy
import bmesh
import os
import time
import math
import mathutils


# ============================================================
# アドオン設定（再起動後も Preferences に保持）
# ============================================================

ADDON_ID = (
    __name__
    if __name__ != "__main__"
    else "my_hot_key_inspired_by_maya"
)

# 実行時に登録したアドオンキーマップ (km, kmi)
_addon_keymaps = []

# グローバルポリシー等で無効化したユーザーキーマップ項目
# (keymap_name, kmi_id)
_disabled_user_keymap_item_ids = []


def _addon_prefs(context=None):
    """アドオン設定を取得する。未登録時は None。"""
    try:
        addons = (context or bpy.context).preferences.addons
    except Exception:
        return None

    # パッケージ名 / モジュール名の両方に対応
    for key in (ADDON_ID, ADDON_ID.split(".")[-1], __package__ or ""):
        if not key:
            continue
        try:
            mod = addons.get(key)
        except Exception:
            mod = None
        if mod is not None:
            return getattr(mod, "preferences", None)

    # フォールバック: 名前部分一致
    try:
        for mod in addons:
            if ADDON_ID in mod.module or mod.module.endswith(
                "my_hot_key_inspired_by_maya"
            ):
                return mod.preferences
    except Exception:
        pass

    return None


def _pref_value(name, default):
    prefs = _addon_prefs()
    if prefs is None:
        return default
    return getattr(prefs, name, default)


# 後方互換用のモジュール定数（オペレーター本体が参照）
# アドオン有効時は Preferences の値が優先されるようプロパティで読む。
SPACE_HOLD_TIME = 0.3
KEEP_SPACE_PLAY_IN_ANIM_EDITORS = True
ALT1_ALSO_TOGGLE_EMPTIES = False
RESET_DELTA_TRANSFORMS = True
GRAPH_KEY_VERTEX_SIZE = 6
GRAPH_HANDLE_VERTEX_SIZE = 5
SLIDE_SNAP_FRAMES = True
SLIDE_AXIS_LOCK_THRESHOLD_PX = 5
MICRO_MANIPULATOR_GIZMO_SCALE = 1.0
MICRO_ORIENTATION_TYPES = {
    'GLOBAL',
    'LOCAL',
    'GIMBAL',
}
PRESET_FILENAME = "my_hot_key_inspired_by_maya.py"


def get_space_hold_time():
    return float(_pref_value("space_hold_time", SPACE_HOLD_TIME))


def get_keep_space_play_in_anim_editors():
    return bool(
        _pref_value(
            "keep_space_play_in_anim_editors",
            KEEP_SPACE_PLAY_IN_ANIM_EDITORS,
        )
    )


def get_alt1_also_toggle_empties():
    return bool(
        _pref_value(
            "alt1_also_toggle_empties",
            ALT1_ALSO_TOGGLE_EMPTIES,
        )
    )


def get_reset_delta_transforms():
    return bool(
        _pref_value(
            "reset_delta_transforms",
            RESET_DELTA_TRANSFORMS,
        )
    )


def get_graph_key_vertex_size():
    return int(
        _pref_value("graph_key_vertex_size", GRAPH_KEY_VERTEX_SIZE)
    )


def get_graph_handle_vertex_size():
    return int(
        _pref_value(
            "graph_handle_vertex_size",
            GRAPH_HANDLE_VERTEX_SIZE,
        )
    )


def get_slide_snap_frames():
    return bool(_pref_value("slide_snap_frames", SLIDE_SNAP_FRAMES))


def get_slide_axis_lock_threshold_px():
    return int(
        _pref_value(
            "slide_axis_lock_threshold_px",
            SLIDE_AXIS_LOCK_THRESHOLD_PX,
        )
    )


def get_micro_manipulator_gizmo_scale():
    return float(
        _pref_value(
            "micro_manipulator_gizmo_scale",
            MICRO_MANIPULATOR_GIZMO_SCALE,
        )
    )


class MAYA_HOTKEY_AT_preferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    use_industry_compatible_base: bpy.props.BoolProperty(
        name="Industry Compatible をベースにする",
        description=(
            "アドオン有効化時に Industry Compatible キー設定を読み込む。"
            "競合の少ない Maya 風操作の土台になります"
        ),
        default=True,
    )

    restore_user_keymap_on_base: bpy.props.BoolProperty(
        name="読み込み時にユーザーキーマップをリセット",
        description=(
            "Industry Compatible 読み込み後、ユーザー変更キーを"
            "すべてリセットする（初回セットアップ向け・破壊的）"
        ),
        default=False,
    )

    apply_maya_zoom: bpy.props.BoolProperty(
        name="Maya式ズーム方向を適用",
        description="Dolly / 水平ドラッグ / 反転なし",
        default=True,
    )

    disable_mouse_emulate_3_button: bpy.props.BoolProperty(
        name="3ボタンマウスエミュレートを無効化",
        description=(
            "Alt+LMB 回転などと競合するため無効化を推奨"
        ),
        default=True,
    )

    keep_space_play_in_anim_editors: bpy.props.BoolProperty(
        name="アニメーションエディターで Space=再生を維持",
        default=True,
    )

    space_hold_time: bpy.props.FloatProperty(
        name="Space / D 長押し判定（秒）",
        default=0.3,
        min=0.05,
        max=2.0,
        subtype='TIME',
    )

    alt1_also_toggle_empties: bpy.props.BoolProperty(
        name="Alt+1 で Empty 表示も切替",
        default=False,
    )

    reset_delta_transforms: bpy.props.BoolProperty(
        name="トランスフォーム初期化で Delta もリセット",
        default=True,
    )

    graph_key_vertex_size: bpy.props.IntProperty(
        name="グラフ キー点サイズ",
        default=6,
        min=1,
        max=20,
    )

    graph_handle_vertex_size: bpy.props.IntProperty(
        name="グラフ ハンドル点サイズ",
        default=5,
        min=1,
        max=20,
    )

    slide_snap_frames: bpy.props.BoolProperty(
        name="Shift+MMB キー移動でフレームにスナップ",
        default=True,
    )

    slide_axis_lock_threshold_px: bpy.props.IntProperty(
        name="軸ロック判定ピクセル",
        default=5,
        min=1,
        max=50,
    )

    micro_manipulator_gizmo_scale: bpy.props.FloatProperty(
        name="Micro Manipulator サイズ",
        default=1.0,
        min=0.1,
        max=5.0,
    )

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.label(text="起動・ベースキーマップ", icon='PREFERENCES')
        col.prop(self, "use_industry_compatible_base")
        sub = col.column(align=True)
        sub.enabled = self.use_industry_compatible_base
        sub.prop(self, "restore_user_keymap_on_base")
        col.prop(self, "apply_maya_zoom")
        col.prop(self, "disable_mouse_emulate_3_button")

        layout.separator()
        col = layout.column(align=True)
        col.label(text="操作", icon='MOUSE_MMB')
        col.prop(self, "space_hold_time")
        col.prop(self, "keep_space_play_in_anim_editors")
        col.prop(self, "alt1_also_toggle_empties")
        col.prop(self, "reset_delta_transforms")
        col.prop(self, "slide_snap_frames")
        col.prop(self, "slide_axis_lock_threshold_px")

        layout.separator()
        col = layout.column(align=True)
        col.label(text="表示", icon='HIDE_OFF')
        col.prop(self, "graph_key_vertex_size")
        col.prop(self, "graph_handle_vertex_size")
        col.prop(self, "micro_manipulator_gizmo_scale")

        layout.separator()
        row = layout.row(align=True)
        row.operator(
            "wm.maya_hotkey_reapply_keymap",
            icon='FILE_REFRESH',
        )
        row.operator(
            "wm.maya_hotkey_export_preset",
            icon='EXPORT',
        )

        box = layout.box()
        box.label(text="主なショートカット", icon='INFO')
        col = box.column(align=True)
        col.label(text="Alt+LMB/MMB/RMB: 回転 / パン / ズーム")
        col.label(text="Space 単押し: 四分割トグル / 長押し: Hotbox")
        col.label(text="Q/W/E/R: 選択 / 移動 / 回転 / スケール")
        col.label(text="Ctrl+Shift+RMB: Manipulator Settings")
        col.label(text="Z: Undo / Alt+Q: 再生")
        col.label(text="S: キー挿入（全域） / Alt+W/S: キー移動 / Alt+A/D: 1F")
        col.label(text="Alt+1: コントローラー表示切替")
        col.label(text="Alt+* または Alt+Shift+8: トランスフォーム初期化")


# ============================================================
# Industry Compatible を読み込む
# ============================================================

def find_industry_compatible_preset():
    filepath = None

    try:
        filepath = bpy.utils.preset_find(
            "Industry_Compatible",
            "keyconfig",
            ext=".py",
        )
    except Exception:
        pass

    if filepath:
        return filepath

    try:
        for directory in bpy.utils.preset_paths("keyconfig"):
            candidate = os.path.join(
                directory,
                "Industry_Compatible.py",
            )

            if os.path.isfile(candidate):
                return candidate
    except Exception:
        pass

    return None


# ============================================================
# キーマップ操作用ヘルパー
# ============================================================

def is_exact_event(
    kmi,
    event_type,
    value='PRESS',
    shift=False,
    ctrl=False,
    alt=False,
    oskey=False,
):
    if kmi.any:
        return False

    if kmi.type != event_type:
        return False

    if kmi.value != value:
        return False

    if kmi.shift != shift:
        return False

    if kmi.ctrl != ctrl:
        return False

    if kmi.alt != alt:
        return False

    if kmi.oskey != oskey:
        return False

    if getattr(kmi, "hyper", False):
        return False

    if getattr(kmi, "key_modifier", 'NONE') != 'NONE':
        return False

    if getattr(kmi, "direction", 'ANY') != 'ANY':
        return False

    return True


# ============================================================
# グローバルキーポリシー
# ============================================================

GLOBAL_KEY_POLICIES = (
    (
        'Z',
        'PRESS',
        False,
        False,
        False,
        {'ed.undo'},
    ),
    (
        'Q',
        'PRESS',
        False,
        False,
        True,
        {'screen.animation_play'},
    ),
    (
        'A',
        'PRESS',
        False,
        False,
        True,
        {'screen.frame_offset'},
    ),
    (
        'D',
        'PRESS',
        False,
        False,
        True,
        {'screen.frame_offset'},
    ),
    (
        'W',
        'PRESS',
        False,
        False,
        True,
        {'screen.maya_keyframe_jump'},
    ),
    (
        'S',
        'PRESS',
        False,
        False,
        True,
        {'screen.maya_keyframe_jump'},
    ),
    # 修飾なし S = Maya Set Key（キー挿入）
    (
        'S',
        'PRESS',
        False,
        False,
        False,
        {'screen.maya_keyframe_insert', 'anim.keyframe_insert'},
    ),
    (
        'ONE',
        'PRESS',
        False,
        False,
        True,
        {'view3d.maya_toggle_controllers'},
    ),
    (
        'NUMPAD_ASTERIX',
        'PRESS',
        False,
        False,
        True,
        {'object.maya_reset_transforms'},
    ),
    (
        'EIGHT',
        'PRESS',
        True,
        False,
        True,
        {'object.maya_reset_transforms'},
    ),
)


# ============================================================
# グラフエディター表示設定
# ============================================================

def setup_graph_editor_handle_display():
    configured_count = 0

    try:
        screens = bpy.data.screens
    except Exception:
        return

    for screen in screens:
        for area in screen.areas:
            if area.type != 'GRAPH_EDITOR':
                continue

            for space in area.spaces:
                if getattr(space, "type", None) != 'GRAPH_EDITOR':
                    continue

                try:
                    space.show_handles = True
                except Exception:
                    pass

                try:
                    space.use_only_selected_keyframe_handles = False
                except Exception:
                    pass

                configured_count += 1

    print(
        f"✅ {configured_count} 個のグラフエディターで"
        "ハンドルを常時操作できる標準表示に戻しました。"
    )


@bpy.app.handlers.persistent
def _maya_graph_display_load_post(_dummy):
    setup_graph_editor_handle_display()


def register_graph_display_load_handler():
    handlers = bpy.app.handlers.load_post

    for handler in list(handlers):
        if getattr(handler, "__name__", "") == "_maya_graph_display_load_post":
            try:
                handlers.remove(handler)
            except Exception:
                pass

    handlers.append(_maya_graph_display_load_post)


def unregister_graph_display_load_handler():
    handlers = bpy.app.handlers.load_post

    for handler in list(handlers):
        if getattr(handler, "__name__", "") == "_maya_graph_display_load_post":
            try:
                handlers.remove(handler)
            except Exception:
                pass


# ============================================================
# 3D View共通ヘルパー
# ============================================================

def _point_in_rect(x, y, rx, ry, rw, rh):
    return (
        rx <= x < rx + rw and
        ry <= y < ry + rh
    )


def _region_center_distance_sq(region, x, y):
    cx = region.x + region.width * 0.5
    cy = region.y + region.height * 0.5

    dx = cx - x
    dy = cy - y

    return dx * dx + dy * dy


def _is_region_view3d(value):
    try:
        return isinstance(value, bpy.types.RegionView3D)
    except Exception:
        return False


def is_view3d_quadview(space):
    if space is None:
        return False

    try:
        return len(space.region_quadviews) > 0
    except Exception:
        return False


def _make_context_override_kwargs(
    context,
    area=None,
    region=None,
    space=None,
    region_data=None,
):
    kwargs = {}

    window = getattr(context, "window", None)

    if window is not None:
        kwargs["window"] = window

        try:
            if window.screen is not None:
                kwargs["screen"] = window.screen
        except Exception:
            pass
    else:
        screen = getattr(context, "screen", None)

        if screen is not None:
            kwargs["screen"] = screen

    if area is not None:
        kwargs["area"] = area

    if region is not None:
        kwargs["region"] = region

    if space is not None:
        kwargs["space_data"] = space

    if region_data is not None:
        kwargs["region_data"] = region_data

    return kwargs


def resolve_region_data_for_region(context, area, region, space):
    if area is None or region is None or space is None:
        return None

    try:
        region_data = getattr(region, "data", None)

        if _is_region_view3d(region_data):
            return region_data
    except Exception:
        pass

    try:
        if context.area == area and context.region == region:
            region_data = context.region_data

            if _is_region_view3d(region_data):
                return region_data
    except Exception:
        pass

    if hasattr(context, "temp_override"):
        kwargs = _make_context_override_kwargs(
            context,
            area=area,
            region=region,
            space=space,
            region_data=None,
        )

        override_variants = (
            kwargs,
            {
                key: value
                for key, value in kwargs.items()
                if key != "space_data"
            },
        )

        for override_kwargs in override_variants:
            try:
                with context.temp_override(**override_kwargs):
                    region_data = context.region_data

                    if _is_region_view3d(region_data):
                        return region_data
            except Exception:
                pass

    if not is_view3d_quadview(space):
        try:
            region_data = space.region_3d

            if _is_region_view3d(region_data):
                return region_data
        except Exception:
            pass

    return None


def find_view3d_area_region_under_mouse(context, mouse_x, mouse_y):
    screen = None

    try:
        if context.window is not None:
            screen = context.window.screen
    except Exception:
        pass

    if screen is None:
        try:
            screen = context.screen
        except Exception:
            screen = None

    area = None

    if screen is not None and mouse_x is not None and mouse_y is not None:
        for area_candidate in screen.areas:
            if area_candidate.type != 'VIEW_3D':
                continue

            if _point_in_rect(
                mouse_x,
                mouse_y,
                area_candidate.x,
                area_candidate.y,
                area_candidate.width,
                area_candidate.height,
            ):
                area = area_candidate
                break

    if area is None:
        try:
            if context.area is not None and context.area.type == 'VIEW_3D':
                area = context.area
        except Exception:
            pass

    if area is None:
        return None, None, None, None

    try:
        space = area.spaces.active
    except Exception:
        space = None

    if space is None or getattr(space, "type", None) != 'VIEW_3D':
        return area, None, space, None

    window_regions = [
        region
        for region in area.regions
        if (
            region.type == 'WINDOW' and
            region.width > 0 and
            region.height > 0
        )
    ]

    region = None

    if mouse_x is not None and mouse_y is not None:
        for region_candidate in window_regions:
            if _point_in_rect(
                mouse_x,
                mouse_y,
                region_candidate.x,
                region_candidate.y,
                region_candidate.width,
                region_candidate.height,
            ):
                region = region_candidate
                break

    if (
        region is None and
        window_regions and
        mouse_x is not None and
        mouse_y is not None
    ):
        region = min(
            window_regions,
            key=lambda item: _region_center_distance_sq(
                item,
                mouse_x,
                mouse_y,
            ),
        )

    if region is None:
        try:
            if (
                context.area == area and
                context.region is not None and
                context.region.type == 'WINDOW'
            ):
                region = context.region
        except Exception:
            pass

    if region is None and window_regions:
        region = max(
            window_regions,
            key=lambda item: item.width * item.height,
        )

    region_data = resolve_region_data_for_region(
        context,
        area,
        region,
        space,
    )

    return area, region, space, region_data


def find_any_view3d_space(context):
    screen = None

    try:
        if context.window is not None:
            screen = context.window.screen
    except Exception:
        pass

    if screen is None:
        try:
            screen = context.screen
        except Exception:
            return None

    if screen is None:
        return None

    best_space = None
    best_size = -1

    for area in screen.areas:
        if area.type != 'VIEW_3D':
            continue

        size = area.width * area.height

        if size <= best_size:
            continue

        try:
            candidate = area.spaces.active
        except Exception:
            continue

        if (
            candidate is not None and
            getattr(candidate, "type", None) == 'VIEW_3D'
        ):
            best_space = candidate
            best_size = size

    return best_space


def resolve_active_region_view3d(context):
    rv3d = getattr(context, "region_data", None)

    if _is_region_view3d(rv3d):
        return rv3d

    space = getattr(context, "space_data", None)

    if space is not None and getattr(space, "type", None) == 'VIEW_3D':
        try:
            rv3d = space.region_3d

            if _is_region_view3d(rv3d):
                return rv3d
        except Exception:
            pass

    space = find_any_view3d_space(context)

    if space is not None:
        try:
            rv3d = space.region_3d

            if _is_region_view3d(rv3d):
                return rv3d
        except Exception:
            pass

    return None


def copy_region_view3d_state(src, dst):
    if src is None or dst is None:
        return

    try:
        if src.as_pointer() == dst.as_pointer():
            return
    except Exception:
        pass

    attrs = (
        "view_location",
        "view_rotation",
        "view_distance",
        "view_camera_offset",
        "view_camera_zoom",
        "view_perspective",
    )

    for attr in attrs:
        try:
            value = getattr(src, attr)

            try:
                value = value.copy()
            except Exception:
                pass

            setattr(dst, attr, value)
        except Exception:
            pass


def call_region_quadview_for_region(
    context,
    area,
    region,
    space,
    region_data,
):
    if area is None or region is None:
        return bpy.ops.screen.region_quadview()

    kwargs = _make_context_override_kwargs(
        context,
        area=area,
        region=region,
        space=space,
        region_data=region_data,
    )

    if hasattr(context, "temp_override"):
        override_variants = []

        override_variants.append(dict(kwargs))

        kwargs_no_region_data = dict(kwargs)
        kwargs_no_region_data.pop("region_data", None)
        override_variants.append(kwargs_no_region_data)

        kwargs_no_space_region_data = dict(kwargs_no_region_data)
        kwargs_no_space_region_data.pop("space_data", None)
        override_variants.append(kwargs_no_space_region_data)

        last_error = None

        for override_kwargs in override_variants:
            try:
                with context.temp_override(**override_kwargs):
                    return bpy.ops.screen.region_quadview()
            except Exception as error:
                last_error = error

        print(
            "⚠️ マウス下Region指定でregion_quadviewを実行できませんでした。"
            f" 通常contextで再試行します: {last_error}"
        )

    return bpy.ops.screen.region_quadview()


def call_menu_pie_for_region(
    context,
    menu_name,
    area,
    region,
    space,
    region_data,
):
    kwargs = _make_context_override_kwargs(
        context,
        area=area,
        region=region,
        space=space,
        region_data=region_data,
    )

    if (
        hasattr(context, "temp_override") and
        area is not None and
        region is not None
    ):
        override_variants = []

        override_variants.append(dict(kwargs))

        kwargs_no_region_data = dict(kwargs)
        kwargs_no_region_data.pop("region_data", None)
        override_variants.append(kwargs_no_region_data)

        kwargs_no_space_region_data = dict(kwargs_no_region_data)
        kwargs_no_space_region_data.pop("space_data", None)
        override_variants.append(kwargs_no_space_region_data)

        last_error = None

        for override_kwargs in override_variants:
            try:
                with context.temp_override(**override_kwargs):
                    return bpy.ops.wm.call_menu_pie(
                        'INVOKE_DEFAULT',
                        name=menu_name,
                    )
            except Exception as error:
                last_error = error

        print(
            "⚠️ マウス下Region指定でHotboxを開けませんでした。"
            f" 通常contextで再試行します: {last_error}"
        )

    return bpy.ops.wm.call_menu_pie(
        'INVOKE_DEFAULT',
        name=menu_name,
    )


def tag_all_view3d_redraw():
    try:
        screens = bpy.data.screens
    except Exception:
        return

    for screen in screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                try:
                    area.tag_redraw()
                except Exception:
                    pass


def iter_view3d_spaces():
    try:
        screens = bpy.data.screens
    except Exception:
        return

    for screen in screens:
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue

            for space in area.spaces:
                if getattr(space, "type", None) == 'VIEW_3D':
                    yield space


# ============================================================
# Transform Orientation / Micro Manipulator
# ============================================================

def get_current_transform_orientation(context):
    try:
        orientation = context.scene.transform_orientation_slots[0].type
    except Exception:
        orientation = 'GLOBAL'

    if orientation not in MICRO_ORIENTATION_TYPES:
        return 'GLOBAL'

    return orientation


def set_transform_orientation(context, orientation):
    if orientation not in MICRO_ORIENTATION_TYPES:
        orientation = 'GLOBAL'

    try:
        context.scene.transform_orientation_slots[0].type = orientation
    except Exception as error:
        print(
            f"⚠️ Transform Orientationを設定できませんでした: {error}"
        )
        return False

    tag_all_view3d_redraw()
    return True


def restore_maya_micro_space_visibility():
    wm = getattr(bpy.context, "window_manager", None)

    if wm is None:
        return

    try:
        owned = bool(wm.maya_micro_visibility_owned)
    except Exception:
        owned = False

    if not owned:
        return

    try:
        previous_show_gizmo = bool(
            wm.maya_micro_previous_show_gizmo
        )
    except Exception:
        previous_show_gizmo = True

    try:
        previous_show_gizmo_tool = bool(
            wm.maya_micro_previous_show_gizmo_tool
        )
    except Exception:
        previous_show_gizmo_tool = True

    try:
        previous_show_gizmo_context = bool(
            wm.maya_micro_previous_show_gizmo_context
        )
    except Exception:
        previous_show_gizmo_context = True

    for space in iter_view3d_spaces():
        try:
            space.show_gizmo = previous_show_gizmo
        except Exception:
            pass

        try:
            space.show_gizmo_tool = previous_show_gizmo_tool
        except Exception:
            pass

        try:
            space.show_gizmo_context = previous_show_gizmo_context
        except Exception:
            pass

    try:
        wm.maya_micro_visibility_owned = False
    except Exception:
        pass

    tag_all_view3d_redraw()


def apply_maya_micro_space_visibility(context, enabled):
    wm = getattr(context, "window_manager", None)

    if wm is None:
        return

    if not enabled:
        restore_maya_micro_space_visibility()
        return

    try:
        owned = bool(wm.maya_micro_visibility_owned)
    except Exception:
        owned = False

    if not owned:
        source_space = getattr(context, "space_data", None)

        if (
            source_space is None or
            getattr(source_space, "type", None) != 'VIEW_3D'
        ):
            source_space = find_any_view3d_space(context)

        if source_space is None:
            try:
                source_space = next(iter(iter_view3d_spaces()))
            except Exception:
                source_space = None

        if source_space is not None:
            try:
                wm.maya_micro_previous_show_gizmo = bool(
                    source_space.show_gizmo
                )
            except Exception:
                wm.maya_micro_previous_show_gizmo = True

            try:
                wm.maya_micro_previous_show_gizmo_tool = bool(
                    source_space.show_gizmo_tool
                )
            except Exception:
                wm.maya_micro_previous_show_gizmo_tool = True

            try:
                wm.maya_micro_previous_show_gizmo_context = bool(
                    source_space.show_gizmo_context
                )
            except Exception:
                wm.maya_micro_previous_show_gizmo_context = True

        try:
            wm.maya_micro_visibility_owned = True
        except Exception:
            pass

    for space in iter_view3d_spaces():
        try:
            space.show_gizmo = True
        except Exception:
            pass

        # Blender標準のツールギズモを隠し、
        # Micro Manipulatorとの重複クリックを防ぐ。
        try:
            space.show_gizmo_tool = False
        except Exception:
            pass

        # カスタムのPersistent GizmoGroupを表示する。
        try:
            space.show_gizmo_context = True
        except Exception:
            pass

    tag_all_view3d_redraw()


def register_maya_runtime_properties():
    # maya_micro_manipulator_mode は旧バージョンの残骸。
    # 削除リストに含めてクリーンアップする（再作成はしない）。
    property_names = (
        "maya_micro_manipulator_enabled",
        "maya_micro_manipulator_mode",
        "maya_micro_visibility_owned",
        "maya_micro_previous_show_gizmo",
        "maya_micro_previous_show_gizmo_tool",
        "maya_micro_previous_show_gizmo_context",
    )

    for property_name in property_names:
        if hasattr(bpy.types.WindowManager, property_name):
            try:
                delattr(
                    bpy.types.WindowManager,
                    property_name,
                )
            except Exception:
                pass

    bpy.types.WindowManager.maya_micro_manipulator_enabled = (
        bpy.props.BoolProperty(
            name="Micro Manipulator",
            description=(
                "約1/10の感度で動作する高精度マニピュレーター"
            ),
            default=False,
            options={'SKIP_SAVE'},
        )
    )

    bpy.types.WindowManager.maya_micro_visibility_owned = (
        bpy.props.BoolProperty(
            default=False,
            options={'HIDDEN', 'SKIP_SAVE'},
        )
    )

    bpy.types.WindowManager.maya_micro_previous_show_gizmo = (
        bpy.props.BoolProperty(
            default=True,
            options={'HIDDEN', 'SKIP_SAVE'},
        )
    )

    bpy.types.WindowManager.maya_micro_previous_show_gizmo_tool = (
        bpy.props.BoolProperty(
            default=True,
            options={'HIDDEN', 'SKIP_SAVE'},
        )
    )

    bpy.types.WindowManager.maya_micro_previous_show_gizmo_context = (
        bpy.props.BoolProperty(
            default=True,
            options={'HIDDEN', 'SKIP_SAVE'},
        )
    )


def unregister_maya_runtime_properties():
    property_names = (
        "maya_micro_manipulator_enabled",
        "maya_micro_manipulator_mode",
        "maya_micro_visibility_owned",
        "maya_micro_previous_show_gizmo",
        "maya_micro_previous_show_gizmo_tool",
        "maya_micro_previous_show_gizmo_context",
    )

    for property_name in property_names:
        if hasattr(bpy.types.WindowManager, property_name):
            try:
                delattr(bpy.types.WindowManager, property_name)
            except Exception:
                pass


def _micro_average_vectors(vectors):
    if not vectors:
        return None

    total = mathutils.Vector((0.0, 0.0, 0.0))

    for vector in vectors:
        total += vector

    return total / len(vectors)


def _micro_bounding_box_center(vectors):
    if not vectors:
        return None

    min_value = vectors[0].copy()
    max_value = vectors[0].copy()

    for vector in vectors[1:]:
        min_value.x = min(min_value.x, vector.x)
        min_value.y = min(min_value.y, vector.y)
        min_value.z = min(min_value.z, vector.z)

        max_value.x = max(max_value.x, vector.x)
        max_value.y = max(max_value.y, vector.y)
        max_value.z = max(max_value.z, vector.z)

    return (min_value + max_value) * 0.5


def _micro_edit_mesh_active_position(context, obj, bm):
    try:
        active = bm.select_history.active
    except Exception:
        active = None

    if active is None:
        return None

    local_position = None

    if isinstance(active, bmesh.types.BMVert):
        local_position = active.co.copy()

    elif isinstance(active, bmesh.types.BMEdge):
        local_position = (
            active.verts[0].co +
            active.verts[1].co
        ) * 0.5

    elif isinstance(active, bmesh.types.BMFace):
        local_position = active.calc_center_median()

    if local_position is None:
        return None

    try:
        return obj.matrix_world @ local_position
    except Exception:
        return None


def _micro_edit_mesh_positions(context, obj):
    if obj is None or obj.type != 'MESH':
        return [], None

    try:
        bm = bmesh.from_edit_mesh(obj.data)
    except Exception:
        return [], None

    positions = []

    try:
        for vertex in bm.verts:
            if vertex.select:
                positions.append(
                    obj.matrix_world @ vertex.co
                )
    except Exception:
        positions = []

    active_position = _micro_edit_mesh_active_position(
        context,
        obj,
        bm,
    )

    return positions, active_position


def _micro_pose_bone_world_matrix(context, pose_bone):
    obj = getattr(context, "active_object", None)

    if obj is None or pose_bone is None:
        return None

    try:
        return obj.matrix_world @ pose_bone.matrix
    except Exception:
        return None


def _micro_pose_positions(context):
    positions = []

    try:
        selected_pose_bones = context.selected_pose_bones or []
    except Exception:
        selected_pose_bones = []

    for pose_bone in selected_pose_bones:
        matrix = _micro_pose_bone_world_matrix(
            context,
            pose_bone,
        )

        if matrix is not None:
            positions.append(matrix.translation.copy())

    active_position = None

    try:
        active_pose_bone = context.active_pose_bone
    except Exception:
        active_pose_bone = None

    if active_pose_bone is not None:
        matrix = _micro_pose_bone_world_matrix(
            context,
            active_pose_bone,
        )

        if matrix is not None:
            active_position = matrix.translation.copy()

    return positions, active_position


def _micro_object_positions(context):
    try:
        selected_objects = list(context.selected_objects or [])
    except Exception:
        selected_objects = []

    origin_positions = []
    bounding_positions = []

    for obj in selected_objects:
        try:
            origin_positions.append(
                obj.matrix_world.translation.copy()
            )
        except Exception:
            pass

        try:
            for corner in obj.bound_box:
                bounding_positions.append(
                    obj.matrix_world @ mathutils.Vector(corner)
                )
        except Exception:
            pass

    active_position = None
    active_object = getattr(context, "active_object", None)

    if active_object is not None:
        try:
            active_position = (
                active_object.matrix_world.translation.copy()
            )
        except Exception:
            pass

    return (
        origin_positions,
        bounding_positions,
        active_position,
    )


def get_micro_manipulator_pivot(context):
    try:
        pivot_mode = context.scene.tool_settings.transform_pivot_point
    except Exception:
        pivot_mode = 'MEDIAN_POINT'

    if pivot_mode == 'CURSOR':
        try:
            return context.scene.cursor.location.copy()
        except Exception:
            return mathutils.Vector((0.0, 0.0, 0.0))

    if context.mode == 'POSE':
        positions, active_position = _micro_pose_positions(context)

        if pivot_mode == 'ACTIVE_ELEMENT' and active_position is not None:
            return active_position

        if pivot_mode == 'BOUNDING_BOX_CENTER':
            center = _micro_bounding_box_center(positions)
        else:
            center = _micro_average_vectors(positions)

        if center is not None:
            return center

        if active_position is not None:
            return active_position

    if context.mode == 'EDIT_MESH':
        obj = getattr(context, "active_object", None)

        positions, active_position = _micro_edit_mesh_positions(
            context,
            obj,
        )

        if pivot_mode == 'ACTIVE_ELEMENT' and active_position is not None:
            return active_position

        if pivot_mode == 'BOUNDING_BOX_CENTER':
            center = _micro_bounding_box_center(positions)
        else:
            center = _micro_average_vectors(positions)

        if center is not None:
            return center

        if active_position is not None:
            return active_position

    (
        origin_positions,
        bounding_positions,
        active_position,
    ) = _micro_object_positions(context)

    if pivot_mode == 'ACTIVE_ELEMENT' and active_position is not None:
        return active_position

    if pivot_mode == 'BOUNDING_BOX_CENTER':
        center = _micro_bounding_box_center(
            bounding_positions or origin_positions
        )
    else:
        center = _micro_average_vectors(origin_positions)

    if center is not None:
        return center

    if active_position is not None:
        return active_position

    active_object = getattr(context, "active_object", None)

    if active_object is not None:
        try:
            return active_object.matrix_world.translation.copy()
        except Exception:
            pass

    return mathutils.Vector((0.0, 0.0, 0.0))


def _micro_active_transform_matrix(context):
    if context.mode == 'POSE':
        try:
            active_pose_bone = context.active_pose_bone
        except Exception:
            active_pose_bone = None

        matrix = _micro_pose_bone_world_matrix(
            context,
            active_pose_bone,
        )

        if matrix is not None:
            return matrix

    active_object = getattr(context, "active_object", None)

    if active_object is not None:
        try:
            return active_object.matrix_world.copy()
        except Exception:
            pass

    return mathutils.Matrix.Identity(4)


def _micro_active_rotation_target(context):
    if context.mode == 'POSE':
        try:
            if context.active_pose_bone is not None:
                return context.active_pose_bone
        except Exception:
            pass

    return getattr(context, "active_object", None)


def _micro_matrix_axes(matrix):
    try:
        matrix_3x3 = matrix.to_3x3()
    except Exception:
        matrix_3x3 = mathutils.Matrix.Identity(3)

    axes = []

    for index in range(3):
        try:
            axis = matrix_3x3.col[index].copy()
        except Exception:
            axis = mathutils.Vector((0.0, 0.0, 0.0))
            axis[index] = 1.0

        if axis.length_squared < 1e-12:
            axis = mathutils.Vector((0.0, 0.0, 0.0))
            axis[index] = 1.0
        else:
            axis.normalize()

        axes.append(axis)

    return axes


def _micro_gimbal_axes(context):
    final_matrix = _micro_active_transform_matrix(context)
    local_axes = _micro_matrix_axes(final_matrix)

    target = _micro_active_rotation_target(context)

    if target is None:
        return local_axes

    rotation_mode = getattr(target, "rotation_mode", 'XYZ')

    if rotation_mode in {'QUATERNION', 'AXIS_ANGLE'}:
        return local_axes

    if rotation_mode not in {
        'XYZ',
        'XZY',
        'YXZ',
        'YZX',
        'ZXY',
        'ZYX',
    }:
        return local_axes

    try:
        euler = target.rotation_euler.copy()
        base_quaternion = euler.to_quaternion()
        final_quaternion = final_matrix.to_quaternion()

        parent_quaternion = (
            final_quaternion @ base_quaternion.inverted()
        )
    except Exception:
        return local_axes

    axes = []
    epsilon = 1e-5

    for index in range(3):
        try:
            perturbed = euler.copy()
            perturbed[index] += epsilon

            perturbed_quaternion = perturbed.to_quaternion()

            delta = (
                perturbed_quaternion @
                base_quaternion.inverted()
            )

            axis = delta.axis.copy()

            if axis.length_squared < 1e-12:
                axis = mathutils.Vector((0.0, 0.0, 0.0))
                axis[index] = 1.0

            axis = parent_quaternion @ axis

            if axis.length_squared < 1e-12:
                axis = local_axes[index]
            else:
                axis.normalize()

            axes.append(axis)

        except Exception:
            axes.append(local_axes[index])

    return axes


def get_micro_manipulator_axes(context, orientation):
    if orientation == 'GLOBAL':
        return (
            mathutils.Vector((1.0, 0.0, 0.0)),
            mathutils.Vector((0.0, 1.0, 0.0)),
            mathutils.Vector((0.0, 0.0, 1.0)),
        )

    if orientation == 'GIMBAL':
        return tuple(_micro_gimbal_axes(context))

    matrix = _micro_active_transform_matrix(context)
    return tuple(_micro_matrix_axes(matrix))


def _micro_axis_matrix(origin, axis):
    axis = axis.copy()

    if axis.length_squared < 1e-12:
        axis = mathutils.Vector((0.0, 0.0, 1.0))
    else:
        axis.normalize()

    world_y = mathutils.Vector((0.0, 1.0, 0.0))

    if abs(axis.dot(world_y)) > 0.999:
        up_axis = 'X'
    else:
        up_axis = 'Y'

    try:
        quaternion = axis.to_track_quat('Z', up_axis)
        matrix = quaternion.to_matrix().to_4x4()
    except Exception:
        matrix = mathutils.Matrix.Identity(4)

    matrix.translation = origin
    return matrix


def _micro_active_tool_idname(context):
    try:
        tool = context.workspace.tools.from_space_view3d_mode(
            context.mode,
            create=False,
        )

        if tool is not None:
            return tool.idname
    except Exception:
        pass

    return ""


def get_micro_manipulator_visible_mode(context):
    """常にW / E / Rの現在ツールに連動する（AUTO固定）。"""
    tool_idname = _micro_active_tool_idname(context)

    if tool_idname == 'builtin.rotate':
        return 'ROTATE'

    if tool_idname == 'builtin.scale':
        return 'SCALE'

    return 'MOVE'


def _safe_setattr(target, name, value):
    try:
        setattr(target, name, value)
        return True
    except Exception:
        return False


class VIEW3D_OT_maya_set_transform_orientation(bpy.types.Operator):
    bl_idname = "view3d.maya_set_transform_orientation"
    bl_label = "マニピュレーター方向を設定"

    # 'UNDO' が必須。
    # transform_orientation_slots はシーンデータのため
    # アンドゥステップに記録されるが、'UNDO' が無いと
    # この変更自体のステップが積まれず、直前のステップには
    # 変更前の方向が残ったままになる。
    # その状態でマニピュレーター操作などをして Z（ed.undo）を
    # 1回押すと、数値の巻き戻しと同時に方向設定まで
    # 一緒に戻ってしまう。
    bl_options = {'REGISTER', 'UNDO'}

    orientation: bpy.props.EnumProperty(
        name="Transform Orientation",
        items=(
            ('GLOBAL', "Global", "ワールド座標に合わせる"),
            ('LOCAL', "Local", "アクティブ対象のローカル座標に合わせる"),
            ('GIMBAL', "Gimbal", "Euler回転軸に合わせる"),
        ),
        default='GLOBAL',
    )

    def execute(self, context):
        if not set_transform_orientation(
            context,
            self.orientation,
        ):
            self.report(
                {'WARNING'},
                "Transform Orientationを変更できませんでした。",
            )
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Manipulator Orientation: {self.orientation}",
        )
        return {'FINISHED'}


class VIEW3D_OT_maya_toggle_micro_manipulator(bpy.types.Operator):
    bl_idname = "view3d.maya_toggle_micro_manipulator"
    bl_label = "Micro Manipulator切替"
    bl_options = {'REGISTER'}

    enable: bpy.props.BoolProperty(
        name="有効",
        default=True,
    )

    def execute(self, context):
        wm = context.window_manager

        wm.maya_micro_manipulator_enabled = self.enable

        apply_maya_micro_space_visibility(
            context,
            self.enable,
        )

        tag_all_view3d_redraw()

        if self.enable:
            self.report(
                {'INFO'},
                "Micro Manipulator: ON（約1/10感度）",
            )
        else:
            self.report(
                {'INFO'},
                "Micro Manipulator: OFF",
            )

        return {'FINISHED'}


def _interaction_mode_id(context_mode):
    """context.mode を Object / Edit / Pose の3分類へ変換する。"""
    if context_mode == 'POSE':
        return 'POSE'

    if context_mode.startswith('EDIT'):
        return 'EDIT'

    if context_mode == 'OBJECT':
        return 'OBJECT'

    return ''


class VIEW3D_OT_maya_set_interaction_mode(bpy.types.Operator):
    bl_idname = "view3d.maya_set_interaction_mode"
    bl_label = "モード切替 (Maya)"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=(
            ('OBJECT', "Object Mode", "オブジェクトモードに切り替える"),
            ('EDIT', "Edit Mode", "編集モードに切り替える"),
            ('POSE', "Pose Mode", "ポーズモードに切り替える"),
        ),
        default='OBJECT',
    )

    def execute(self, context):
        active = getattr(context, "active_object", None)

        if active is None:
            self.report(
                {'WARNING'},
                "アクティブオブジェクトがありません。",
            )
            return {'CANCELLED'}

        current = _interaction_mode_id(context.mode)

        if current == self.mode:
            self.report(
                {'INFO'},
                f"すでに {self.mode} モードです。",
            )
            return {'FINISHED'}

        if self.mode == 'POSE' and active.type != 'ARMATURE':
            self.report(
                {'WARNING'},
                "Pose Modeはアーマチュアのみ使用できます。",
            )
            return {'CANCELLED'}

        try:
            bpy.ops.object.mode_set(mode=self.mode)
        except Exception as error:
            self.report(
                {'WARNING'},
                f"モードを切り替えられませんでした: {error}",
            )
            return {'CANCELLED'}

        tag_all_view3d_redraw()

        self.report(
            {'INFO'},
            f"モード: {self.mode}",
        )
        return {'FINISHED'}



class VIEW3D_OT_maya_call_manipulator_menu(bpy.types.Operator):
    """Ctrl+Shift+右クリック用。wm.call_menu より確実にメニューを開く。"""
    bl_idname = "view3d.maya_call_manipulator_menu"
    bl_label = "Manipulator Settings を開く"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        try:
            bpy.ops.wm.call_menu(
                name=VIEW3D_MT_maya_manipulator_menu.bl_idname,
            )
        except Exception as error:
            try:
                bpy.ops.wm.call_menu(
                    name="VIEW3D_MT_maya_manipulator_menu",
                )
            except Exception as error2:
                self.report(
                    {'WARNING'},
                    f"Manipulator Settings を開けませんでした: {error2}",
                )
                return {'CANCELLED'}

        return {'FINISHED'}


class VIEW3D_MT_maya_manipulator_menu(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_maya_manipulator_menu"
    bl_label = "Manipulator Settings"

    # 注意:
    # このメニューは box() / column() の入れ子や scale_y 調整を
    # 使わず、単純な縦一列のフローだけで構成する。
    # 入れ子レイアウトを混ぜると高さ計算が崩れて
    # 左右に大きな空白ができるため、絶対に追加しないこと。
    def draw(self, context):
        layout = self.layout

        orientation = get_current_transform_orientation(context)
        wm = context.window_manager

        layout.label(
            text="Manipulator Orientation",
            icon='ORIENTATION_GLOBAL',
        )

        for orientation_id, label in (
            ('GLOBAL', "Global"),
            ('LOCAL', "Local"),
            ('GIMBAL', "Gimbal"),
        ):
            icon = (
                'RADIOBUT_ON'
                if orientation == orientation_id
                else 'RADIOBUT_OFF'
            )

            operator = layout.operator(
                "view3d.maya_set_transform_orientation",
                text=label,
                icon=icon,
            )
            operator.orientation = orientation_id

        layout.separator()

        enabled = bool(
            getattr(
                wm,
                "maya_micro_manipulator_enabled",
                False,
            )
        )

        toggle_operator = layout.operator(
            "view3d.maya_toggle_micro_manipulator",
            text=(
                "Micro Manipulator: ON"
                if enabled
                else "Micro Manipulator: OFF"
            ),
            icon=(
                'CHECKBOX_HLT'
                if enabled
                else 'CHECKBOX_DEHLT'
            ),
        )
        toggle_operator.enable = not enabled

        layout.label(
            text="通常の約1/10の感度・W/E/R連動",
            icon='INFO',
        )

        layout.separator()

        layout.label(
            text="Interaction Mode",
            icon='OBJECT_DATAMODE',
        )

        current_mode = _interaction_mode_id(context.mode)

        for mode_id, label in (
            ('OBJECT', "Object Mode"),
            ('EDIT', "Edit Mode"),
            ('POSE', "Pose Mode"),
        ):
            icon = (
                'RADIOBUT_ON'
                if current_mode == mode_id
                else 'RADIOBUT_OFF'
            )

            operator = layout.operator(
                "view3d.maya_set_interaction_mode",
                text=label,
                icon=icon,
            )
            operator.mode = mode_id


class VIEW3D_GGT_maya_micro_manipulator(
    bpy.types.GizmoGroup
):
    bl_idname = "VIEW3D_GGT_maya_micro_manipulator"
    bl_label = "Maya Micro Manipulator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT'}

    _AXIS_COLORS = (
        (0.95, 0.12, 0.12),
        (0.20, 0.85, 0.20),
        (0.18, 0.38, 1.00),
    )

    @classmethod
    def poll(cls, context):
        wm = getattr(context, "window_manager", None)

        if wm is None:
            return False

        if not getattr(
            wm,
            "maya_micro_manipulator_enabled",
            False,
        ):
            return False

        active_object = getattr(context, "active_object", None)

        if active_object is None:
            return False

        if context.mode == 'POSE':
            try:
                return bool(context.selected_pose_bones)
            except Exception:
                return False

        if context.mode == 'EDIT_MESH':
            return True

        try:
            return bool(context.selected_objects)
        except Exception:
            return active_object is not None

    def setup(self, context):
        self._gizmo_groups = {
            'MOVE': [],
            'ROTATE': [],
            'SCALE': [],
        }

        for axis_index in range(3):
            axis_constraint = [False, False, False]
            axis_constraint[axis_index] = True
            axis_constraint = tuple(axis_constraint)

            color = self._AXIS_COLORS[axis_index]

            # ------------------------------------------------
            # Micro Move
            # ------------------------------------------------

            move_gizmo = self.gizmos.new(
                "GIZMO_GT_arrow_3d"
            )

            move_properties = move_gizmo.target_set_operator(
                "transform.translate"
            )

            _safe_setattr(
                move_properties,
                "constraint_axis",
                axis_constraint,
            )
            _safe_setattr(
                move_properties,
                "orient_type",
                'GLOBAL',
            )
            _safe_setattr(
                move_properties,
                "release_confirm",
                True,
            )
            _safe_setattr(
                move_properties,
                "use_accurate",
                True,
            )

            _safe_setattr(move_gizmo, "draw_style", 'CONE')
            _safe_setattr(move_gizmo, "use_draw_modal", True)
            _safe_setattr(move_gizmo, "use_draw_value", True)
            _safe_setattr(move_gizmo, "line_width", 2.5)

            move_gizmo.color = color
            move_gizmo.alpha = 0.8
            move_gizmo.color_highlight = (1.0, 1.0, 0.2)
            move_gizmo.alpha_highlight = 1.0
            move_gizmo.scale_basis = (
                get_micro_manipulator_gizmo_scale()
            )

            self._gizmo_groups['MOVE'].append(
                (
                    move_gizmo,
                    move_properties,
                    axis_index,
                )
            )

            # ------------------------------------------------
            # Micro Rotate
            # ------------------------------------------------

            rotate_gizmo = self.gizmos.new(
                "GIZMO_GT_dial_3d"
            )

            rotate_properties = rotate_gizmo.target_set_operator(
                "transform.rotate"
            )

            _safe_setattr(
                rotate_properties,
                "constraint_axis",
                axis_constraint,
            )
            _safe_setattr(
                rotate_properties,
                "orient_type",
                'GLOBAL',
            )
            _safe_setattr(
                rotate_properties,
                "release_confirm",
                True,
            )
            _safe_setattr(
                rotate_properties,
                "use_accurate",
                True,
            )

            _safe_setattr(rotate_gizmo, "use_draw_modal", True)
            _safe_setattr(rotate_gizmo, "use_draw_value", True)
            _safe_setattr(rotate_gizmo, "line_width", 3.0)

            rotate_gizmo.color = color
            rotate_gizmo.alpha = 0.65
            rotate_gizmo.color_highlight = (1.0, 1.0, 0.2)
            rotate_gizmo.alpha_highlight = 1.0
            rotate_gizmo.scale_basis = (
                get_micro_manipulator_gizmo_scale() * 1.15
            )

            self._gizmo_groups['ROTATE'].append(
                (
                    rotate_gizmo,
                    rotate_properties,
                    axis_index,
                )
            )

            # ------------------------------------------------
            # Micro Scale
            # ------------------------------------------------

            scale_gizmo = self.gizmos.new(
                "GIZMO_GT_arrow_3d"
            )

            scale_properties = scale_gizmo.target_set_operator(
                "transform.resize"
            )

            _safe_setattr(
                scale_properties,
                "constraint_axis",
                axis_constraint,
            )
            _safe_setattr(
                scale_properties,
                "orient_type",
                'GLOBAL',
            )
            _safe_setattr(
                scale_properties,
                "release_confirm",
                True,
            )
            _safe_setattr(
                scale_properties,
                "use_accurate",
                True,
            )

            _safe_setattr(scale_gizmo, "draw_style", 'BOX')
            _safe_setattr(scale_gizmo, "use_draw_modal", True)
            _safe_setattr(scale_gizmo, "use_draw_value", True)
            _safe_setattr(scale_gizmo, "line_width", 2.5)

            scale_gizmo.color = color
            scale_gizmo.alpha = 0.8
            scale_gizmo.color_highlight = (1.0, 1.0, 0.2)
            scale_gizmo.alpha_highlight = 1.0
            scale_gizmo.scale_basis = (
                get_micro_manipulator_gizmo_scale()
            )

            self._gizmo_groups['SCALE'].append(
                (
                    scale_gizmo,
                    scale_properties,
                    axis_index,
                )
            )

        self._update_gizmos(context)

    def refresh(self, context):
        self._update_gizmos(context)

    def draw_prepare(self, context):
        self._update_gizmos(context)

    def _update_gizmos(self, context):
        apply_maya_micro_space_visibility(
            context,
            True,
        )

        orientation = get_current_transform_orientation(
            context
        )

        visible_mode = get_micro_manipulator_visible_mode(
            context
        )

        origin = get_micro_manipulator_pivot(context)

        axes = get_micro_manipulator_axes(
            context,
            orientation,
        )

        for mode_name, gizmo_items in self._gizmo_groups.items():
            is_visible = (mode_name == visible_mode)

            for gizmo, operator_properties, axis_index in gizmo_items:
                try:
                    gizmo.hide = not is_visible
                except Exception:
                    pass

                if not is_visible:
                    continue

                _safe_setattr(
                    operator_properties,
                    "orient_type",
                    orientation,
                )
                _safe_setattr(
                    operator_properties,
                    "use_accurate",
                    True,
                )
                _safe_setattr(
                    operator_properties,
                    "release_confirm",
                    True,
                )

                try:
                    gizmo.matrix_basis = _micro_axis_matrix(
                        origin,
                        axes[axis_index],
                    )
                except Exception:
                    pass


# ============================================================
# Mayaスペースキー
# ============================================================

class VIEW3D_MT_maya_hotbox_pie(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_maya_hotbox_pie"
    bl_label = "Hotbox (Maya風)"

    def draw(self, context):
        pie = self.layout.menu_pie()
        is_pose = (context.mode == 'POSE')

        if hasattr(bpy.types, "ANIM_OT_keyframe_insert_menu"):
            pie.operator(
                "anim.keyframe_insert_menu",
                text="キー挿入...",
                icon='KEY_HLT',
            )
        else:
            pie.operator(
                "anim.keyframe_insert",
                text="キー挿入",
                icon='KEY_HLT',
            )

        pie.operator(
            "anim.keyframe_delete_v3d",
            text="キー削除",
            icon='KEY_DEHLT',
        )

        pie.operator(
            "wm.toolbar",
            text="すべてのツール",
            icon='TOOL_SETTINGS',
        )

        pie.operator(
            "screen.animation_play",
            text="再生 / 停止",
            icon='PLAY',
        )

        pie.menu(
            "VIEW3D_MT_maya_spawn_menu",
            text="オブジェクト作成",
            icon='ADD',
        )

        pie.menu(
            "VIEW3D_MT_maya_constraint_menu",
            text="コンストレイント",
            icon='CONSTRAINT',
        )

        if is_pose:
            pie.operator(
                "pose.transforms_clear",
                text="ポーズをリセット",
                icon='LOOP_BACK',
            )
        else:
            pie.operator(
                "object.posemode_toggle",
                text="Object / Pose 切替",
                icon='POSE_HLT',
            )

        pie.operator(
            "view3d.view_selected",
            text="選択にフォーカス",
            icon='ZOOM_SELECTED',
        )

        center = pie.column()

        gap = center.column()
        gap.separator()
        gap.scale_y = 7.0

        box = center.box().column()
        box.scale_y = 1.2

        box.menu(
            "VIEW3D_MT_maya_view_menu",
            text="ビュー切替",
            icon='VIEW_PERSPECTIVE',
        )


class VIEW3D_OT_maya_space(bpy.types.Operator):
    bl_idname = "view3d.maya_space"
    bl_label = "Maya Space (Tap: Quad View / Hold: Hotbox)"
    bl_options = {'REGISTER'}

    _timer = None
    _start_time = 0.0
    _mouse_x = 0
    _mouse_y = 0

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        self._start_time = time.monotonic()

        self._mouse_x = getattr(event, "mouse_x", 0)
        self._mouse_y = getattr(event, "mouse_y", 0)

        area, region, space, region_data = (
            find_view3d_area_region_under_mouse(
                context,
                self._mouse_x,
                self._mouse_y,
            )
        )

        if area is None or region is None:
            return {'PASS_THROUGH'}

        wm = context.window_manager

        self._timer = wm.event_timer_add(
            0.02,
            window=context.window,
        )

        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _remove_timer(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(
                self._timer
            )
            self._timer = None

    def _update_mouse_from_event(self, event):
        if event.type == 'TIMER':
            return

        try:
            self._mouse_x = event.mouse_x
            self._mouse_y = event.mouse_y
        except Exception:
            pass

    def modal(self, context, event):
        self._update_mouse_from_event(event)

        if event.type == 'SPACE' and event.value == 'RELEASE':
            self._remove_timer(context)

            elapsed = time.monotonic() - self._start_time

            if elapsed >= get_space_hold_time():
                self._open_hotbox(context)
            else:
                self._toggle_quad_view(context)

            return {'FINISHED'}

        if event.type == 'SPACE' and event.value == 'PRESS':
            return {'RUNNING_MODAL'}

        if event.type == 'TIMER':
            elapsed = time.monotonic() - self._start_time

            if elapsed >= get_space_hold_time():
                self._remove_timer(context)
                self._open_hotbox(context)
                return {'FINISHED'}

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self._remove_timer(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def _open_hotbox(self, context):
        area, region, space, region_data = (
            find_view3d_area_region_under_mouse(
                context,
                self._mouse_x,
                self._mouse_y,
            )
        )

        try:
            call_menu_pie_for_region(
                context,
                VIEW3D_MT_maya_hotbox_pie.bl_idname,
                area,
                region,
                space,
                region_data,
            )
        except Exception as error:
            self.report(
                {'WARNING'},
                f"Hotboxを開けませんでした: {error}",
            )

    def _toggle_quad_view(self, context):
        area, region, space, region_data = (
            find_view3d_area_region_under_mouse(
                context,
                self._mouse_x,
                self._mouse_y,
            )
        )

        try:
            if (
                space is not None and
                is_view3d_quadview(space) and
                region_data is not None
            ):
                main_region_data = None

                try:
                    main_region_data = space.region_3d
                except Exception:
                    pass

                copy_region_view3d_state(
                    region_data,
                    main_region_data,
                )

            call_region_quadview_for_region(
                context,
                area,
                region,
                space,
                region_data,
            )

            try:
                if area is not None:
                    area.tag_redraw()
            except Exception:
                pass

        except Exception as error:
            self.report(
                {'WARNING'},
                f"ビュー切替に失敗しました: {error}",
            )

    def cancel(self, context):
        self._remove_timer(context)


# ============================================================
# Graph D Key (Tap: Auto Clamped / Hold: Handle Menu)
# ============================================================

class GRAPH_MT_maya_handle_type_menu(bpy.types.Menu):
    bl_idname = "GRAPH_MT_maya_handle_type_menu"
    bl_label = "Handle Type"

    def draw(self, context):
        layout = self.layout
        layout.operator("graph.handle_type", text="Free").type = 'FREE'
        layout.operator("graph.handle_type", text="Aligned").type = 'ALIGNED'
        layout.operator("graph.handle_type", text="Vector").type = 'VECTOR'
        layout.operator("graph.handle_type", text="Auto").type = 'AUTO'
        layout.operator("graph.handle_type", text="Auto Clamped").type = 'AUTO_CLAMPED'


class GRAPH_OT_maya_d_key(bpy.types.Operator):
    bl_idname = "graph.maya_d_key"
    bl_label = "Maya D Key (Tap: Auto Clamped / Hold: Handle Menu)"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    _start_time = 0.0

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'GRAPH_EDITOR':
            return {'PASS_THROUGH'}

        self._start_time = time.monotonic()

        wm = context.window_manager
        self._timer = wm.event_timer_add(
            0.02,
            window=context.window,
        )

        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _remove_timer(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

    def modal(self, context, event):
        if event.type == 'D' and event.value == 'RELEASE':
            self._remove_timer(context)

            elapsed = time.monotonic() - self._start_time

            if elapsed >= get_space_hold_time():
                self._open_menu(context)
            else:
                self._apply_auto_clamped(context)

            return {'FINISHED'}

        if event.type == 'D' and event.value == 'PRESS':
            return {'RUNNING_MODAL'}

        if event.type == 'TIMER':
            elapsed = time.monotonic() - self._start_time

            if elapsed >= get_space_hold_time():
                self._remove_timer(context)
                self._open_menu(context)
                return {'FINISHED'}

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self._remove_timer(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def _apply_auto_clamped(self, context):
        try:
            bpy.ops.graph.handle_type(type='AUTO_CLAMPED')
        except Exception as e:
            self.report({'WARNING'}, f"Auto Clampedの適用に失敗しました: {e}")

    def _open_menu(self, context):
        try:
            bpy.ops.wm.call_menu(name=GRAPH_MT_maya_handle_type_menu.bl_idname)
        except Exception as e:
            self.report({'WARNING'}, f"メニューの表示に失敗しました: {e}")

    def cancel(self, context):
        self._remove_timer(context)


# ============================================================
# Alt+1 = コントローラー表示切替
# ============================================================

class VIEW3D_OT_maya_toggle_controllers(bpy.types.Operator):
    bl_idname = "view3d.maya_toggle_controllers"
    bl_label = "コントローラー表示切替 (Maya Alt+1)"
    bl_options = {'REGISTER'}

    def _find_space(self, context, event=None):
        space = None

        if event is not None:
            mouse_x = getattr(event, "mouse_x", None)
            mouse_y = getattr(event, "mouse_y", None)

            (
                _area,
                _region,
                space,
                _region_data,
            ) = find_view3d_area_region_under_mouse(
                context,
                mouse_x,
                mouse_y,
            )

        if space is None or getattr(space, "type", None) != 'VIEW_3D':
            candidate = getattr(context, "space_data", None)

            if (
                candidate is not None and
                getattr(candidate, "type", None) == 'VIEW_3D'
            ):
                space = candidate
            else:
                space = None

        if space is None:
            space = find_any_view3d_space(context)

        return space

    def _toggle(self, context, space):
        if space is None:
            self.report(
                {'WARNING'},
                "3D Viewが見つかりませんでした。",
            )
            return {'CANCELLED'}

        try:
            overlay = space.overlay
        except Exception:
            self.report(
                {'WARNING'},
                "オーバーレイ設定を取得できませんでした。",
            )
            return {'CANCELLED'}

        show = not overlay.show_bones
        overlay.show_bones = show

        if get_alt1_also_toggle_empties():
            try:
                space.show_object_viewport_empty = show
            except Exception:
                pass

        try:
            for area in context.window.screen.areas:
                if (
                    area.type == 'VIEW_3D' and
                    area.spaces.active == space
                ):
                    area.tag_redraw()
        except Exception:
            pass

        self.report(
            {'INFO'},
            (
                "コントローラー: 表示"
                if show
                else "コントローラー: 非表示"
            ),
        )

        return {'FINISHED'}

    def invoke(self, context, event):
        return self._toggle(
            context,
            self._find_space(context, event),
        )

    def execute(self, context):
        return self._toggle(
            context,
            self._find_space(context),
        )


# ============================================================
# Alt+W / Alt+S = キーフレームジャンプ
# ============================================================

class SCREEN_OT_maya_keyframe_jump(bpy.types.Operator):
    bl_idname = "screen.maya_keyframe_jump"
    bl_label = "キーフレームジャンプ (Maya Alt+W/S)"
    bl_description = (
        "選択オブジェクトの前後キーフレームへ移動。"
        "マウス位置に関係なく動作する"
    )
    bl_options = {'REGISTER'}

    next: bpy.props.BoolProperty(
        name="次のキーフレームへ",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        # エリア依存にしない。どこからでも実行可能にする。
        return getattr(context, "scene", None) is not None

    @staticmethod
    def _iter_action_fcurves(action):
        if action is None:
            return

        # Blender 4.4+ layered actions
        try:
            layers = getattr(action, "layers", None)
            if layers:
                for layer in layers:
                    for strip in getattr(layer, "strips", []) or []:
                        ch_bag = getattr(strip, "channelbag", None)
                        if ch_bag is None:
                            continue
                        for fcurve in getattr(ch_bag, "fcurves", []) or []:
                            yield fcurve
                return
        except Exception:
            pass

        try:
            for fcurve in action.fcurves:
                yield fcurve
        except Exception:
            pass

    @classmethod
    def _collect_from_id(cls, id_data, frames):
        if id_data is None:
            return

        anim = getattr(id_data, "animation_data", None)
        if anim is None:
            return

        action = getattr(anim, "action", None)
        if action is None:
            return

        try:
            for fcurve in cls._iter_action_fcurves(action):
                try:
                    for keyframe_point in fcurve.keyframe_points:
                        frames.add(float(keyframe_point.co.x))
                except Exception:
                    pass
        except Exception:
            pass

    @classmethod
    def _gather_objects(cls, context):
        """エリア context に依存せず選択オブジェクトを集める。"""
        objects = set()

        # 1) 通常 context
        try:
            for obj in (context.selected_objects or []):
                objects.add(obj)
        except Exception:
            pass

        try:
            if context.active_object is not None:
                objects.add(context.active_object)
        except Exception:
            pass

        # 2) view_layer から直接（Properties 等でも有効）
        try:
            view_layer = context.view_layer
            if view_layer is not None:
                for obj in view_layer.objects:
                    try:
                        if obj.select_get():
                            objects.add(obj)
                    except Exception:
                        pass

                active = getattr(view_layer.objects, "active", None)
                if active is not None:
                    objects.add(active)
        except Exception:
            pass

        # 3) 全ウィンドウの view_layer も見る（コンテキスト欠落時）
        if not objects:
            try:
                for window in context.window_manager.windows:
                    screen = window.screen
                    if screen is None:
                        continue
                    # window.view_layer があれば優先
                    vl = getattr(window, "view_layer", None)
                    if vl is None:
                        continue
                    for obj in vl.objects:
                        try:
                            if obj.select_get():
                                objects.add(obj)
                        except Exception:
                            pass
                    active = getattr(vl.objects, "active", None)
                    if active is not None:
                        objects.add(active)
            except Exception:
                pass

        return objects

    @classmethod
    def _collect_keyframes(cls, context):
        frames = set()
        objects = cls._gather_objects(context)

        for obj in objects:
            cls._collect_from_id(obj, frames)

            # ポーズボーン固有の action は object 側 animation_data に含まれる
            data = getattr(obj, "data", None)
            if data is not None:
                cls._collect_from_id(data, frames)

                shape_keys = getattr(data, "shape_keys", None)
                if shape_keys is not None:
                    cls._collect_from_id(shape_keys, frames)

            # マテリアル等（選択オブジェクトの）
            try:
                for slot in getattr(obj, "material_slots", []) or []:
                    mat = getattr(slot, "material", None)
                    if mat is not None:
                        cls._collect_from_id(mat, frames)
                        if getattr(mat, "node_tree", None) is not None:
                            cls._collect_from_id(mat.node_tree, frames)
            except Exception:
                pass

        return frames, objects

    def invoke(self, context, event):
        # マウス下エリアに依存せず execute へ
        return self.execute(context)

    def execute(self, context):
        scene = context.scene
        if scene is None:
            self.report({'WARNING'}, "シーンがありません。")
            return {'CANCELLED'}

        frames, objects = self._collect_keyframes(context)

        if not frames:
            # 選択にキーが無い場合のみグローバルジャンプを試す
            try:
                result = bpy.ops.screen.keyframe_jump(next=self.next)
                if 'FINISHED' in result:
                    self._tag_redraw(context)
                    return {'FINISHED'}
            except Exception:
                pass

            if not objects:
                self.report(
                    {'INFO'},
                    "オブジェクトが選択されていません。",
                )
            else:
                self.report(
                    {'INFO'},
                    "選択オブジェクトにキーフレームがありません。",
                )
            return {'CANCELLED'}

        try:
            current = float(scene.frame_current_final)
        except Exception:
            current = float(scene.frame_current)

        epsilon = 1e-4

        if self.next:
            candidates = [
                frame
                for frame in frames
                if frame > current + epsilon
            ]
            target = min(candidates) if candidates else None
        else:
            candidates = [
                frame
                for frame in frames
                if frame < current - epsilon
            ]
            target = max(candidates) if candidates else None

        if target is None:
            self.report(
                {'INFO'},
                "これ以上キーフレームがありません。",
            )
            return {'CANCELLED'}

        frame = int(math.floor(target + 1e-6))
        subframe = float(target) - float(frame)

        try:
            scene.frame_set(frame, subframe=subframe)
        except TypeError:
            scene.frame_set(frame)
        except Exception as error:
            self.report(
                {'WARNING'},
                f"フレーム移動に失敗しました: {error}",
            )
            return {'CANCELLED'}

        self._tag_redraw(context)
        return {'FINISHED'}

    @staticmethod
    def _tag_redraw(context):
        try:
            for window in context.window_manager.windows:
                screen = window.screen
                if screen is None:
                    continue
                for area in screen.areas:
                    try:
                        area.tag_redraw()
                    except Exception:
                        pass
        except Exception:
            pass


# ============================================================
# S = キーフレーム挿入（Maya Set Key）
# マウス位置に依存せず、選択オブジェクトに対して動作する
# ============================================================

class SCREEN_OT_maya_keyframe_insert(bpy.types.Operator):
    bl_idname = "screen.maya_keyframe_insert"
    bl_label = "キーフレーム挿入 (Maya S)"
    bl_description = (
        "選択オブジェクト / ボーンにキーを打つ。"
        "ビューポート外でも同じ動作"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return getattr(context, "scene", None) is not None

    @staticmethod
    def _gather_objects(context):
        objects = set()

        try:
            for obj in (context.selected_objects or []):
                objects.add(obj)
        except Exception:
            pass

        try:
            if context.active_object is not None:
                objects.add(context.active_object)
        except Exception:
            pass

        try:
            view_layer = context.view_layer
            if view_layer is not None:
                for obj in view_layer.objects:
                    try:
                        if obj.select_get():
                            objects.add(obj)
                    except Exception:
                        pass
                active = getattr(view_layer.objects, "active", None)
                if active is not None:
                    objects.add(active)
        except Exception:
            pass

        if not objects:
            try:
                for window in context.window_manager.windows:
                    vl = getattr(window, "view_layer", None)
                    if vl is None:
                        continue
                    for obj in vl.objects:
                        try:
                            if obj.select_get():
                                objects.add(obj)
                        except Exception:
                            pass
                    active = getattr(vl.objects, "active", None)
                    if active is not None:
                        objects.add(active)
            except Exception:
                pass

        return objects

    @staticmethod
    def _tag_redraw(context):
        try:
            for window in context.window_manager.windows:
                screen = window.screen
                if screen is None:
                    continue
                for area in screen.areas:
                    try:
                        area.tag_redraw()
                    except Exception:
                        pass
        except Exception:
            pass

    def _try_ops_keyframe_insert(self, context):
        """Blender 標準のキー挿入を、メニューを出さずに実行する。"""
        # Industry Compatible の S に近い順で試す
        attempt_specs = [
            # (callable_factory,)
            ('anim.keyframe_insert', {}),
            ('anim.keyframe_insert', {'type': 'AVAILABLE'}),
            ('anim.keyframe_insert', {'type': 'DEFAULT'}),
            ('anim.keyframe_insert_by_name', {'type': 'Available'}),
            ('anim.keyframe_insert_by_name', {'type': 'LocRotScale'}),
            ('anim.keyframe_insert', {'type': 'LocRotScale'}),
            ('anim.keyframe_insert_menu', {
                'type': '__ACTIVE__',
                'always_prompt': False,
            }),
        ]

        for op_id, kwargs in attempt_specs:
            try:
                parts = op_id.split('.')
                op = bpy.ops
                for part in parts:
                    op = getattr(op, part)

                # always_prompt 非対応環境向け
                try:
                    result = op(**kwargs)
                except TypeError:
                    kwargs2 = dict(kwargs)
                    kwargs2.pop('always_prompt', None)
                    try:
                        result = op(**kwargs2)
                    except TypeError:
                        # type 引数なし
                        if not kwargs:
                            raise
                        try:
                            result = op()
                        except Exception:
                            continue

                if result is not None and 'FINISHED' in result:
                    return True
            except Exception:
                continue

        return False

    def _manual_insert_on_targets(self, context):
        """オペレーターが使えない場合の直接 keyframe_insert。"""
        objects = self._gather_objects(context)
        if not objects:
            return 0

        inserted = 0
        try:
            frame = context.scene.frame_current
        except Exception:
            frame = None

        is_pose = (getattr(context, "mode", "") == 'POSE')

        if is_pose:
            pose_bones = []
            try:
                pose_bones = list(context.selected_pose_bones or [])
            except Exception:
                pose_bones = []

            if not pose_bones:
                try:
                    if context.active_pose_bone is not None:
                        pose_bones = [context.active_pose_bone]
                except Exception:
                    pass

            for pose_bone in pose_bones:
                for data_path in (
                    "location",
                    "rotation_euler",
                    "rotation_quaternion",
                    "rotation_axis_angle",
                    "scale",
                ):
                    try:
                        if frame is not None:
                            ok = pose_bone.keyframe_insert(data_path, frame=frame)
                        else:
                            ok = pose_bone.keyframe_insert(data_path)
                        if ok:
                            inserted += 1
                    except Exception:
                        pass
            return inserted

        for obj in objects:
            # 回転モードに合わせたパス
            rot_paths = ["rotation_euler", "rotation_quaternion", "rotation_axis_angle"]
            mode = getattr(obj, "rotation_mode", 'XYZ')
            if mode == 'QUATERNION':
                rot_paths = ["rotation_quaternion"]
            elif mode == 'AXIS_ANGLE':
                rot_paths = ["rotation_axis_angle"]
            else:
                rot_paths = ["rotation_euler"]

            data_paths = ["location"] + rot_paths + ["scale"]

            for data_path in data_paths:
                try:
                    if frame is not None:
                        ok = obj.keyframe_insert(data_path, frame=frame)
                    else:
                        ok = obj.keyframe_insert(data_path)
                    if ok:
                        inserted += 1
                except Exception:
                    pass

        return inserted

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        objects = self._gather_objects(context)

        if not objects and getattr(context, "mode", "") != 'POSE':
            self.report({'INFO'}, "キーを打つ対象が選択されていません。")
            return {'CANCELLED'}

        # まず標準オペレーター（キーイングセット対応）
        if self._try_ops_keyframe_insert(context):
            self._tag_redraw(context)
            self.report({'INFO'}, "キーフレームを挿入しました。")
            return {'FINISHED'}

        # フォールバック: 直接挿入
        count = self._manual_insert_on_targets(context)
        if count > 0:
            self._tag_redraw(context)
            self.report(
                {'INFO'},
                f"キーフレームを挿入しました（{count} チャンネル）。",
            )
            return {'FINISHED'}

        self.report(
            {'WARNING'},
            "キーフレームを挿入できませんでした。"
            "キーイングセットまたは選択を確認してください。",
        )
        return {'CANCELLED'}


# ============================================================
# Alt+* = トランスフォーム初期化 /
#          選択キーフレームのデフォルト化
# ============================================================

class OBJECT_OT_maya_reset_transforms(bpy.types.Operator):
    bl_idname = "object.maya_reset_transforms"
    bl_label = "トランスフォームを初期化 (Maya Alt+*)"
    bl_options = {'REGISTER', 'UNDO'}

    _ANIM_EDITOR_AREA_TYPES = {
        'GRAPH_EDITOR',
        'DOPESHEET_EDITOR',
    }

    # --------------------------------------------------------
    # 選択キーフレームのデフォルト化
    # --------------------------------------------------------

    @staticmethod
    def _default_channel_value(data_path, array_index):
        """トランスフォーム系チャンネルのデフォルト値を返す。
        対象外のチャンネルは None を返す。
        pose.bones["..."].location のようなパスにも対応する。
        """
        if not data_path:
            return None

        if data_path.endswith("rotation_quaternion"):
            return 1.0 if array_index == 0 else 0.0

        if data_path.endswith("rotation_axis_angle"):
            # デフォルト (0.0, 0.0, 1.0, 0.0)
            return 1.0 if array_index == 2 else 0.0

        if data_path.endswith("scale"):
            # scale / delta_scale
            return 1.0

        if data_path.endswith("location"):
            # location / delta_location
            return 0.0

        if data_path.endswith("rotation_euler"):
            # rotation_euler / delta_rotation_euler
            return 0.0

        return None

    @staticmethod
    def _collect_anim_fcurves(context):
        fcurves = []

        try:
            fcurves = list(context.editable_fcurves or [])
        except Exception:
            fcurves = []

        if not fcurves:
            try:
                fcurves = list(context.visible_fcurves or [])
            except Exception:
                fcurves = []

        if not fcurves:
            objects = set()

            try:
                objects.update(context.selected_objects or [])
            except Exception:
                pass

            try:
                if context.active_object is not None:
                    objects.add(context.active_object)
            except Exception:
                pass

            for obj in objects:
                anim = getattr(obj, "animation_data", None)

                if anim is None or anim.action is None:
                    continue

                try:
                    fcurves.extend(anim.action.fcurves)
                except Exception:
                    pass

        return [
            fcurve
            for fcurve in fcurves
            if (
                not getattr(fcurve, "lock", False) and
                not getattr(fcurve, "hide", False)
            )
        ]

    def _execute_selected_keyframe_reset(self, context):
        """選択中のキーフレームだけをデフォルト値に戻す。
        現在フレーム上のキーでも、選択されていなければ触らない。
        ハンドルは同じ差分で移動させ、カーブ形状を保つ。
        """
        key_count = 0
        curve_count = 0
        skipped_channel_count = 0
        total_selected_points_count = 0

        for fcurve in self._collect_anim_fcurves(context):
            try:
                selected_points = [
                    keyframe_point
                    for keyframe_point in fcurve.keyframe_points
                    if keyframe_point.select_control_point
                ]
            except Exception:
                continue

            if not selected_points:
                continue
                
            total_selected_points_count += len(selected_points)

            default_value = self._default_channel_value(
                getattr(fcurve, "data_path", ""),
                getattr(fcurve, "array_index", 0),
            )

            if default_value is None:
                # トランスフォーム以外のチャンネルは対象外。
                skipped_channel_count += 1
                continue

            for keyframe_point in selected_points:
                try:
                    delta = default_value - keyframe_point.co.y

                    keyframe_point.co.y = default_value
                    keyframe_point.handle_left.y += delta
                    keyframe_point.handle_right.y += delta

                    key_count += 1
                except Exception:
                    pass

            try:
                fcurve.update()
            except Exception:
                pass

            curve_count += 1

        if total_selected_points_count == 0:
            return {'PASS_THROUGH'}

        if key_count == 0:
            self.report(
                {'INFO'},
                "選択キーフレームはトランスフォーム系"
                "チャンネルではないため対象外です。",
            )
            return {'CANCELLED'}

        try:
            for area in context.window.screen.areas:
                if area.type in {
                    'VIEW_3D',
                    'DOPESHEET_EDITOR',
                    'GRAPH_EDITOR',
                    'NLA_EDITOR',
                }:
                    area.tag_redraw()
        except Exception:
            pass

        message = (
            f"{curve_count} 本のカーブで {key_count} 個の"
            "選択キーフレームをデフォルト値に戻しました。"
        )

        if skipped_channel_count > 0:
            message += (
                f"（対象外チャンネル {skipped_channel_count} 本は"
                "スキップ）"
            )

        self.report({'INFO'}, message)
        return {'FINISHED'}

    # --------------------------------------------------------
    # 従来のトランスフォーム初期化
    # --------------------------------------------------------

    @staticmethod
    def _reset_transform_channels(target, include_delta=False):
        try:
            target.location = (0.0, 0.0, 0.0)
        except Exception:
            pass

        try:
            target.rotation_euler = (0.0, 0.0, 0.0)
        except Exception:
            pass

        try:
            target.rotation_quaternion = (
                1.0,
                0.0,
                0.0,
                0.0,
            )
        except Exception:
            pass

        try:
            target.rotation_axis_angle = (
                0.0,
                0.0,
                1.0,
                0.0,
            )
        except Exception:
            pass

        try:
            target.scale = (1.0, 1.0, 1.0)
        except Exception:
            pass

        if include_delta:
            try:
                target.delta_location = (0.0, 0.0, 0.0)
            except Exception:
                pass

            try:
                target.delta_rotation_euler = (
                    0.0,
                    0.0,
                    0.0,
                )
            except Exception:
                pass

            try:
                target.delta_rotation_quaternion = (
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                )
            except Exception:
                pass

            try:
                target.delta_scale = (1.0, 1.0, 1.0)
            except Exception:
                pass

    @staticmethod
    def _autokey_enabled(context):
        try:
            return bool(
                context.scene.tool_settings.use_keyframe_insert_auto
            )
        except Exception:
            return False

    @staticmethod
    def _rotation_data_path(target):
        mode = getattr(target, "rotation_mode", 'XYZ')

        if mode == 'QUATERNION':
            return "rotation_quaternion"

        if mode == 'AXIS_ANGLE':
            return "rotation_axis_angle"

        return "rotation_euler"

    @classmethod
    def _insert_reset_keys(
        cls,
        context,
        target,
        include_delta=False,
    ):
        try:
            frame = context.scene.frame_current
        except Exception:
            frame = None

        options = set()

        try:
            if getattr(
                context.preferences.edit,
                "use_keyframe_insert_available",
                False,
            ):
                options.add('INSERTKEY_AVAILABLE')
        except Exception:
            pass

        data_paths = [
            "location",
            cls._rotation_data_path(target),
            "scale",
        ]

        if include_delta:
            data_paths.append("delta_location")

            if getattr(
                target,
                "rotation_mode",
                'XYZ',
            ) == 'QUATERNION':
                data_paths.append(
                    "delta_rotation_quaternion"
                )
            else:
                data_paths.append(
                    "delta_rotation_euler"
                )

            data_paths.append("delta_scale")

        inserted = 0

        for data_path in data_paths:
            try:
                if frame is not None and options:
                    ok = target.keyframe_insert(
                        data_path,
                        frame=frame,
                        options=options,
                    )
                elif frame is not None:
                    ok = target.keyframe_insert(
                        data_path,
                        frame=frame,
                    )
                else:
                    ok = target.keyframe_insert(data_path)

                if ok:
                    inserted += 1

            except TypeError:
                try:
                    if frame is not None:
                        ok = target.keyframe_insert(
                            data_path,
                            frame=frame,
                        )
                    else:
                        ok = target.keyframe_insert(data_path)

                    if ok:
                        inserted += 1
                except Exception:
                    pass

            except Exception:
                pass

        return inserted

    def execute(self, context):
        # アニメーションエディター上で実行された場合は、
        # 「選択キーフレームのデフォルト化」モードで動作する。
        area_type = getattr(
            getattr(context, "area", None),
            "type",
            "",
        )

        if area_type in self._ANIM_EDITOR_AREA_TYPES:
            result = self._execute_selected_keyframe_reset(context)
            if result != {'PASS_THROUGH'}:
                return result

        # 以下は従来動作（3D View等での現在値リセット、またはアニメーションエディターでキー非選択時のフォールバック）。
        reset_count = 0
        keyed_count = 0
        autokey = self._autokey_enabled(context)

        if context.mode == 'POSE':
            pose_bones = context.selected_pose_bones or []

            for pose_bone in pose_bones:
                self._reset_transform_channels(pose_bone)
                reset_count += 1

                if autokey:
                    if self._insert_reset_keys(
                        context,
                        pose_bone,
                    ):
                        keyed_count += 1

            if reset_count == 0:
                self.report(
                    {'WARNING'},
                    "ボーンが選択されていません。",
                )
                return {'CANCELLED'}

            if autokey:
                self.report(
                    {'INFO'},
                    f"{reset_count} 本のボーンを初期姿勢に戻し、"
                    f"{keyed_count} 本にキーを挿入しました"
                    "（Auto Keying: ON）。",
                )
            else:
                self.report(
                    {'INFO'},
                    f"{reset_count} 本のボーンを初期姿勢に戻しました"
                    "（Auto Keying: OFF → キーは保存されません）。",
                )

        else:
            selected = list(context.selected_objects or [])

            for obj in selected:
                self._reset_transform_channels(
                    obj,
                    include_delta=get_reset_delta_transforms(),
                )
                reset_count += 1

                if autokey:
                    if self._insert_reset_keys(
                        context,
                        obj,
                        include_delta=get_reset_delta_transforms(),
                    ):
                        keyed_count += 1

            if reset_count == 0:
                self.report(
                    {'WARNING'},
                    "オブジェクトが選択されていません。",
                )
                return {'CANCELLED'}

            if autokey:
                self.report(
                    {'INFO'},
                    f"{reset_count} 個のオブジェクトを初期状態に戻し、"
                    f"{keyed_count} 個にキーを挿入しました"
                    "（Auto Keying: ON）。",
                )
            else:
                self.report(
                    {'INFO'},
                    f"{reset_count} 個のオブジェクトを初期状態に戻しました"
                    "（Auto Keying: OFF → キーは保存されません）。",
                )

        try:
            for area in context.window.screen.areas:
                if area.type in {
                    'VIEW_3D',
                    'DOPESHEET_EDITOR',
                    'GRAPH_EDITOR',
                    'NLA_EDITOR',
                }:
                    area.tag_redraw()
        except Exception:
            pass

        return {'FINISHED'}


# ============================================================
# グラフエディター: Shift+中ドラッグ
# 修正: オイラー回転などで数値が暴れる不具合を修正。
#       View上のマウス移動量(Region→View変換)がそのまま内部値(radians)に
#       加算され、Degrees表示(57.3倍ズレ)で制御不能になっていた。
#       各F-Curveのデータパス/単位系に応じたスケールで内部Δへ変換し、
#       マウスカーソル分がそのまま見た目上の移動量になるよう修正。
# ============================================================

class GRAPH_OT_maya_slide_keys(bpy.types.Operator):
    bl_idname = "graph.maya_slide_keys"
    bl_label = "キーを軸ロック移動 (Maya Shift+MMB)"
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    @classmethod
    def poll(cls, context):
        return (
            context.area is not None and
            context.area.type == 'GRAPH_EDITOR' and
            context.region is not None and
            context.region.type == 'WINDOW'
        )

    @staticmethod
    def _collect_editable_fcurves(context):
        try:
            fcurves = list(context.editable_fcurves or [])
        except Exception:
            fcurves = []

        if not fcurves:
            try:
                fcurves = list(context.visible_fcurves or [])
            except Exception:
                fcurves = []

        return [
            fcurve
            for fcurve in fcurves
            if (
                not getattr(fcurve, "lock", False) and
                not getattr(fcurve, "hide", False)
            )
        ]

    @staticmethod
    def _is_angle_fcurve(fcurve):
        """回転の角度としてDegrees表示されるF-Curveか判定。
        rotation_euler は常に角度。rotation_axis_angle は index 0 のみ角度。
        """
        try:
            path = getattr(fcurve, "data_path", "") or ""
            idx = getattr(fcurve, "array_index", 0)
            if path.endswith("rotation_euler"):
                return True
            if path.endswith("rotation_axis_angle") and idx == 0:
                return True
            # pose.bones["..."].rotation_euler のようなパスも末尾で判定できる
            if "rotation_euler" in path:
                return True
            if "rotation_axis_angle" in path and idx == 0:
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _value_scale_for_fcurve(fcurve, context):
        """View Δ(表示単位) → 内部 Δ(ラジアン等) へのスケール。
        Degrees表示時は view=degrees, 内部=radians なので pi/180 を掛ける。
        それ以外は 1.0。
        正規化表示中は表示が0-1に正規化されているため角度変換は行わない。
        """
        try:
            space = getattr(context, "space_data", None)
            if space is not None and getattr(space, "use_normalization", False):
                return 1.0
            scene = getattr(context, "scene", None)
            if scene is not None:
                unit_settings = getattr(scene, "unit_settings", None)
                if unit_settings is not None:
                    rot_unit = getattr(unit_settings, "system_rotation", 'DEGREES')
                    if rot_unit == 'RADIANS':
                        return 1.0
            # シーン取得不可でもデフォルトは Degrees とみなす
            if GRAPH_OT_maya_slide_keys._is_angle_fcurve(fcurve):
                return math.radians(1.0)  # pi/180
        except Exception:
            pass
        return 1.0

    def invoke(self, context, event):
        region = context.region
        self._targets = []
        # (fcurve, originals, value_scale) を保持。value_scale は ViewΔ→内部Δ変換用
        self._use_normalization = False

        try:
            space_tmp = getattr(context, "space_data", None)
            self._use_normalization = bool(getattr(space_tmp, "use_normalization", False))
        except Exception:
            self._use_normalization = False

        for fcurve in self._collect_editable_fcurves(context):
            originals = []

            try:
                for keyframe_point in fcurve.keyframe_points:
                    if keyframe_point.select_control_point:
                        originals.append((
                            (
                                keyframe_point.co.x,
                                keyframe_point.co.y,
                            ),
                            (
                                keyframe_point.handle_left.x,
                                keyframe_point.handle_left.y,
                            ),
                            (
                                keyframe_point.handle_right.x,
                                keyframe_point.handle_right.y,
                            ),
                        ))
            except Exception:
                continue

            if originals:
                scale = self._value_scale_for_fcurve(fcurve, context)
                self._targets.append((fcurve, originals, scale))

        if not self._targets:
            return {'PASS_THROUGH'}

        space = getattr(context, "space_data", None)

        if getattr(space, "use_normalization", False):
            self.report(
                {'WARNING'},
                "正規化表示中のため、値の移動量が表示と一致しない"
                "場合があります。",
            )

        self._axis = None

        self._start_region = (
            event.mouse_region_x,
            event.mouse_region_y,
        )

        try:
            self._start_view = region.view2d.region_to_view(
                self._start_region[0],
                self._start_region[1],
            )
        except Exception:
            return {'PASS_THROUGH'}

        # 追加: ピクセル→Viewのスケールを保持（マウスカーソル追従の検証用）
        # ただし実際の移動はViewΔを基にしつつ、各F-Curveで内部単位へ正しく変換する
        try:
            # View範囲からピクセルあたりのView量を算出（将来のピクセル基準補正に利用可能）
            x0, y0 = region.view2d.region_to_view(0, 0)
            x1, y1 = region.view2d.region_to_view(region.width, region.height)
            self._view_per_pixel_x = (x1 - x0) / max(region.width, 1)
            self._view_per_pixel_y = (y1 - y0) / max(region.height, 1)
        except Exception:
            self._view_per_pixel_x = 0.0
            self._view_per_pixel_y = 0.0

        context.window_manager.modal_handler_add(self)

        self._set_header(context, 0.0, 0.0)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {
            'MOUSEMOVE',
            'INBETWEEN_MOUSEMOVE',
        }:
            self._update(context, event)
            return {'RUNNING_MODAL'}

        if (
            event.type == 'MIDDLEMOUSE' and
            event.value == 'RELEASE'
        ):
            self._finish(context)
            return {'FINISHED'}

        if (
            event.type in {'ESC', 'RIGHTMOUSE'} and
            event.value == 'PRESS'
        ):
            self._apply_delta(context, 0.0, 0.0)
            self._finish(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def _update(self, context, event):
        region = context.region

        if region is None:
            return

        mouse_x = event.mouse_region_x
        mouse_y = event.mouse_region_y

        pixel_dx = mouse_x - self._start_region[0]
        pixel_dy = mouse_y - self._start_region[1]

        if self._axis is None:
            if max(
                abs(pixel_dx),
                abs(pixel_dy),
            ) < get_slide_axis_lock_threshold_px():
                return

            self._axis = (
                'FRAME'
                if abs(pixel_dx) >= abs(pixel_dy)
                else 'VALUE'
            )

        try:
            view = region.view2d.region_to_view(
                mouse_x,
                mouse_y,
            )
        except Exception:
            return

        # マウスカーソル分の View Δ を取得。これが「カーソルが動いた分」そのもの。
        delta_frame_view = view[0] - self._start_view[0]
        delta_value_view = view[1] - self._start_view[1]

        if self._axis == 'FRAME':
            delta_value_view = 0.0

            if get_slide_snap_frames() and not event.ctrl:
                delta_frame_view = float(round(delta_frame_view))
        else:
            delta_frame_view = 0.0

        # 内部値への適用は各F-Curveのスケールで行うため、ここではViewΔを渡す
        self._apply_delta(
            context,
            delta_frame_view,
            delta_value_view,
        )

        self._set_header(
            context,
            delta_frame_view,
            delta_value_view,
        )

    def _apply_delta(self, context, delta_frame_view, delta_value_view):
        # delta_*_view は View(表示)座標系でのマウス移動量。
        # 各F-Curveで内部単位へ変換してから加算することで、
        # 見た目上キーがマウスカーソルに追従し、オイラー回転でも57倍ズレが起きない。
        for item in self._targets:
            if len(item) == 3:
                fcurve, originals, value_scale = item
            else:
                # 旧形式互換
                fcurve, originals = item
                value_scale = self._value_scale_for_fcurve(fcurve, context)

            # フレーム軸は常にView=内部(フレーム)なのでスケール不要
            # 値軸のみF-Curveごとにスケール
            delta_value_internal = delta_value_view * value_scale

            try:
                selected = [
                    keyframe_point
                    for keyframe_point in fcurve.keyframe_points
                    if keyframe_point.select_control_point
                ]
            except Exception:
                continue

            if len(selected) != len(originals):
                continue

            for keyframe_point, (co, hl, hr) in zip(
                selected,
                originals,
            ):
                try:
                    # フレームと値は別々にスケール適用
                    # 内部値 = 元の内部値 + ViewΔ * スケール
                    keyframe_point.co = (
                        co[0] + delta_frame_view,
                        co[1] + delta_value_internal,
                    )

                    keyframe_point.handle_left = (
                        hl[0] + delta_frame_view,
                        hl[1] + delta_value_internal,
                    )

                    keyframe_point.handle_right = (
                        hr[0] + delta_frame_view,
                        hr[1] + delta_value_internal,
                    )
                except Exception:
                    pass

            try:
                fcurve.update()
            except Exception:
                pass

        try:
            context.area.tag_redraw()
        except Exception:
            pass

    def _set_header(self, context, delta_frame_view, delta_value_view):
        try:
            if self._axis == 'FRAME':
                axis_label = "フレーム"
            elif self._axis == 'VALUE':
                axis_label = "値"
            else:
                axis_label = "方向で軸決定"

            # ViewΔを表示。内部がラジアンでも見た目はDegreesなのでViewΔの方が直感的
            # ただし参考として内部Δ(Radians換算)も括弧内に表示
            extra = ""
            if self._axis == 'VALUE' and delta_value_view != 0.0:
                # 代表的なスケールで内部Δを推定表示
                try:
                    # 最初のF-Curveのスケールで代表
                    rep_scale = self._targets[0][2] if len(self._targets[0]) == 3 else 1.0
                    internal = delta_value_view * rep_scale
                    if abs(rep_scale - math.radians(1.0)) < 1e-9:
                        extra = f" / 内部 {internal:+.4f} rad"
                    elif rep_scale != 1.0:
                        extra = f" / 内部 {internal:+.3f}"
                except Exception:
                    pass

            context.area.header_text_set(
                f"キー移動 [{axis_label}]  "
                f"Frame {delta_frame_view:+.1f} / "
                f"Value {delta_value_view:+.3f}{extra}  "
                "(MMB離す: 確定 / ESC: キャンセル / "
                "Ctrl: スナップ解除)"
            )
        except Exception:
            pass

    def _finish(self, context):
        try:
            context.area.header_text_set(None)
        except Exception:
            pass

        try:
            context.area.tag_redraw()
        except Exception:
            pass


# ============================================================
# ビュー切替
# ============================================================

class VIEW3D_OT_maya_set_view(bpy.types.Operator):
    bl_idname = "view3d.maya_set_view"
    bl_label = "ビュー切替 (Maya)"
    bl_options = {'REGISTER'}

    view_type: bpy.props.StringProperty(default='PERSP')

    _ORTHO_ROTATIONS = {
        'FRONT': (0.7071068, 0.7071068, 0.0, 0.0),
        'BACK': (0.0, 0.0, 0.7071068, 0.7071068),
        'RIGHT': (0.5, 0.5, 0.5, 0.5),
        'LEFT': (0.5, 0.5, -0.5, -0.5),
        'TOP': (1.0, 0.0, 0.0, 0.0),
        'BOTTOM': (0.0, 1.0, 0.0, 0.0),
    }

    def execute(self, context):
        view_type = self.view_type
        rv3d = resolve_active_region_view3d(context)

        if view_type == 'PERSP':
            if rv3d is None:
                self.report(
                    {'WARNING'},
                    "3D Viewが見つかりませんでした。",
                )
                return {'CANCELLED'}

            try:
                rv3d.view_perspective = 'PERSP'
            except Exception:
                pass

            self.report({'INFO'}, "ビュー: Perspective")
            return {'FINISHED'}

        if view_type == 'CAMERA_NEW':
            return self._create_camera_from_view(
                context,
                rv3d,
            )

        if view_type in self._ORTHO_ROTATIONS:
            try:
                result = bpy.ops.view3d.view_axis(
                    type=view_type
                )

                if 'FINISHED' in result:
                    self.report(
                        {'INFO'},
                        f"ビュー: {view_type}",
                    )
                    return {'FINISHED'}
            except Exception:
                pass

            if rv3d is not None:
                try:
                    rv3d.view_perspective = 'ORTHO'
                    rv3d.view_rotation = mathutils.Quaternion(
                        self._ORTHO_ROTATIONS[view_type]
                    )

                    self.report(
                        {'INFO'},
                        f"ビュー: {view_type}",
                    )
                    return {'FINISHED'}
                except Exception:
                    pass

            self.report(
                {'WARNING'},
                "ビューを切り替えられませんでした。",
            )
            return {'CANCELLED'}

        return {'CANCELLED'}

    def _create_camera_from_view(self, context, rv3d):
        scene = context.scene

        cam_data = bpy.data.cameras.new("MayaCamera")
        cam_obj = bpy.data.objects.new(
            "MayaCamera",
            cam_data,
        )

        collection = (
            getattr(context, "collection", None) or
            scene.collection
        )

        try:
            collection.objects.link(cam_obj)
        except Exception:
            try:
                scene.collection.objects.link(cam_obj)
            except Exception:
                self.report(
                    {'WARNING'},
                    "カメラをシーンに追加できませんでした。",
                )
                return {'CANCELLED'}

        if rv3d is not None:
            try:
                cam_obj.matrix_world = (
                    rv3d.view_matrix.inverted()
                )
            except Exception:
                pass

        try:
            scene.camera = cam_obj
        except Exception:
            pass

        if rv3d is not None:
            try:
                rv3d.view_perspective = 'CAMERA'
            except Exception:
                pass

        self.report(
            {'INFO'},
            f"新規カメラ '{cam_obj.name}' を作成し、"
            "その視点に入りました。",
        )
        return {'FINISHED'}


class VIEW3D_OT_maya_look_through_camera(
    bpy.types.Operator
):
    bl_idname = "view3d.maya_look_through_camera"
    bl_label = "カメラ視点へ切替 (Maya)"
    bl_options = {'REGISTER', 'UNDO'}

    camera_name: bpy.props.StringProperty(
        name="カメラ名",
        default="",
    )

    def execute(self, context):
        scene = context.scene
        cam_obj = None

        try:
            cam_obj = scene.objects.get(self.camera_name)
        except Exception:
            pass

        if cam_obj is None:
            try:
                cam_obj = bpy.data.objects.get(
                    self.camera_name
                )
            except Exception:
                pass

        if cam_obj is None or cam_obj.type != 'CAMERA':
            self.report(
                {'WARNING'},
                f"カメラ '{self.camera_name}' が見つかりませんでした。",
            )
            return {'CANCELLED'}

        try:
            scene.camera = cam_obj
        except Exception as error:
            self.report(
                {'WARNING'},
                f"シーンカメラを設定できませんでした: {error}",
            )
            return {'CANCELLED'}

        rv3d = resolve_active_region_view3d(context)

        if rv3d is not None:
            try:
                rv3d.view_perspective = 'CAMERA'
            except Exception:
                pass
        else:
            self.report(
                {'WARNING'},
                "3D Viewが見つからないため、"
                "シーンカメラのみ変更しました。",
            )

        tag_all_view3d_redraw()

        self.report(
            {'INFO'},
            f"カメラ '{cam_obj.name}' の視点に切り替えました。",
        )
        return {'FINISHED'}


class VIEW3D_MT_maya_view_menu(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_maya_view_menu"
    bl_label = "ビュー切替"

    def draw(self, context):
        layout = self.layout

        layout.operator(
            "view3d.maya_set_view",
            text="Perspective",
            icon='VIEW_PERSPECTIVE',
        ).view_type = 'PERSP'

        layout.separator()

        layout.operator(
            "view3d.maya_set_view",
            text="Front",
            icon='AXIS_FRONT',
        ).view_type = 'FRONT'

        layout.operator(
            "view3d.maya_set_view",
            text="Back",
        ).view_type = 'BACK'

        layout.operator(
            "view3d.maya_set_view",
            text="Right",
            icon='AXIS_SIDE',
        ).view_type = 'RIGHT'

        layout.operator(
            "view3d.maya_set_view",
            text="Left",
        ).view_type = 'LEFT'

        layout.operator(
            "view3d.maya_set_view",
            text="Top",
            icon='AXIS_TOP',
        ).view_type = 'TOP'

        layout.operator(
            "view3d.maya_set_view",
            text="Bottom",
        ).view_type = 'BOTTOM'

        try:
            cameras = [
                obj
                for obj in context.scene.objects
                if obj.type == 'CAMERA'
            ]
        except Exception:
            cameras = []

        if cameras:
            layout.separator()

            layout.label(
                text="シーンのカメラ:",
                icon='CAMERA_DATA',
            )

            active_camera = getattr(
                context.scene,
                "camera",
                None,
            )

            for cam_obj in sorted(
                cameras,
                key=lambda item: item.name.lower(),
            ):
                is_active = (cam_obj == active_camera)

                operator = layout.operator(
                    "view3d.maya_look_through_camera",
                    text=cam_obj.name,
                    icon=(
                        'VIEW_CAMERA'
                        if is_active
                        else 'OUTLINER_OB_CAMERA'
                    ),
                )
                operator.camera_name = cam_obj.name

        layout.separator()

        layout.operator(
            "view3d.maya_set_view",
            text="New Camera（現在の視点）",
            icon='OUTLINER_OB_CAMERA',
        ).view_type = 'CAMERA_NEW'


# ============================================================
# オブジェクト作成メニュー
# ============================================================

class VIEW3D_MT_maya_spawn_menu(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_maya_spawn_menu"
    bl_label = "オブジェクト作成"

    def draw(self, context):
        layout = self.layout

        layout.operator(
            "mesh.primitive_plane_add",
            text="Plane",
            icon='MESH_PLANE',
        )

        layout.operator(
            "mesh.primitive_cube_add",
            text="Cube",
            icon='MESH_CUBE',
        )

        layout.operator(
            "mesh.primitive_circle_add",
            text="Circle",
            icon='MESH_CIRCLE',
        )

        layout.operator(
            "mesh.primitive_uv_sphere_add",
            text="UV Sphere",
            icon='MESH_UVSPHERE',
        )

        layout.operator(
            "mesh.primitive_ico_sphere_add",
            text="Ico Sphere",
            icon='MESH_ICOSPHERE',
        )

        layout.operator(
            "mesh.primitive_cylinder_add",
            text="Cylinder",
            icon='MESH_CYLINDER',
        )

        layout.operator(
            "mesh.primitive_cone_add",
            text="Cone",
            icon='MESH_CONE',
        )

        layout.operator(
            "mesh.primitive_torus_add",
            text="Torus",
            icon='MESH_TORUS',
        )

        layout.separator()

        layout.operator(
            "object.empty_add",
            text="Empty",
            icon='EMPTY_DATA',
        )

        layout.operator(
            "object.armature_add",
            text="Armature",
            icon='OUTLINER_OB_ARMATURE',
        )

        layout.operator(
            "object.camera_add",
            text="Camera",
            icon='OUTLINER_OB_CAMERA',
        )

        layout.operator(
            "object.light_add",
            text="Light",
            icon='OUTLINER_OB_LIGHT',
        )

        layout.operator(
            "object.text_add",
            text="Text",
            icon='OUTLINER_OB_FONT',
        )


# ============================================================
# コンストレイント
# ============================================================

class OBJECT_OT_maya_add_constraint(bpy.types.Operator):
    bl_idname = "object.maya_add_constraint"
    bl_label = "コンストレイント追加 (Maya)"
    bl_options = {'REGISTER', 'UNDO'}

    constraint_type: bpy.props.StringProperty(
        default='COPY_LOCATION'
    )

    def execute(self, context):
        active = context.active_object

        if active is None:
            self.report(
                {'WARNING'},
                "アクティブオブジェクトがありません。",
            )
            return {'CANCELLED'}

        targets = [
            obj
            for obj in (context.selected_objects or [])
            if obj != active
        ]

        try:
            constraint = active.constraints.new(
                type=self.constraint_type
            )
        except Exception as error:
            self.report(
                {'WARNING'},
                f"コンストレイントを追加できませんでした: {error}",
            )
            return {'CANCELLED'}

        if targets:
            target = targets[-1]

            try:
                constraint.target = target
            except Exception:
                pass

            self.report(
                {'INFO'},
                f"{active.name} に {constraint.name} を追加"
                f"（ターゲット: {target.name}）",
            )
        else:
            self.report(
                {'INFO'},
                f"{active.name} に {constraint.name} を追加"
                "（ターゲット未設定）",
            )

        return {'FINISHED'}


class VIEW3D_MT_maya_constraint_menu(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_maya_constraint_menu"
    bl_label = "コンストレイント"

    def draw(self, context):
        layout = self.layout

        layout.operator(
            "object.maya_add_constraint",
            text="Parent（Child Of）",
            icon='CONSTRAINT',
        ).constraint_type = 'CHILD_OF'

        layout.operator(
            "object.maya_add_constraint",
            text="Point（Copy Location）",
            icon='CON_LOCLIKE',
        ).constraint_type = 'COPY_LOCATION'

        layout.operator(
            "object.maya_add_constraint",
            text="Orient（Copy Rotation）",
            icon='CON_ROTLIKE',
        ).constraint_type = 'COPY_ROTATION'

        layout.operator(
            "object.maya_add_constraint",
            text="Scale（Copy Scale）",
            icon='CON_SIZELIKE',
        ).constraint_type = 'COPY_SCALE'

        layout.operator(
            "object.maya_add_constraint",
            text="Aim（Track To）",
            icon='CON_TRACKTO',
        ).constraint_type = 'TRACK_TO'

        layout.operator(
            "object.maya_add_constraint",
            text="Aim（Damped Track）",
            icon='CON_TRACKTO',
        ).constraint_type = 'DAMPED_TRACK'

        layout.separator()

        layout.operator(
            "object.constraints_clear",
            text="すべてのコンストレイントを削除",
            icon='X',
        )


# ============================================================
# クラス登録
# ============================================================

# 旧バージョンで登録されていて現在は廃止されたクラス名。
LEGACY_CLASS_NAMES = (
    "VIEW3D_OT_maya_set_micro_manipulator_mode",
)

MAYA_SPACE_CLASSES = (
    VIEW3D_OT_maya_set_transform_orientation,
    VIEW3D_OT_maya_toggle_micro_manipulator,
    VIEW3D_OT_maya_set_interaction_mode,
    VIEW3D_OT_maya_call_manipulator_menu,
    VIEW3D_MT_maya_manipulator_menu,
    VIEW3D_GGT_maya_micro_manipulator,

    VIEW3D_OT_maya_set_view,
    VIEW3D_OT_maya_look_through_camera,
    VIEW3D_MT_maya_view_menu,
    VIEW3D_MT_maya_spawn_menu,
    OBJECT_OT_maya_add_constraint,
    VIEW3D_MT_maya_constraint_menu,
    VIEW3D_MT_maya_hotbox_pie,
    VIEW3D_OT_maya_space,
    GRAPH_MT_maya_handle_type_menu,
    GRAPH_OT_maya_d_key,
    VIEW3D_OT_maya_toggle_controllers,
    SCREEN_OT_maya_keyframe_jump,
    SCREEN_OT_maya_keyframe_insert,
    OBJECT_OT_maya_reset_transforms,
    GRAPH_OT_maya_slide_keys,
)


def register_maya_space_classes():
    # 廃止クラスの残骸を先に除去する。
    for class_name in LEGACY_CLASS_NAMES:
        existing = getattr(bpy.types, class_name, None)

        if existing is not None:
            try:
                bpy.utils.unregister_class(existing)
            except Exception:
                pass

    for cls in reversed(MAYA_SPACE_CLASSES):
        existing = getattr(
            bpy.types,
            cls.__name__,
            None,
        )

        if existing is not None:
            try:
                bpy.utils.unregister_class(existing)
            except Exception:
                pass

    for cls in MAYA_SPACE_CLASSES:
        bpy.utils.register_class(cls)


def unregister_maya_space_classes():
    for cls in reversed(MAYA_SPACE_CLASSES):
        existing = getattr(bpy.types, cls.__name__, None)

        if existing is not None:
            try:
                bpy.utils.unregister_class(existing)
            except Exception:
                pass

    for class_name in LEGACY_CLASS_NAMES:
        existing = getattr(bpy.types, class_name, None)

        if existing is not None:
            try:
                bpy.utils.unregister_class(existing)
            except Exception:
                pass


# ============================================================
# キーマップ登録（アドオンキーコンフィグ）
# ============================================================

def _clear_addon_keymaps():
    seen_kms = []
    for km, kmi in _addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
        if km not in seen_kms:
            seen_kms.append(km)

    # 再利用キーマップ上に残骸があれば一掃する
    for km in seen_kms:
        try:
            for kmi in list(km.keymap_items):
                try:
                    km.keymap_items.remove(kmi)
                except Exception:
                    pass
        except Exception:
            pass

    _addon_keymaps.clear()


def _restore_disabled_user_keymap_items():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.user

    if not kc:
        _disabled_user_keymap_item_ids.clear()
        return

    for keymap_name, item_id in list(_disabled_user_keymap_item_ids):
        km = kc.keymaps.get(keymap_name)
        if km is None:
            continue

        for kmi in km.keymap_items:
            if kmi.id == item_id:
                try:
                    kmi.active = True
                except Exception:
                    pass
                break

    _disabled_user_keymap_item_ids.clear()


def _track_disable_kmi(km, kmi):
    if kmi.active:
        kmi.active = False
        _disabled_user_keymap_item_ids.append((km.name, kmi.id))
        return True
    return False


def apply_global_key_policies(keyconfig):
    disabled_count = 0

    for km in keyconfig.keymaps:
        for kmi in km.keymap_items:
            for (
                event_type,
                value,
                shift,
                ctrl,
                alt,
                keep_idnames,
            ) in GLOBAL_KEY_POLICIES:

                if kmi.idname in keep_idnames:
                    continue

                if is_exact_event(
                    kmi,
                    event_type,
                    value=value,
                    shift=shift,
                    ctrl=ctrl,
                    alt=alt,
                ):
                    if _track_disable_kmi(km, kmi):
                        disabled_count += 1
                    break

    print(
        f"🔇 グローバルキーポリシーにより {disabled_count} 件の"
        "競合割り当てを無効化しました。"
    )


def disable_alt_s_keyinsert_conflicts(keyconfig):
    keyframe_insert_prefixes = (
        'anim.keyframe_insert',
    )

    disabled_count = 0

    for km in keyconfig.keymaps:
        for kmi in km.keymap_items:
            if kmi.type != 'S':
                continue

            is_keyframe_insert = any(
                kmi.idname.startswith(prefix)
                for prefix in keyframe_insert_prefixes
            )

            if not is_keyframe_insert:
                continue

            if kmi.any or kmi.alt:
                if _track_disable_kmi(km, kmi):
                    disabled_count += 1

    print(
        f"🔇 Alt+Sで誤発動するキー挿入を {disabled_count} 件"
        "無効化しました。"
    )


def disable_alt_ws_conflicts(keyconfig):
    """Alt+W / Alt+S の競合を全域で無効化し、キーフレームジャンプを優先する。"""
    disabled_count = 0
    keep = {
        'screen.maya_keyframe_jump',
    }

    for km in keyconfig.keymaps:
        for kmi in km.keymap_items:
            if kmi.type not in {'W', 'S'}:
                continue

            if kmi.idname in keep:
                continue

            # Alt+W / Alt+S（any 含む）を潰す
            uses_alt = bool(getattr(kmi, "alt", False) or getattr(kmi, "any", False))
            if not uses_alt:
                continue

            # Shift/Ctrl 付きは別ショートカットとして残す
            if kmi.shift or kmi.ctrl or kmi.oskey:
                # any の場合は修飾の解釈が曖昧なので無効化
                if not getattr(kmi, "any", False):
                    continue

            if kmi.value not in {'PRESS', 'ANY', 'CLICK'}:
                continue

            if _track_disable_kmi(km, kmi):
                disabled_count += 1

    print(
        f"🔇 Alt+W/S の競合を {disabled_count} 件無効化しました。"
    )


def disable_plain_s_conflicts(keyconfig):
    """修飾なし S の競合を無効化し、Maya Set Key を優先する。

    エリアによって Insert Keyframes メニューや別オペレーターが
    立ち上がる問題を防ぐ。
    """
    disabled_count = 0

    for km in keyconfig.keymaps:
        for kmi in km.keymap_items:
            if kmi.type != 'S':
                continue

            # 自分のオペレーターは残す
            if kmi.idname == 'screen.maya_keyframe_insert':
                continue

            # 修飾キー付き（Alt+S 等）はここでは触らない
            if not getattr(kmi, "any", False):
                if kmi.shift or kmi.ctrl or kmi.alt or kmi.oskey:
                    continue

            if kmi.value not in {'PRESS', 'ANY', 'CLICK'}:
                continue

            # メニューを開くもの・標準のエリア依存キー挿入を無効化
            if _track_disable_kmi(km, kmi):
                disabled_count += 1

    print(
        f"🔇 修飾なしSの競合を {disabled_count} 件無効化しました。"
    )


def disable_space_play_bindings(keyconfig):
    disabled_count = 0

    for km in keyconfig.keymaps:
        for kmi in km.keymap_items:
            if kmi.idname != 'screen.animation_play':
                continue

            if not is_exact_event(kmi, 'SPACE', value='PRESS'):
                continue

            if _track_disable_kmi(km, kmi):
                disabled_count += 1

    print(
        f"🔇 スペース=再生の割り当てを {disabled_count} 件"
        "無効化しました。"
    )



def disable_ctrl_shift_rmb_conflicts(keyconfig):
    """Ctrl+Shift+右クリックの競合を無効化し、Manipulator Settings を優先する。"""
    disabled_count = 0
    keep_idnames = {
        'view3d.maya_call_manipulator_menu',
        'wm.call_menu',
    }

    for km in keyconfig.keymaps:
        for kmi in km.keymap_items:
            if not is_exact_event(
                kmi,
                'RIGHTMOUSE',
                value='PRESS',
                shift=True,
                ctrl=True,
            ):
                continue

            # 自分たちのメニュー呼び出しは残す
            if kmi.idname in keep_idnames:
                try:
                    menu_name = getattr(kmi.properties, "name", "")
                except Exception:
                    menu_name = ""

                if (
                    kmi.idname == 'view3d.maya_call_manipulator_menu' or
                    menu_name == VIEW3D_MT_maya_manipulator_menu.bl_idname or
                    menu_name == "VIEW3D_MT_maya_manipulator_menu"
                ):
                    continue

            if _track_disable_kmi(km, kmi):
                disabled_count += 1

    print(
        f"🔇 Ctrl+Shift+RMB の競合を {disabled_count} 件無効化しました。"
    )


def force_q_select_box_no_cycle(keyconfig):
    """Qキーのツール割り当てから cycle を除去し、
    矩形選択（builtin.select_box）に固定する。
    """
    fixed_cycle_count = 0
    fixed_name_count = 0

    tool_set_idnames = {
        'wm.tool_set_by_id',
        'wm.tool_set_by_index',
    }

    for km in keyconfig.keymaps:
        for kmi in km.keymap_items:
            if kmi.type != 'Q':
                continue

            if kmi.idname not in tool_set_idnames:
                continue

            properties = kmi.properties

            try:
                if getattr(properties, "cycle", False):
                    properties.cycle = False
                    fixed_cycle_count += 1
            except Exception:
                pass

            try:
                if (
                    not kmi.any and
                    not kmi.shift and
                    not kmi.ctrl and
                    not kmi.alt and
                    not kmi.oskey
                ):
                    name = getattr(properties, "name", "")

                    if (
                        isinstance(name, str) and
                        name.startswith("builtin.select") and
                        name != "builtin.select_box"
                    ):
                        properties.name = "builtin.select_box"
                        fixed_name_count += 1
            except Exception:
                pass

    print(
        f"🔒 Qキーのツール切替: cycle無効化 {fixed_cycle_count} 件 / "
        f"矩形選択へ固定 {fixed_name_count} 件"
    )


def add_addon_binding(
    km,
    operator,
    event_type,
    value='PRESS',
    *,
    shift=False,
    ctrl=False,
    alt=False,
    oskey=False,
    repeat=None,
    properties=None,
):
    """アドオンキーマップに項目を追加し、解除用に記録する。

    type / value は Blender API の位置引数として渡す。
    （キーワードの type= はバージョンによって無視・失敗することがある）
    """
    shift_i = 1 if shift else 0
    ctrl_i = 1 if ctrl else 0
    alt_i = 1 if alt else 0
    oskey_i = 1 if oskey else 0

    kmi = None
    last_error = None

    # 最優先: 正規の位置引数形式
    try:
        kmi = km.keymap_items.new(
            operator,
            event_type,
            value,
            ctrl=ctrl_i,
            alt=alt_i,
            shift=shift_i,
            oskey=oskey_i,
            head=True,
        )
    except TypeError as error:
        last_error = error

    if kmi is None:
        try:
            kmi = km.keymap_items.new(
                operator,
                event_type,
                value,
                ctrl=ctrl_i,
                alt=alt_i,
                shift=shift_i,
                oskey=oskey_i,
            )
        except TypeError as error:
            last_error = error

    if kmi is None:
        try:
            kmi = km.keymap_items.new(
                operator,
                type=event_type,
                value=value,
                ctrl=ctrl_i,
                alt=alt_i,
                shift=shift_i,
                oskey=oskey_i,
                head=True,
            )
        except TypeError as error:
            last_error = error
            raise RuntimeError(
                f"キーマップ項目を作成できませんでした: "
                f"{operator} {event_type} ({last_error})"
            ) from error

    # 修飾キーを明示再設定（bool/int 差の吸収）
    try:
        kmi.shift = bool(shift)
    except Exception:
        try:
            kmi.shift = shift_i
        except Exception:
            pass

    try:
        kmi.ctrl = bool(ctrl)
    except Exception:
        try:
            kmi.ctrl = ctrl_i
        except Exception:
            pass

    try:
        kmi.alt = bool(alt)
    except Exception:
        try:
            kmi.alt = alt_i
        except Exception:
            pass

    try:
        kmi.oskey = bool(oskey)
    except Exception:
        try:
            kmi.oskey = oskey_i
        except Exception:
            pass

    if repeat is not None:
        try:
            kmi.repeat = repeat
        except Exception:
            pass

    for property_name, property_value in (properties or {}).items():
        try:
            setattr(
                kmi.properties,
                property_name,
                property_value,
            )
        except Exception as error:
            print(
                f"⚠️ {operator}.{property_name} を設定できませんでした: "
                f"{error}"
            )

    _addon_keymaps.append((km, kmi))
    return kmi


def get_addon_keymap(
    keyconfig,
    name,
    space_type='EMPTY',
    region_type='WINDOW',
):
    """アドオン KC 上のキーマップを取得または作成する。
    再適用時に同名キーマップを再利用し、項目の重複蓄積を防ぐ。
    """
    for km in keyconfig.keymaps:
        if (
            km.name == name and
            km.space_type == space_type and
            km.region_type == region_type
        ):
            return km

    return keyconfig.keymaps.new(
        name=name,
        space_type=space_type,
        region_type=region_type,
    )


def activate_industry_compatible_base(restore_user=False):
    filepath = find_industry_compatible_preset()

    if not filepath:
        print(
            "⚠️ Industry Compatibleキーマップが見つかりませんでした。"
        )
        return False

    result = bpy.utils.keyconfig_set(filepath)

    if result is False:
        print(
            "⚠️ Industry Compatibleキーマップを有効化できませんでした。"
        )
        return False

    if restore_user:
        result = bpy.ops.preferences.keymap_restore(all=True)
        if 'FINISHED' not in result:
            print("⚠️ ユーザーキーマップをリセットできませんでした。")
            return False

    return True


def setup_maya_style_zoom_direction(preferences):
    inputs = preferences.inputs
    inputs.view_zoom_method = 'DOLLY'
    inputs.view_zoom_axis = 'HORIZONTAL'
    inputs.invert_mouse_zoom = False


def setup_maya_style_graph_theme(preferences):
    try:
        theme = preferences.themes[0]
    except Exception as error:
        print(f"⚠️ テーマを取得できませんでした: {error}")
        return

    graph_theme = getattr(theme, "graph_editor", None)

    if graph_theme is None:
        print("⚠️ グラフエディターのテーマ設定が見つかりませんでした。")
        return

    try:
        graph_theme.vertex_size = get_graph_key_vertex_size()
    except Exception as error:
        print(f"⚠️ vertex_size を設定できませんでした: {error}")

    try:
        graph_theme.handle_vertex_size = get_graph_handle_vertex_size()
    except Exception:
        pass

    print(
        f"✅ グラフエディターのキーフレーム点サイズを "
        f"{get_graph_key_vertex_size()} に拡大しました。"
    )


def apply_input_preferences():
    preferences = bpy.context.preferences
    prefs = _addon_prefs()

    disable_emulate = True if prefs is None else prefs.disable_mouse_emulate_3_button
    apply_zoom = True if prefs is None else prefs.apply_maya_zoom

    if disable_emulate:
        try:
            preferences.inputs.use_mouse_emulate_3_button = False
        except Exception:
            pass

    if apply_zoom:
        try:
            setup_maya_style_zoom_direction(preferences)
        except Exception as error:
            print(f"⚠️ ズーム設定を適用できませんでした: {error}")

    try:
        setup_maya_style_graph_theme(preferences)
    except Exception as error:
        print(f"⚠️ グラフテーマを適用できませんでした: {error}")


def register_maya_keymaps():
    """アドオンキーマップとユーザー競合の無効化を適用する。"""
    _clear_addon_keymaps()
    # 以前の無効化を一旦戻してから再適用（再適用オペレーター用）
    _restore_disabled_user_keymap_items()

    wm = bpy.context.window_manager
    kc_addon = wm.keyconfigs.addon
    kc_user = wm.keyconfigs.user

    if not kc_addon:
        raise RuntimeError(
            "アドオンキーマップを取得できませんでした。"
        )

    if not kc_user:
        raise RuntimeError(
            "ユーザーキーマップを取得できませんでした。"
        )

    # --------------------------------------------------------
    # ユーザー側の競合を無効化（無効化時に解除）
    # --------------------------------------------------------

    disable_space_play_bindings(kc_user)
    apply_global_key_policies(kc_user)
    disable_alt_s_keyinsert_conflicts(kc_user)
    disable_alt_ws_conflicts(kc_user)
    disable_plain_s_conflicts(kc_user)
    disable_ctrl_shift_rmb_conflicts(kc_user)
    force_q_select_box_no_cycle(kc_user)

    # --------------------------------------------------------
    # アドオンキーマップ
    # --------------------------------------------------------

    km_3d = get_addon_keymap(
        kc_addon,
        "3D View",
        space_type='VIEW_3D',
    )

    km_screen = get_addon_keymap(
        kc_addon,
        "Screen",
    )

    km_window = get_addon_keymap(
        kc_addon,
        "Window",
    )

    km_object = get_addon_keymap(
        kc_addon,
        "Object Mode",
    )

    km_pose = get_addon_keymap(
        kc_addon,
        "Pose",
    )
    # Pose Mode 名は環境により "Pose" / "Pose Mode"
    # Industry Compatible では "Pose" の場合があるため両方登録
    km_pose_mode = get_addon_keymap(
        kc_addon,
        "Pose Mode",
    )

    km_mesh = get_addon_keymap(
        kc_addon,
        "Mesh",
    )

    km_dopesheet = get_addon_keymap(
        kc_addon,
        "Dopesheet",
        space_type='DOPESHEET_EDITOR',
    )

    km_graph = get_addon_keymap(
        kc_addon,
        "Graph Editor",
        space_type='GRAPH_EDITOR',
    )

    km_nla = get_addon_keymap(
        kc_addon,
        "NLA Editor",
        space_type='NLA_EDITOR',
    )

    km_view2d = get_addon_keymap(
        kc_addon,
        "View2D",
    )

    mode_keymaps = (
        km_3d,
        km_object,
        km_pose,
        km_pose_mode,
        km_mesh,
    )

    # --------------------------------------------------------
    # グローバルキー
    # Alt+W/S 等はマウス下エリアに依存せず動くよう、
    # Window / Screen に加え主要エディタ全域へ登録する
    # --------------------------------------------------------

    # 追加の共通エディタ（ビューポート外でも Alt+W/S を拾う）
    km_outliner = get_addon_keymap(
        kc_addon,
        "Outliner",
        space_type='OUTLINER',
    )
    km_properties = get_addon_keymap(
        kc_addon,
        "Property Editor",
        space_type='PROPERTIES',
    )
    km_uv = get_addon_keymap(
        kc_addon,
        "UV Editor",
        space_type='IMAGE_EDITOR',
    )
    km_node = get_addon_keymap(
        kc_addon,
        "Node Editor",
        space_type='NODE_EDITOR',
    )
    km_text = get_addon_keymap(
        kc_addon,
        "Text",
        space_type='TEXT_EDITOR',
    )
    km_console = get_addon_keymap(
        kc_addon,
        "Console",
        space_type='CONSOLE',
    )
    km_info = get_addon_keymap(
        kc_addon,
        "Info",
        space_type='INFO',
    )
    km_file = get_addon_keymap(
        kc_addon,
        "File Browser",
        space_type='FILE_BROWSER',
    )
    km_pref = get_addon_keymap(
        kc_addon,
        "Preferences",
        space_type='PREFERENCES',
    )
    km_clip = get_addon_keymap(
        kc_addon,
        "Clip Editor",
        space_type='CLIP_EDITOR',
    )
    km_seq = get_addon_keymap(
        kc_addon,
        "Sequencer",
        space_type='SEQUENCE_EDITOR',
    )
    km_spreadsheet = get_addon_keymap(
        kc_addon,
        "Spreadsheet",
        space_type='SPREADSHEET',
    )

    # ユーザー KC に存在する全キーマップ名も拾い、取りこぼしを防ぐ
    extra_user_keymaps = []
    try:
        seen_names = set()
        for km_user in kc_user.keymaps:
            key = (km_user.name, km_user.space_type, km_user.region_type)
            if key in seen_names:
                continue
            seen_names.add(key)
            # モーダルマップは触らない
            if getattr(km_user, "is_modal", False):
                continue
            try:
                extra_user_keymaps.append(
                    get_addon_keymap(
                        kc_addon,
                        km_user.name,
                        space_type=km_user.space_type,
                        region_type=km_user.region_type,
                    )
                )
            except Exception:
                pass
    except Exception:
        pass

    add_addon_binding(
        km_window,
        'ed.undo',
        'Z',
    )

    add_addon_binding(
        km_window,
        'screen.animation_play',
        'Q',
        alt=True,
        repeat=False,
    )

    global_anim_defs = (
        (
            'W',
            'screen.maya_keyframe_jump',
            {'next': False},
        ),
        (
            'S',
            'screen.maya_keyframe_jump',
            {'next': True},
        ),
        (
            'A',
            'screen.frame_offset',
            {'delta': -1},
        ),
        (
            'D',
            'screen.frame_offset',
            {'delta': 1},
        ),
    )

    # どこにマウスがあっても拾えるよう広範囲に登録
    global_anim_keymaps = [
        km_window,
        km_screen,
        km_3d,
        km_object,
        km_pose,
        km_pose_mode,
        km_mesh,
        km_dopesheet,
        km_graph,
        km_nla,
        km_outliner,
        km_properties,
        km_uv,
        km_node,
        km_text,
        km_console,
        km_info,
        km_file,
        km_pref,
        km_clip,
        km_seq,
        km_spreadsheet,
        km_view2d,
    ]
    global_anim_keymaps.extend(extra_user_keymaps)

    # 重複除去（同一 km オブジェクト）
    unique_global_anim_keymaps = []
    seen_km = set()
    for km_target in global_anim_keymaps:
        try:
            km_id = km_target.as_pointer()
        except Exception:
            km_id = id(km_target)
        if km_id in seen_km:
            continue
        seen_km.add(km_id)
        unique_global_anim_keymaps.append(km_target)

    for km_target in unique_global_anim_keymaps:
        for key, operator, properties in global_anim_defs:
            add_addon_binding(
                km_target,
                operator,
                key,
                alt=True,
                properties=properties,
            )

        # 修飾なし S = Maya Set Key（キー挿入）
        # ビューポート外でも Insert Keyframes メニューではなく同じ動作にする
        add_addon_binding(
            km_target,
            'screen.maya_keyframe_insert',
            'S',
            repeat=False,
        )

    add_addon_binding(
        km_window,
        'view3d.maya_toggle_controllers',
        'ONE',
        alt=True,
        repeat=False,
    )

    add_addon_binding(
        km_window,
        'object.maya_reset_transforms',
        'NUMPAD_ASTERIX',
        alt=True,
        repeat=False,
    )

    add_addon_binding(
        km_window,
        'object.maya_reset_transforms',
        'EIGHT',
        alt=True,
        shift=True,
        repeat=False,
    )

    # --------------------------------------------------------
    # Q / W / E / R
    # --------------------------------------------------------

    qwer_defs = (
        ('Q', 'builtin.select_box'),
        ('W', 'builtin.move'),
        ('E', 'builtin.rotate'),
        ('R', 'builtin.scale'),
    )

    for km_target in mode_keymaps:
        for key, tool_name in qwer_defs:
            add_addon_binding(
                km_target,
                'wm.tool_set_by_id',
                key,
                properties={
                    'name': tool_name,
                    'cycle': False,
                },
            )

    # --------------------------------------------------------
    # アニメーションエディター W / E / R / F
    # --------------------------------------------------------

    add_addon_binding(
        km_graph,
        'transform.translate',
        'W',
    )

    add_addon_binding(
        km_graph,
        'transform.rotate',
        'E',
    )

    add_addon_binding(
        km_graph,
        'transform.resize',
        'R',
    )

    add_addon_binding(
        km_dopesheet,
        'transform.transform',
        'W',
        properties={
            'mode': 'TIME_TRANSLATE',
        },
    )

    add_addon_binding(
        km_dopesheet,
        'transform.transform',
        'R',
        properties={
            'mode': 'TIME_SCALE',
        },
    )

    add_addon_binding(
        km_nla,
        'transform.transform',
        'W',
        properties={
            'mode': 'TRANSLATION',
        },
    )

    add_addon_binding(
        km_nla,
        'transform.transform',
        'R',
        properties={
            'mode': 'TIME_SCALE',
        },
    )

    add_addon_binding(
        km_graph,
        'graph.view_selected',
        'F',
    )

    add_addon_binding(
        km_dopesheet,
        'action.view_selected',
        'F',
    )

    add_addon_binding(
        km_nla,
        'nla.view_selected',
        'F',
    )

    # --------------------------------------------------------
    # グラフエディター
    # --------------------------------------------------------

    add_addon_binding(
        km_graph,
        'graph.maya_d_key',
        'D',
        repeat=False,
    )

    add_addon_binding(
        km_graph,
        'graph.maya_slide_keys',
        'MIDDLEMOUSE',
        shift=True,
    )

    # --------------------------------------------------------
    # 2Dエディター共通ナビゲーション
    # --------------------------------------------------------

    add_addon_binding(
        km_view2d,
        'view2d.pan',
        'MIDDLEMOUSE',
        alt=True,
    )

    add_addon_binding(
        km_view2d,
        'view2d.zoom',
        'RIGHTMOUSE',
        alt=True,
    )

    # --------------------------------------------------------
    # アニメーション操作（各エディター）
    # --------------------------------------------------------

    anim_defs = (
        (
            'Z',
            'ed.undo',
            {},
            False,
        ),
        (
            'Q',
            'screen.animation_play',
            {},
            True,
        ),
        (
            'A',
            'screen.frame_offset',
            {'delta': -1},
            True,
        ),
        (
            'D',
            'screen.frame_offset',
            {'delta': 1},
            True,
        ),
        (
            'W',
            'screen.maya_keyframe_jump',
            {'next': False},
            True,
        ),
        (
            'S',
            'screen.maya_keyframe_jump',
            {'next': True},
            True,
        ),
    )

    animation_keymaps = (
        km_screen,
        km_3d,
        km_object,
        km_pose,
        km_pose_mode,
        km_mesh,
        km_dopesheet,
        km_graph,
        km_nla,
    )

    for km_target in animation_keymaps:
        for key, operator, properties, use_alt in anim_defs:
            add_addon_binding(
                km_target,
                operator,
                key,
                alt=use_alt,
                properties=properties,
            )

    # アニメーションエディターで Space=再生を維持
    if get_keep_space_play_in_anim_editors():
        for km_target in (km_dopesheet, km_graph, km_nla):
            add_addon_binding(
                km_target,
                'screen.animation_play',
                'SPACE',
                repeat=False,
            )

    # --------------------------------------------------------
    # Maya式ビューポートナビゲーション
    # --------------------------------------------------------

    nav_defs = (
        ('LEFTMOUSE', 'view3d.rotate'),
        ('MIDDLEMOUSE', 'view3d.move'),
        ('RIGHTMOUSE', 'view3d.zoom'),
    )

    for mouse_button, operator in nav_defs:
        add_addon_binding(
            km_3d,
            operator,
            mouse_button,
            alt=True,
        )

    # --------------------------------------------------------
    # Ctrl+Shift+右クリック: Manipulator Settings
    # 専用オペレーターで開き、複数キーマップへ登録して取りこぼしを防ぐ
    # --------------------------------------------------------

    manipulator_menu_keymaps = (
        km_3d,
        km_object,
        km_pose,
        km_pose_mode,
        km_mesh,
        km_window,
        km_screen,
    )

    for km_target in manipulator_menu_keymaps:
        add_addon_binding(
            km_target,
            'view3d.maya_call_manipulator_menu',
            'RIGHTMOUSE',
            ctrl=True,
            shift=True,
            repeat=False,
        )

        # 互換: wm.call_menu でも登録（環境差の保険）
        add_addon_binding(
            km_target,
            'wm.call_menu',
            'RIGHTMOUSE',
            ctrl=True,
            shift=True,
            repeat=False,
            properties={
                'name': VIEW3D_MT_maya_manipulator_menu.bl_idname,
            },
        )

    # --------------------------------------------------------
    # スペースキー
    # --------------------------------------------------------

    add_addon_binding(
        km_3d,
        'view3d.maya_space',
        'SPACE',
        repeat=False,
    )

    # --------------------------------------------------------
    # Alt+1 / Alt+*
    # --------------------------------------------------------

    for km_target in mode_keymaps:
        add_addon_binding(
            km_target,
            'view3d.maya_toggle_controllers',
            'ONE',
            alt=True,
            repeat=False,
        )

    for km_target in (
        km_3d,
        km_object,
        km_pose,
        km_pose_mode,
    ):
        add_addon_binding(
            km_target,
            'object.maya_reset_transforms',
            'NUMPAD_ASTERIX',
            alt=True,
            repeat=False,
        )

        add_addon_binding(
            km_target,
            'object.maya_reset_transforms',
            'EIGHT',
            alt=True,
            shift=True,
            repeat=False,
        )

    for km_target in (
        km_graph,
        km_dopesheet,
    ):
        add_addon_binding(
            km_target,
            'object.maya_reset_transforms',
            'NUMPAD_ASTERIX',
            alt=True,
            repeat=False,
        )

        add_addon_binding(
            km_target,
            'object.maya_reset_transforms',
            'EIGHT',
            alt=True,
            shift=True,
            repeat=False,
        )

    # --------------------------------------------------------
    # F = フォーカス
    # --------------------------------------------------------

    for km_target in (
        km_3d,
        km_object,
        km_pose,
        km_pose_mode,
    ):
        add_addon_binding(
            km_target,
            'view3d.view_selected',
            'F',
            properties={
                'use_all_regions': False,
            },
        )

    # --------------------------------------------------------
    # 4 / 5 / 6 / 7 = シェーディング
    # --------------------------------------------------------

    shading_defs = (
        ('FOUR', 'WIREFRAME'),
        ('FIVE', 'SOLID'),
        ('SIX', 'MATERIAL'),
        ('SEVEN', 'RENDERED'),
    )

    for km_target in mode_keymaps:
        for key, shading_type in shading_defs:
            add_addon_binding(
                km_target,
                'wm.context_set_enum',
                key,
                properties={
                    'data_path': 'space_data.shading.type',
                    'value': shading_type,
                },
            )

    # --------------------------------------------------------
    # 1 / 2 / 3 = Subdivision Preview
    # --------------------------------------------------------

    subdivision_defs = (
        ('ONE', 0),
        ('TWO', 1),
        ('THREE', 2),
    )

    for km_target in (
        km_object,
        km_mesh,
    ):
        for key, level in subdivision_defs:
            add_addon_binding(
                km_target,
                'object.subdivision_set',
                key,
                properties={
                    'level': level,
                    'relative': False,
                    'ensure_modifier': level > 0,
                },
            )

    # --------------------------------------------------------
    # F8 / F9 / F10 / F11
    # --------------------------------------------------------

    add_addon_binding(
        km_3d,
        'object.editmode_toggle',
        'F8',
    )

    component_defs = (
        ('F9', 'VERT'),
        ('F10', 'EDGE'),
        ('F11', 'FACE'),
    )

    for key, select_type in component_defs:
        add_addon_binding(
            km_mesh,
            'mesh.select_mode',
            key,
            properties={
                'type': select_type,
            },
        )

    # --------------------------------------------------------
    # ダブルクリック = エッジループ選択
    # --------------------------------------------------------

    add_addon_binding(
        km_mesh,
        'mesh.loop_select',
        'LEFTMOUSE',
        value='DOUBLE_CLICK',
        properties={
            'extend': False,
            'deselect': False,
            'toggle': False,
        },
    )

    print(
        f"✅ アドオンキーマップを {len(_addon_keymaps)} 件登録しました。"
    )


def unregister_maya_keymaps():
    _clear_addon_keymaps()
    _restore_disabled_user_keymap_items()


# ============================================================
# メンテナンス用オペレーター
# ============================================================

class WM_OT_maya_hotkey_reapply_keymap(bpy.types.Operator):
    bl_idname = "wm.maya_hotkey_reapply_keymap"
    bl_label = "Maya風キーマップを再適用"
    bl_description = (
        "アドオンキーマップと競合無効化をやり直す"
    )
    bl_options = {'REGISTER'}

    def execute(self, context):
        prefs = _addon_prefs(context)

        try:
            restore_maya_micro_space_visibility()
        except Exception:
            pass

        if prefs is not None and prefs.use_industry_compatible_base:
            activate_industry_compatible_base(
                restore_user=bool(prefs.restore_user_keymap_on_base),
            )

        apply_input_preferences()
        setup_graph_editor_handle_display()

        try:
            register_maya_keymaps()
        except Exception as error:
            self.report({'ERROR'}, f"キーマップ再適用に失敗: {error}")
            return {'CANCELLED'}

        self.report({'INFO'}, "Maya風キーマップを再適用しました。")
        return {'FINISHED'}


class WM_OT_maya_hotkey_export_preset(bpy.types.Operator):
    bl_idname = "wm.maya_hotkey_export_preset"
    bl_label = "キーマッププリセットを書き出し"
    bl_description = (
        "現在のユーザーキーマップを presets/keyconfig に保存"
    )
    bl_options = {'REGISTER'}

    def execute(self, context):
        preset_directory = bpy.utils.user_resource(
            'SCRIPTS',
            path="presets/keyconfig",
            create=True,
        )

        if not preset_directory:
            self.report(
                {'ERROR'},
                "プリセット保存先を作成できませんでした。",
            )
            return {'CANCELLED'}

        target_file = os.path.join(
            preset_directory,
            PRESET_FILENAME,
        )

        try:
            result = bpy.ops.preferences.keyconfig_export(
                filepath=target_file,
                all=True,
            )
        except Exception as error:
            self.report({'ERROR'}, f"書き出し失敗: {error}")
            return {'CANCELLED'}

        if 'FINISHED' not in result:
            self.report({'ERROR'}, "キーマッププリセットを書き出せませんでした。")
            return {'CANCELLED'}

        self.report({'INFO'}, f"保存しました: {target_file}")
        return {'FINISHED'}


# ============================================================
# register / unregister
# ============================================================

_classes_extra = (
    MAYA_HOTKEY_AT_preferences,
    WM_OT_maya_hotkey_reapply_keymap,
    WM_OT_maya_hotkey_export_preset,
)


def register():
    # Preferences を先に登録
    for cls in _classes_extra:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            # 再登録時
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass
            bpy.utils.register_class(cls)

    # 旧 Micro 状態の復旧
    try:
        restore_maya_micro_space_visibility()
    except Exception:
        pass

    register_maya_space_classes()
    register_maya_runtime_properties()
    register_graph_display_load_handler()

    prefs = _addon_prefs()

    if prefs is None or prefs.use_industry_compatible_base:
        restore_user = bool(
            prefs.restore_user_keymap_on_base
        ) if prefs is not None else False
        activate_industry_compatible_base(restore_user=restore_user)

    apply_input_preferences()
    setup_graph_editor_handle_display()

    try:
        register_maya_keymaps()
    except Exception as error:
        print(f"⚠️ キーマップ登録に失敗しました: {error}")
        raise

    print("🎉 My Hot Key Inspired by Maya を有効化しました。")
    print("   Preferences > Add-ons から設定・再適用が可能です。")
    print("   再起動後もアドオンが有効なら全機能が自動で復元されます。")


def unregister():
    try:
        restore_maya_micro_space_visibility()
    except Exception:
        pass

    try:
        unregister_maya_keymaps()
    except Exception as error:
        print(f"⚠️ キーマップ解除に失敗: {error}")

    unregister_graph_display_load_handler()
    unregister_maya_runtime_properties()
    unregister_maya_space_classes()

    for cls in reversed(_classes_extra):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    print("👋 My Hot Key Inspired by Maya を無効化しました。")


if __name__ == "__main__":
    register()
