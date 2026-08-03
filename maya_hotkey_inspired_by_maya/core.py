import bpy
import os

from bpy.app.handlers import persistent


# ============================================================
# 設定
# ============================================================

RESET_TO_CLEAN_INDUSTRY_BASE = True
SAVE_AS_PRESET = True
PRESET_FILENAME = "my_hot_key_inspired_by_maya.py"

SPACE_HOLD_TIME = 0.3
KEEP_SPACE_PLAY_IN_ANIM_EDITORS = True

ALT1_ALSO_TOGGLE_EMPTIES = False
RESET_DELTA_TRANSFORMS = True

GRAPH_KEY_VERTEX_SIZE = 6
GRAPH_HANDLE_VERTEX_SIZE = 5

SLIDE_SNAP_FRAMES = True
SLIDE_AXIS_LOCK_THRESHOLD_PX = 5

MICRO_MANIPULATOR_FACTOR = 0.1
MICRO_MANIPULATOR_GIZMO_SCALE = 1.0

MICRO_ORIENTATION_TYPES = {
    'GLOBAL',
    'LOCAL',
    'GIMBAL',
}


# ============================================================
# Industry Compatible
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


def activate_clean_industry_keymap():
    filepath = find_industry_compatible_preset()

    if not filepath:
        raise RuntimeError(
            "Industry Compatibleキーマップが見つかりませんでした。"
        )

    result = bpy.utils.keyconfig_set(filepath)

    if result is False:
        raise RuntimeError(
            "Industry Compatibleキーマップを有効化できませんでした。"
        )

    result = bpy.ops.preferences.keymap_restore(all=True)

    if 'FINISHED' not in result:
        raise RuntimeError(
            "ユーザーキーマップをリセットできませんでした。"
        )


# ============================================================
# キーマップ操作
# ============================================================

def get_keymap(
    keyconfig,
    name,
    space_type='EMPTY',
    region_type='WINDOW',
):
    km = keyconfig.keymaps.get(name)

    if km is None:
        km = keyconfig.keymaps.new(
            name=name,
            space_type=space_type,
            region_type=region_type,
        )

    return km


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


def remove_exact_event(
    km,
    event_type,
    value='PRESS',
    shift=False,
    ctrl=False,
    alt=False,
    oskey=False,
):
    for kmi in list(km.keymap_items):
        if is_exact_event(
            kmi,
            event_type,
            value=value,
            shift=shift,
            ctrl=ctrl,
            alt=alt,
            oskey=oskey,
        ):
            km.keymap_items.remove(kmi)


def add_binding(
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
    remove_exact_event(
        km,
        event_type,
        value=value,
        shift=shift,
        ctrl=ctrl,
        alt=alt,
        oskey=oskey,
    )

    arguments = {
        "type": event_type,
        "value": value,
        "shift": shift,
        "ctrl": ctrl,
        "alt": alt,
        "oskey": oskey,
    }

    try:
        kmi = km.keymap_items.new(
            operator,
            head=True,
            **arguments,
        )
    except TypeError:
        kmi = km.keymap_items.new(
            operator,
            **arguments,
        )

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

    return kmi


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
                    if kmi.active:
                        kmi.active = False
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
                if kmi.active:
                    kmi.active = False
                    disabled_count += 1

    print(
        f"🔇 Alt+Sで誤発動するキー挿入を {disabled_count} 件"
        "無効化しました。"
    )


def force_q_select_box_no_cycle(keyconfig):
    """Qキーのツール割り当てから cycle を除去し、
    矩形選択（builtin.select_box）に固定する。

    Industry Compatible等では Q に cycle=True が付いており、
    連打すると投げ縄・サークル選択へ切り替わってしまうため、
    全キーマップを走査して強制的に固定する。
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

            # 修飾キーなしのQで選択系ツールを呼ぶ割り当ては
            # すべて矩形選択に固定する。
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


# ============================================================
# Space再生
# ============================================================

def disable_space_play_bindings(keyconfig):
    disabled_count = 0

    for km in keyconfig.keymaps:
        for kmi in km.keymap_items:
            if kmi.idname != 'screen.animation_play':
                continue

            if not is_exact_event(
                kmi,
                'SPACE',
                value='PRESS',
            ):
                continue

            if kmi.active:
                kmi.active = False
                disabled_count += 1

    print(
        f"🔇 スペース=再生の割り当てを {disabled_count} 件"
        "無効化しました。"
    )


def restore_space_play_in_anim_editors(keyconfig):
    editor_definitions = (
        ("Dopesheet", 'DOPESHEET_EDITOR'),
        ("Graph Editor", 'GRAPH_EDITOR'),
        ("NLA Editor", 'NLA_EDITOR'),
    )

    for keymap_name, space_type in editor_definitions:
        km = get_keymap(
            keyconfig,
            keymap_name,
            space_type=space_type,
        )

        add_binding(
            km,
            'screen.animation_play',
            'SPACE',
            repeat=False,
        )


# ============================================================
# 入力・テーマ
# ============================================================

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
        graph_theme.vertex_size = GRAPH_KEY_VERTEX_SIZE
    except Exception as error:
        print(f"⚠️ vertex_size を設定できませんでした: {error}")

    try:
        graph_theme.handle_vertex_size = GRAPH_HANDLE_VERTEX_SIZE
    except Exception:
        pass

    print(
        f"✅ グラフエディターのキーフレーム点サイズを "
        f"{GRAPH_KEY_VERTEX_SIZE} に拡大しました。"
    )


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
        "ハンドルを常時操作できる表示にしました。"
    )


@persistent
def _maya_graph_display_load_post(_dummy):
    setup_graph_editor_handle_display()


def register_graph_display_load_handler():
    handlers = bpy.app.handlers.load_post

    for handler in list(handlers):
        if getattr(
            handler,
            "__name__",
            "",
        ) == "_maya_graph_display_load_post":
            try:
                handlers.remove(handler)
            except Exception:
                pass

    handlers.append(_maya_graph_display_load_post)


def unregister_graph_display_load_handler():
    handlers = bpy.app.handlers.load_post

    for handler in list(handlers):
        if (
            handler is _maya_graph_display_load_post or
            getattr(
                handler,
                "__name__",
                "",
            ) == "_maya_graph_display_load_post"
        ):
            try:
                handlers.remove(handler)
            except Exception:
                pass


# ============================================================
# 3D View共通処理
# ============================================================

def safe_setattr(target, name, value):
    try:
        setattr(target, name, value)
        return True
    except Exception:
        return False


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


def resolve_region_data_for_region(
    context,
    area,
    region,
    space,
):
    if area is None or region is None or space is None:
        return None

    try:
        region_data = getattr(region, "data", None)

        if _is_region_view3d(region_data):
            return region_data
    except Exception:
        pass

    try:
        if (
            context.area == area and
            context.region == region
        ):
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


def find_view3d_area_region_under_mouse(
    context,
    mouse_x,
    mouse_y,
):
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

    if (
        screen is not None and
        mouse_x is not None and
        mouse_y is not None
    ):
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
            if (
                context.area is not None and
                context.area.type == 'VIEW_3D'
            ):
                area = context.area
        except Exception:
            pass

    if area is None:
        return None, None, None, None

    try:
        space = area.spaces.active
    except Exception:
        space = None

    if (
        space is None or
        getattr(space, "type", None) != 'VIEW_3D'
    ):
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

    if (
        space is not None and
        getattr(space, "type", None) == 'VIEW_3D'
    ):
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

    attributes = (
        "view_location",
        "view_rotation",
        "view_distance",
        "view_camera_offset",
        "view_camera_zoom",
        "view_perspective",
    )

    for attribute in attributes:
        try:
            value = getattr(src, attribute)

            try:
                value = value.copy()
            except Exception:
                pass

            setattr(dst, attribute, value)
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
        kwargs_no_region_data.pop(
            "region_data",
            None,
        )
        override_variants.append(
            kwargs_no_region_data
        )

        kwargs_no_space_region_data = dict(
            kwargs_no_region_data
        )
        kwargs_no_space_region_data.pop(
            "space_data",
            None,
        )
        override_variants.append(
            kwargs_no_space_region_data
        )

        last_error = None

        for override_kwargs in override_variants:
            try:
                with context.temp_override(**override_kwargs):
                    return bpy.ops.screen.region_quadview()
            except Exception as error:
                last_error = error

        print(
            "⚠️ マウス下Region指定でregion_quadviewを"
            "実行できませんでした。"
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
        kwargs_no_region_data.pop(
            "region_data",
            None,
        )
        override_variants.append(
            kwargs_no_region_data
        )

        kwargs_no_space_region_data = dict(
            kwargs_no_region_data
        )
        kwargs_no_space_region_data.pop(
            "space_data",
            None,
        )
        override_variants.append(
            kwargs_no_space_region_data
        )

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
                if getattr(
                    space,
                    "type",
                    None,
                ) == 'VIEW_3D':
                    yield space
