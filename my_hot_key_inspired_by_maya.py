import bpy
import os
import time
import math
import mathutils


# ============================================================
# 設定
# ============================================================

# 初回実行時は必ず True。
# 以前のスクリプトで無効化されたキーマップをクリーンに復旧する。
#
# 注意:
# 既存のユーザー独自キーマップ変更もリセットされる。
RESET_TO_CLEAN_INDUSTRY_BASE = True

# 実行後にキーマッププリセットとして保存する（バックアップ用途）
SAVE_AS_PRESET = True

# プリセットの実ファイル名
PRESET_FILENAME = "my_hot_key_inspired_by_maya.py"

# スペース長押し判定の秒数（Mayaの体感に近い値）
SPACE_HOLD_TIME = 0.3

# アニメーションエディター（ドープシート/グラフ/NLA）では
# スペース=再生を残す
KEEP_SPACE_PLAY_IN_ANIM_EDITORS = True

# Alt+1 のコントローラー表示切替で、
# ボーンに加えてエンプティも一緒に切り替えるか。
ALT1_ALSO_TOGGLE_EMPTIES = False

# Alt+* でオブジェクトのデルタトランスフォーム
# （Delta Location等）も初期化するか。
RESET_DELTA_TRANSFORMS = True

# ------------------------------------------------------------
# グラフエディタ（Maya風表示・編集）の設定
# ------------------------------------------------------------

# キーフレーム点の描画サイズ（Blenderデフォルトは3。Maya風に大きく）
GRAPH_KEY_VERTEX_SIZE = 6

# ハンドル端点の描画サイズ
GRAPH_HANDLE_VERTEX_SIZE = 5

# Shift+中ドラッグでフレーム方向に動かすとき、
# 整数フレームへスナップするか（Ctrlを押しながらで一時解除）。
SLIDE_SNAP_FRAMES = True

# Shift+中ドラッグの軸ロック判定に使うピクセル数。
# この距離を動いた時点で「フレーム軸」か「値軸」かが確定する。
SLIDE_AXIS_LOCK_THRESHOLD_PX = 5


# ============================================================
# Industry Compatible を読み込む
# ============================================================

def find_industry_compatible_preset():
    """Industry Compatibleキーマッププリセットのパスを探す。"""

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

    # 念のため手動でも探索
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
    """
    Industry Compatibleを有効化し、
    以前のスクリプトによる壊れたユーザー変更をリセットする。
    """

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
# キーマップ操作用ヘルパー
# ============================================================

def get_keymap(
    keyconfig,
    name,
    space_type='EMPTY',
    region_type='WINDOW',
):
    """既存キーマップを取得し、なければ作る。"""

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
    """
    修飾キーまで完全一致するイベントか判定する。

    重要:
    any=Trueの項目には触れない。
    以前のスクリプトはこれを無効化してしまったため、
    通常のクリックやドラッグまで壊していた。
    """

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

    # 新しいBlenderに存在するHyper修飾キーへの対応
    if getattr(kmi, "hyper", False):
        return False

    # 通常キーを別の修飾キーとして使用している項目は対象外
    if getattr(kmi, "key_modifier", 'NONE') != 'NONE':
        return False

    # 方向付きドラッグは対象外
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
    """
    指定したキーマップ内だけで、
    完全一致するイベントを削除する。
    """

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
    """
    完全一致する既存イベントだけを置き換えて登録する。

    default/addon/全エディターを横断して
    active=Falseにする処理は一切行わない。
    """

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
        # 古いBlender向け
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
# （どのエディターにカーソルがあっても同じ動作を保証する）
# ============================================================

# 仕組み:
#   1) ここに載せたキーについて、全キーマップ（3D View /
#      Graph Editor / Dopesheet / Outliner / Properties ...）を
#      走査し、競合する完全一致の割り当てを active=False にする。
#      （エディター固有キーマップはグローバルより優先されるため、
#        これをやらないとカーソル位置によって別の機能が発動する）
#   2) その後、全エディター共通の「Window」キーマップに
#      目的のオペレーターを登録し直す。
#
# 削除ではなく無効化なので、
# Preferences > Keymap の Restore からいつでも復元できる。
#
# 形式: (キー, value, shift, ctrl, alt, 残すオペレーターのセット)
GLOBAL_KEY_POLICIES = (
    # Z = Undo（グラフエディタ等の別機能をすべて無効化）
    ('Z', 'PRESS', False, False, False,
     {'ed.undo'}),

    # Alt+Q = 再生 / 停止
    ('Q', 'PRESS', False, False, True,
     {'screen.animation_play'}),

    # Alt+A / Alt+D = 1フレーム移動
    ('A', 'PRESS', False, False, True,
     {'screen.frame_offset'}),
    ('D', 'PRESS', False, False, True,
     {'screen.frame_offset'}),

    # Alt+W / Alt+S = キーフレームジャンプ
    ('W', 'PRESS', False, False, True,
     {'screen.maya_keyframe_jump'}),
    ('S', 'PRESS', False, False, True,
     {'screen.maya_keyframe_jump'}),

    # Alt+1 = コントローラー表示切替
    ('ONE', 'PRESS', False, False, True,
     {'view3d.maya_toggle_controllers'}),

    # Alt+* = トランスフォーム初期化
    ('NUMPAD_ASTERIX', 'PRESS', False, False, True,
     {'object.maya_reset_transforms'}),
    ('EIGHT', 'PRESS', True, False, True,
     {'object.maya_reset_transforms'}),
)


def apply_global_key_policies(keyconfig):
    """
    GLOBAL_KEY_POLICIESに基づき、
    競合する割り当てを全キーマップで無効化する。
    """

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
    """
    Alt+S で「キーフレーム挿入」が誤発動する問題への対策。

    any=True または alt=True で S キーに反応する
    キーフレーム挿入系の項目をピンポイントで無効化する。
    修飾キーなしの素の S = キー挿入はそのまま残る。
    """

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

            # any=True はすべての修飾キーの組み合わせに反応するため、
            # Alt+Sも拾ってしまう。alt=True指定のものも同様。
            if kmi.any or kmi.alt:
                if kmi.active:
                    kmi.active = False
                    disabled_count += 1

    print(
        f"🔇 Alt+Sで誤発動するキー挿入を {disabled_count} 件"
        "無効化しました。"
    )


def disable_graph_lmb_press_select(km_graph):
    """
    グラフエディタの左クリック PRESS 選択のうち、
    こちらで登録し直すもの以外の重複を無効化する。

    PRESS選択とCLICK_DRAGボックス選択は共存できるため、
    「クリック=選択 / ドラッグ=ボックス選択」の両立が可能。
    ここでは古い重複項目だけを整理する。
    """

    disabled_count = 0

    for kmi in km_graph.keymap_items:
        if kmi.idname != 'graph.clickselect':
            continue

        if kmi.type != 'LEFTMOUSE':
            continue

        # any=True の項目はShiftクリック等も奪ってしまうため無効化
        if kmi.any and kmi.active:
            kmi.active = False
            disabled_count += 1

    if disabled_count:
        print(
            f"🔇 グラフエディタの重複クリック選択を {disabled_count} 件"
            "無効化しました。"
        )


# ============================================================
# スペース=再生の無効化
# ============================================================

def disable_space_play_bindings(keyconfig):
    """
    修飾キーなしの「スペース = screen.animation_play」を
    すべてのキーマップで無効化する。

    削除ではなく active=False にするだけなので、
    Preferences > Keymap の Restore からいつでも復元できる。
    Shift+Space（逆再生）など修飾キー付きの項目には触れない。
    """

    disabled_count = 0

    for km in keyconfig.keymaps:
        for kmi in km.keymap_items:
            if kmi.idname != 'screen.animation_play':
                continue

            if not is_exact_event(kmi, 'SPACE', value='PRESS'):
                continue

            if kmi.active:
                kmi.active = False
                disabled_count += 1

    print(
        f"🔇 スペース=再生の割り当てを {disabled_count} 件"
        "無効化しました。"
    )


def restore_space_play_in_anim_editors(keyconfig):
    """
    アニメーションエディターにだけ
    スペース=再生を個別に登録し直す。

    エディター固有キーマップはグローバルより優先されるため、
    ここに登録すれば確実に効く。
    """

    anim_editor_defs = (
        # タイムラインはドープシートの一種なので
        # "Dopesheet" キーマップでカバーされる。
        ("Dopesheet", 'DOPESHEET_EDITOR'),
        ("Graph Editor", 'GRAPH_EDITOR'),
        ("NLA Editor", 'NLA_EDITOR'),
    )

    for keymap_name, space_type in anim_editor_defs:
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
# Maya式ズーム方向の設定
# ============================================================

def setup_maya_style_zoom_direction(preferences):
    """
    Alt+右ドラッグのズーム方向をMayaと同じにする。

    Mayaのドリー:
        右（右下）にドラッグ = 拡大
        左（左上）にドラッグ = 縮小
    """

    inputs = preferences.inputs

    inputs.view_zoom_method = 'DOLLY'
    inputs.view_zoom_axis = 'HORIZONTAL'
    inputs.invert_mouse_zoom = False


# ============================================================
# グラフエディタの表示をMaya風にする
# ============================================================

def setup_maya_style_graph_theme(preferences):
    """
    キーフレーム点を大きく描画するようテーマを変更する。

    Mayaのグラフエディタのように、
    点が視認しやすく・クリックしやすくなる。
    """

    try:
        theme = preferences.themes[0]
    except Exception as error:
        print(f"⚠️ テーマを取得できませんでした: {error}")
        return

    graph_theme = getattr(theme, "graph_editor", None)

    if graph_theme is None:
        print("⚠️ グラフエディタのテーマ設定が見つかりませんでした。")
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
        f"✅ グラフエディタのキーフレーム点サイズを "
        f"{GRAPH_KEY_VERTEX_SIZE} に拡大しました。"
    )


def setup_graph_editor_handle_display():
    """
    「選択したキーフレームのハンドルだけを表示」を
    すべてのグラフエディタで有効化する。

    これにより、キーを実際にクリックして選択するまで
    ハンドルは表示されない（Mayaと同じ挙動）。

    注意:
    この設定はエディター（スペース）単位で保存されるため、
    スタートアップファイルを保存しておくと
    新規ファイルにも引き継がれる。
    """

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
                    space.use_only_selected_keyframe_handles = True
                    configured_count += 1
                except Exception:
                    pass

                # ハンドル表示自体はON
                # （選択したキーにだけハンドルが出る）
                try:
                    space.show_handles = True
                except Exception:
                    pass

    print(
        f"✅ {configured_count} 個のグラフエディタで"
        "「選択キーのみハンドル表示」を有効化しました。"
    )


def _maya_graph_display_load_post(_dummy):
    """ファイルを開くたびにグラフエディタ表示設定を適用する。"""

    setup_graph_editor_handle_display()


# persistent装飾（再実行に強いようにtryで包む）
try:
    _maya_graph_display_load_post = bpy.app.handlers.persistent(
        _maya_graph_display_load_post
    )
except Exception:
    pass


def register_graph_display_load_handler():
    """
    load_postハンドラーを重複なく登録する。

    別の.blendを開いた後も
    「選択キーのみハンドル表示」が維持される。
    """

    handlers = bpy.app.handlers.load_post

    for handler in list(handlers):
        if getattr(handler, "__name__", "") == "_maya_graph_display_load_post":
            try:
                handlers.remove(handler)
            except Exception:
                pass

    handlers.append(_maya_graph_display_load_post)


# ============================================================
# Maya式 Quad View 切り替え用ヘルパー
# ============================================================

def _point_in_rect(x, y, rx, ry, rw, rh):
    """ウィンドウ座標 x/y が指定矩形内にあるか。"""

    return (
        rx <= x < rx + rw and
        ry <= y < ry + rh
    )


def _region_center_distance_sq(region, x, y):
    """マウス座標からRegion中心までの距離の2乗。"""

    cx = region.x + region.width * 0.5
    cy = region.y + region.height * 0.5
    dx = cx - x
    dy = cy - y
    return dx * dx + dy * dy


def _is_region_view3d(value):
    """値が RegionView3D かどうかを安全に判定する。"""

    try:
        return isinstance(value, bpy.types.RegionView3D)
    except Exception:
        return False


def is_view3d_quadview(space):
    """SpaceView3DがQuad View状態かどうか。"""

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
    """context.temp_override用のキーワードを作る。"""

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
    """
    指定した3D ViewのWINDOW Regionに対応するRegionView3Dを取得する。
    """

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
            {k: v for k, v in kwargs.items() if k != "space_data"},
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
    """
    マウス座標から、3D Viewの Area / WINDOW Region / SpaceView3D /
    RegionView3D を探す。
    """

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
        region for region in area.regions
        if region.type == 'WINDOW' and region.width > 0 and region.height > 0
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

    if region is None and window_regions and mouse_x is not None and mouse_y is not None:
        region = min(
            window_regions,
            key=lambda r: _region_center_distance_sq(r, mouse_x, mouse_y),
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
            key=lambda r: r.width * r.height,
        )

    region_data = resolve_region_data_for_region(
        context,
        area,
        region,
        space,
    )

    return area, region, space, region_data


def find_any_view3d_space(context):
    """
    画面内で最大の3D ViewのSpaceView3Dを返す。

    Alt+1などをアウトライナー等の上で押した場合の
    フォールバックとして使う。
    """

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

        if size > best_size:
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
    """
    現在のcontextから操作対象のRegionView3Dを取得する共通ヘルパー。

    Hotboxのメニュー項目から呼ばれた場合でも、
    フォールバックで画面内最大の3D Viewを対象にする。
    """

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

    # フォールバック: 画面内で最大の3D View
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
    """RegionView3Dの視点状態をコピーする。"""

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
    """
    指定した3D View Regionを対象に screen.region_quadview を実行する。
    """

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
    """指定した3D View Region上でパイメニューを呼ぶ。"""

    kwargs = _make_context_override_kwargs(
        context,
        area=area,
        region=region,
        space=space,
        region_data=region_data,
    )

    if hasattr(context, "temp_override") and area is not None and region is not None:
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


# ============================================================
# Mayaスペースキー再現
# （単押し = 1画面/4分割トグル、長押し = Hotbox風パイメニュー）
# ============================================================

class VIEW3D_MT_maya_hotbox_pie(bpy.types.Menu):
    """Maya Hotboxの代用パイメニュー。"""

    bl_idname = "VIEW3D_MT_maya_hotbox_pie"
    bl_label = "Hotbox (Maya風)"

    def draw(self, context):
        pie = self.layout.menu_pie()
        is_pose = (context.mode == 'POSE')

        # --- 西（左）: キー挿入 ---
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

        # --- 東（右）: キー削除 ---
        pie.operator(
            "anim.keyframe_delete_v3d",
            text="キー削除",
            icon='KEY_DEHLT',
        )

        # --- 南（下）: すべてのツール一覧 ---
        pie.operator(
            "wm.toolbar",
            text="すべてのツール",
            icon='TOOL_SETTINGS',
        )

        # --- 北（上）: 再生/停止 ---
        pie.operator(
            "screen.animation_play",
            text="再生 / 停止",
            icon='PLAY',
        )

        # --- 北西: オブジェクト作成（Maya風スポーン） ---
        pie.menu(
            "VIEW3D_MT_maya_spawn_menu",
            text="オブジェクト作成",
            icon='ADD',
        )

        # --- 北東: コンストレイント ---
        pie.menu(
            "VIEW3D_MT_maya_constraint_menu",
            text="コンストレイント",
            icon='CONSTRAINT',
        )

        # --- 南西: ポーズリセット or Object/Pose切替 ---
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

        # --- 南東: 選択対象へフォーカス ---
        pie.operator(
            "view3d.view_selected",
            text="選択にフォーカス",
            icon='ZOOM_SELECTED',
        )

        # --- 中央（マウスカーソル直下の枠）: ビュー切替 ---
        # 9個目以降の要素はパイの中央に配置される。
        # 上側にダミーの隙間を作ってボックスをカーソル付近へ寄せる。
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
    """
    Mayaのスペースキーを再現するモーダルオペレーター。

    単押し: マウス下のビューポートを 1画面 / 4分割 でトグル。
    長押し: Hotbox風パイメニューを表示。
    """

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

        area, region, space, region_data = find_view3d_area_region_under_mouse(
            context,
            self._mouse_x,
            self._mouse_y,
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
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

    def _update_mouse_from_event(self, event):
        if event.type == 'TIMER':
            return

        try:
            mouse_x = event.mouse_x
            mouse_y = event.mouse_y

            self._mouse_x = mouse_x
            self._mouse_y = mouse_y
        except Exception:
            pass

    def modal(self, context, event):
        self._update_mouse_from_event(event)

        if event.type == 'SPACE' and event.value == 'RELEASE':
            self._remove_timer(context)

            elapsed = time.monotonic() - self._start_time

            if elapsed >= SPACE_HOLD_TIME:
                self._open_hotbox(context)
            else:
                self._toggle_quad_view(context)

            return {'FINISHED'}

        if event.type == 'SPACE' and event.value == 'PRESS':
            return {'RUNNING_MODAL'}

        if event.type == 'TIMER':
            elapsed = time.monotonic() - self._start_time

            if elapsed >= SPACE_HOLD_TIME:
                self._remove_timer(context)
                self._open_hotbox(context)
                return {'FINISHED'}

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self._remove_timer(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def _open_hotbox(self, context):
        area, region, space, region_data = find_view3d_area_region_under_mouse(
            context,
            self._mouse_x,
            self._mouse_y,
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
        area, region, space, region_data = find_view3d_area_region_under_mouse(
            context,
            self._mouse_x,
            self._mouse_y,
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
                    main_region_data = None

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
# Alt+1 = コントローラー表示切替（Maya風）
# ============================================================

class VIEW3D_OT_maya_toggle_controllers(bpy.types.Operator):
    """
    ビューポートのボーン（＝リグコントローラー）表示をトグルする。

    ポイント:
    - ビューポート単位で切り替わる（Mayaのパネル単位と同じ感覚）。
    - オブジェクト自体を隠すわけではないので、
      再生中でもアニメーションはそのまま動き続ける。
    - マウス下のビューポートを優先。3D View以外の上で押した場合は
      画面内で最大の3D Viewに対して効く（グローバル対応）。
    """

    bl_idname = "view3d.maya_toggle_controllers"
    bl_label = "コントローラー表示切替 (Maya Alt+1)"
    bl_options = {'REGISTER'}

    def _find_space(self, context, event=None):
        """対象のSpaceView3Dを探す。マウス下を優先する。"""

        space = None

        if event is not None:
            mouse_x = getattr(event, "mouse_x", None)
            mouse_y = getattr(event, "mouse_y", None)

            _area, _region, space, _region_data = (
                find_view3d_area_region_under_mouse(
                    context,
                    mouse_x,
                    mouse_y,
                )
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

        # グローバル対応:
        # アウトライナー等の上で押された場合は、
        # 画面内で最大の3D Viewにフォールバックする。
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

        if ALT1_ALSO_TOGGLE_EMPTIES:
            try:
                space.show_object_viewport_empty = show
            except Exception:
                pass

        try:
            for area in context.window.screen.areas:
                if area.type == 'VIEW_3D' and area.spaces.active == space:
                    area.tag_redraw()
        except Exception:
            pass

        if show:
            self.report({'INFO'}, "コントローラー: 表示")
        else:
            self.report({'INFO'}, "コントローラー: 非表示")

        return {'FINISHED'}

    def invoke(self, context, event):
        space = self._find_space(context, event)
        return self._toggle(context, space)

    def execute(self, context):
        space = self._find_space(context)
        return self._toggle(context, space)


# ============================================================
# Alt+W / Alt+S = キーフレームジャンプ（どこでも有効）
# ============================================================

class SCREEN_OT_maya_keyframe_jump(bpy.types.Operator):
    """
    選択オブジェクトのキーフレーム間をジャンプする。

    選択中オブジェクトのアクションから直接キーフレームを
    収集するため、カーソルがどのエディター上にあっても動作する。
    """

    bl_idname = "screen.maya_keyframe_jump"
    bl_label = "キーフレームジャンプ (Maya Alt+W/S)"
    bl_options = {'REGISTER'}

    next: bpy.props.BoolProperty(
        name="次のキーフレームへ",
        default=True,
    )

    @staticmethod
    def _collect_from_id(id_data, frames):
        """1つのIDデータブロックからキーフレーム時刻を収集する。"""

        anim = getattr(id_data, "animation_data", None)

        if anim is None:
            return

        action = anim.action

        if action is None:
            return

        try:
            for fcurve in action.fcurves:
                for keyframe_point in fcurve.keyframe_points:
                    frames.add(keyframe_point.co.x)
        except Exception:
            pass

    def _collect_keyframes(self, context):
        """選択オブジェクト群からすべてのキーフレーム時刻を集める。"""

        frames = set()

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
            self._collect_from_id(obj, frames)

            data = getattr(obj, "data", None)

            if data is not None:
                self._collect_from_id(data, frames)

                shape_keys = getattr(data, "shape_keys", None)

                if shape_keys is not None:
                    self._collect_from_id(shape_keys, frames)

        return frames

    def execute(self, context):
        scene = context.scene

        frames = self._collect_keyframes(context)

        if not frames:
            try:
                return bpy.ops.screen.keyframe_jump(next=self.next)
            except Exception:
                self.report(
                    {'INFO'},
                    "選択オブジェクトにキーフレームがありません。",
                )
                return {'CANCELLED'}

        try:
            current = scene.frame_current_final
        except Exception:
            current = float(scene.frame_current)

        epsilon = 1e-4

        if self.next:
            candidates = [f for f in frames if f > current + epsilon]
            target = min(candidates) if candidates else None
        else:
            candidates = [f for f in frames if f < current - epsilon]
            target = max(candidates) if candidates else None

        if target is None:
            self.report(
                {'INFO'},
                "これ以上キーフレームがありません。",
            )
            return {'CANCELLED'}

        frame = int(math.floor(target))
        subframe = target - frame

        try:
            scene.frame_set(frame, subframe=subframe)
        except TypeError:
            scene.frame_set(frame)

        return {'FINISHED'}


# ============================================================
# Alt+* = トランスフォームを初期化（Maya風 / Auto Keying連動）
# ============================================================

class OBJECT_OT_maya_reset_transforms(bpy.types.Operator):
    """
    選択対象の移動 / 回転 / スケールをデフォルト値に戻す。

    「すべて0にする」のではなく初期状態へ戻す:
        移動:     (0, 0, 0)
        回転:     単位回転（角度0）
        スケール: (1, 1, 1)  ← 0ではなく1

    Object Mode: 選択オブジェクトすべてが対象。
                 （設定によりデルタトランスフォームも初期化）
    Pose Mode:   選択ポーズボーンすべてが対象
                 （レストポーズに戻る）。

    Auto Keying（自動キー挿入）との連動:
        タイムラインの Auto Keying が ON のとき:
            リセット後、現在フレームに自動でキーフレームを挿入する。
            → リセットした値が保存される。
        OFF のとき:
            キーは挿入しない。
            → 既存のアニメーションがある場合、フレームを移動した
              時点でリセット結果は破棄される（Mayaと同じ挙動）。

    プロパティへ直接代入する方式のため、
    コンテキストに依存せず、どのエディター上からでも確実に動く。
    Undo（Z）で元に戻せる。
    """

    bl_idname = "object.maya_reset_transforms"
    bl_label = "トランスフォームを初期化 (Maya Alt+*)"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def _reset_transform_channels(target, include_delta=False):
        """
        オブジェクト / ポーズボーン共通の
        トランスフォーム初期化処理。
        """

        try:
            target.location = (0.0, 0.0, 0.0)
        except Exception:
            pass

        # 回転はモードごとにプロパティが違うため、
        # すべてデフォルト値に戻しておく。
        try:
            target.rotation_euler = (0.0, 0.0, 0.0)
        except Exception:
            pass

        try:
            target.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        except Exception:
            pass

        try:
            # (角度, X, Y, Z) デフォルトは角度0 / Y軸
            target.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
        except Exception:
            pass

        try:
            target.scale = (1.0, 1.0, 1.0)
        except Exception:
            pass

        # オブジェクトのデルタトランスフォームも初期化する。
        # （ポーズボーンには存在しないためtry/exceptで安全に処理）
        if include_delta:
            try:
                target.delta_location = (0.0, 0.0, 0.0)
            except Exception:
                pass

            try:
                target.delta_rotation_euler = (0.0, 0.0, 0.0)
            except Exception:
                pass

            try:
                target.delta_rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            except Exception:
                pass

            try:
                target.delta_scale = (1.0, 1.0, 1.0)
            except Exception:
                pass

    @staticmethod
    def _autokey_enabled(context):
        """Auto Keying（自動キー挿入）がONかどうか。"""

        try:
            return bool(
                context.scene.tool_settings.use_keyframe_insert_auto
            )
        except Exception:
            return False

    @staticmethod
    def _rotation_data_path(target):
        """ターゲットの回転モードに対応するデータパスを返す。"""

        mode = getattr(target, "rotation_mode", 'XYZ')

        if mode == 'QUATERNION':
            return "rotation_quaternion"

        if mode == 'AXIS_ANGLE':
            return "rotation_axis_angle"

        return "rotation_euler"

    @classmethod
    def _insert_reset_keys(cls, context, target, include_delta=False):
        """
        リセット後の値に対してキーフレームを挿入する
        （Auto Keying ON のときだけ呼ばれる）。

        戻り値: キーを挿入できたチャンネル数。
        """

        try:
            frame = context.scene.frame_current
        except Exception:
            frame = None

        # 環境設定の「Only Insert Available」を尊重する。
        # （既存のFカーブがあるチャンネルにだけキーを打つ設定）
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

            if getattr(target, "rotation_mode", 'XYZ') == 'QUATERNION':
                data_paths.append("delta_rotation_quaternion")
            else:
                data_paths.append("delta_rotation_euler")

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
                # 古いBlenderでoptions引数が使えない場合
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
                # 存在しないプロパティ（ポーズボーンのdelta等）は無視
                pass

        return inserted

    def execute(self, context):
        reset_count = 0
        keyed_count = 0

        autokey = self._autokey_enabled(context)

        if context.mode == 'POSE':
            pose_bones = context.selected_pose_bones or []

            for pose_bone in pose_bones:
                self._reset_transform_channels(pose_bone)
                reset_count += 1

                # Auto Keying ON → リセット値にキーを挿入して保存
                if autokey:
                    if self._insert_reset_keys(context, pose_bone):
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
                    include_delta=RESET_DELTA_TRANSFORMS,
                )
                reset_count += 1

                # Auto Keying ON → リセット値にキーを挿入して保存
                if autokey:
                    if self._insert_reset_keys(
                        context,
                        obj,
                        include_delta=RESET_DELTA_TRANSFORMS,
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
# グラフエディタ: Shift+中ドラッグ = 軸ロックキー移動（Maya風）
# ============================================================

class GRAPH_OT_maya_slide_keys(bpy.types.Operator):
    """
    選択中のキーフレームを軸ロック付きで移動する。

    Mayaの Shift+中ドラッグ を再現:
        最初に左右へ動かす → フレーム（時間）のみ移動
        最初に上下へ動かす → 値のみ移動
    最初に動かした方向で軸が確定し、
    中ボタンを離すまでその軸に固定される。

    - フレーム移動は整数スナップ（Ctrl押しながらで一時解除）
    - ESC / 右クリック でキャンセル（元の位置に戻る）
    - Undo（Z）対応
    - キーが選択されていない場合は何もせずイベントを素通しする
    """

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
        """編集可能なFカーブを集める。"""

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

        result = []

        for fcurve in fcurves:
            if getattr(fcurve, "lock", False):
                continue

            if getattr(fcurve, "hide", False):
                continue

            result.append(fcurve)

        return result

    def invoke(self, context, event):
        region = context.region

        # 選択中キーフレームの元の座標を保存する。
        # (co, handle_left, handle_right) をFカーブごとに記録。
        self._targets = []

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
                self._targets.append((fcurve, originals))

        # キーが選択されていなければイベントを素通しする。
        # （他の機能を邪魔しない）
        if not self._targets:
            return {'PASS_THROUGH'}

        # 正規化表示中は表示値と実際の値のスケールが異なるため警告。
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

        context.window_manager.modal_handler_add(self)
        self._set_header(context, 0.0, 0.0)

        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            self._update(context, event)
            return {'RUNNING_MODAL'}

        # 中ボタンを離した = 確定
        if event.type == 'MIDDLEMOUSE' and event.value == 'RELEASE':
            self._finish(context)
            return {'FINISHED'}

        # ESC / 右クリック = キャンセル（元の位置に戻す）
        if (
            event.type in {'ESC', 'RIGHTMOUSE'} and
            event.value == 'PRESS'
        ):
            self._apply_delta(context, 0.0, 0.0)
            self._finish(context)
            return {'CANCELLED'}

        # Shiftを途中で離しても移動は継続する（Mayaと同じ体感）
        return {'RUNNING_MODAL'}

    def _update(self, context, event):
        region = context.region

        if region is None:
            return

        mouse_x = event.mouse_region_x
        mouse_y = event.mouse_region_y

        pixel_dx = mouse_x - self._start_region[0]
        pixel_dy = mouse_y - self._start_region[1]

        # 軸がまだ確定していない場合、
        # 一定距離動いた時点で支配的な方向に固定する。
        if self._axis is None:
            if max(abs(pixel_dx), abs(pixel_dy)) < SLIDE_AXIS_LOCK_THRESHOLD_PX:
                return

            if abs(pixel_dx) >= abs(pixel_dy):
                self._axis = 'FRAME'
            else:
                self._axis = 'VALUE'

        try:
            view = region.view2d.region_to_view(mouse_x, mouse_y)
        except Exception:
            return

        delta_frame = view[0] - self._start_view[0]
        delta_value = view[1] - self._start_view[1]

        if self._axis == 'FRAME':
            delta_value = 0.0

            # 整数フレームへスナップ（Ctrlで一時解除）
            if SLIDE_SNAP_FRAMES and not event.ctrl:
                delta_frame = float(round(delta_frame))
        else:
            delta_frame = 0.0

        self._apply_delta(context, delta_frame, delta_value)
        self._set_header(context, delta_frame, delta_value)

    def _apply_delta(self, context, delta_frame, delta_value):
        """保存済みの元座標 + デルタ を全対象キーに適用する。"""

        for fcurve, originals in self._targets:
            try:
                selected = [
                    keyframe_point
                    for keyframe_point in fcurve.keyframe_points
                    if keyframe_point.select_control_point
                ]
            except Exception:
                continue

            # 再ソート等で数が合わなくなった場合は
            # 安全のためこのカーブをスキップする。
            if len(selected) != len(originals):
                continue

            for keyframe_point, (co, hl, hr) in zip(selected, originals):
                try:
                    keyframe_point.co = (
                        co[0] + delta_frame,
                        co[1] + delta_value,
                    )
                    keyframe_point.handle_left = (
                        hl[0] + delta_frame,
                        hl[1] + delta_value,
                    )
                    keyframe_point.handle_right = (
                        hr[0] + delta_frame,
                        hr[1] + delta_value,
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

    def _set_header(self, context, delta_frame, delta_value):
        try:
            if self._axis == 'FRAME':
                axis_label = "フレーム"
            elif self._axis == 'VALUE':
                axis_label = "値"
            else:
                axis_label = "方向で軸決定"

            context.area.header_text_set(
                f"キー移動 [{axis_label}]  "
                f"Frame {delta_frame:+.1f} / Value {delta_value:+.3f}  "
                "(MMB離す: 確定 / ESC: キャンセル / Ctrl: スナップ解除)"
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
# ビュー切替（Maya風・Hotbox中央の枠から呼び出す）
# ============================================================

class VIEW3D_OT_maya_set_view(bpy.types.Operator):
    """
    ビューを切り替える（Maya風）。

    - PERSP:       パースペクティブ表示に戻す。
    - FRONT/BACK/LEFT/RIGHT/TOP/BOTTOM: 各正投影ビュー。
    - CAMERA_NEW:  現在の視点にカメラを新規作成し、その視点へ入る。

    RegionView3Dへ直接アクセスするため、
    Hotboxの中央枠からでも確実に動作する。
    """

    bl_idname = "view3d.maya_set_view"
    bl_label = "ビュー切替 (Maya)"
    bl_options = {'REGISTER'}

    view_type: bpy.props.StringProperty(default='PERSP')

    # Blender標準の正投影ビュー回転（w, x, y, z）
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

        # --- パースペクティブに戻す ---
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

        # --- 現在の視点でカメラを新規作成 ---
        if view_type == 'CAMERA_NEW':
            return self._create_camera_from_view(context, rv3d)

        # --- 正投影ビュー（FRONT/BACK/LEFT/RIGHT/TOP/BOTTOM） ---
        if view_type in self._ORTHO_ROTATIONS:
            # まず標準オペレーターを試す（一番自然な挙動）。
            try:
                result = bpy.ops.view3d.view_axis(type=view_type)

                if 'FINISHED' in result:
                    self.report({'INFO'}, f"ビュー: {view_type}")
                    return {'FINISHED'}
            except Exception:
                pass

            # フォールバック: 回転を直接設定する。
            if rv3d is not None:
                try:
                    rv3d.view_perspective = 'ORTHO'
                    rv3d.view_rotation = mathutils.Quaternion(
                        self._ORTHO_ROTATIONS[view_type]
                    )
                    self.report({'INFO'}, f"ビュー: {view_type}")
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
        """現在の視点にカメラを作成し、そのカメラ視点へ入る。"""

        scene = context.scene

        cam_data = bpy.data.cameras.new("MayaCamera")
        cam_obj = bpy.data.objects.new("MayaCamera", cam_data)

        collection = getattr(context, "collection", None) or scene.collection

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

        # 現在のビュー行列の逆行列 = カメラのワールド行列。
        if rv3d is not None:
            try:
                cam_obj.matrix_world = rv3d.view_matrix.inverted()
            except Exception:
                pass

        try:
            scene.camera = cam_obj
        except Exception:
            pass

        # そのカメラ視点へ切り替える。
        if rv3d is not None:
            try:
                rv3d.view_perspective = 'CAMERA'
            except Exception:
                pass

        self.report(
            {'INFO'},
            f"新規カメラ '{cam_obj.name}' を作成し、その視点に入りました。",
        )
        return {'FINISHED'}


class VIEW3D_OT_maya_look_through_camera(bpy.types.Operator):
    """
    指定した名前のカメラの視点に切り替える（Maya風 Look Through）。

    - scene.camera を対象カメラに設定する。
    - ビューをカメラ視点（'CAMERA'）に切り替える。
    """

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

        # まず現在のシーン内から探し、なければ全データから探す。
        try:
            cam_obj = scene.objects.get(self.camera_name)
        except Exception:
            cam_obj = None

        if cam_obj is None:
            try:
                cam_obj = bpy.data.objects.get(self.camera_name)
            except Exception:
                cam_obj = None

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
                "3D Viewが見つからないため、シーンカメラのみ変更しました。",
            )

        # 再描画
        try:
            for area in context.window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        except Exception:
            pass

        self.report(
            {'INFO'},
            f"カメラ '{cam_obj.name}' の視点に切り替えました。",
        )
        return {'FINISHED'}


class VIEW3D_MT_maya_view_menu(bpy.types.Menu):
    """Hotbox中央の枠から開くビュー切替メニュー。"""

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

        # --- シーン内のすべてのカメラ（Maya風 Look Through） ---
        cameras = []

        try:
            cameras = [
                obj for obj in context.scene.objects
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

            active_camera = getattr(context.scene, "camera", None)

            for cam_obj in sorted(
                cameras,
                key=lambda o: o.name.lower(),
            ):
                is_active = (cam_obj == active_camera)

                op = layout.operator(
                    "view3d.maya_look_through_camera",
                    text=cam_obj.name,
                    icon='VIEW_CAMERA' if is_active else 'OUTLINER_OB_CAMERA',
                )
                op.camera_name = cam_obj.name

        layout.separator()

        layout.operator(
            "view3d.maya_set_view",
            text="New Camera（現在の視点）",
            icon='OUTLINER_OB_CAMERA',
        ).view_type = 'CAMERA_NEW'


# ============================================================
# オブジェクト作成メニュー（Maya風スポーン）
# ============================================================

class VIEW3D_MT_maya_spawn_menu(bpy.types.Menu):
    """3Dカーソル位置にオブジェクトを作成するメニュー。"""

    bl_idname = "VIEW3D_MT_maya_spawn_menu"
    bl_label = "オブジェクト作成"

    def draw(self, context):
        layout = self.layout

        # --- メッシュプリミティブ ---
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

        # --- その他のオブジェクト ---
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
# コンストレイント（Maya風）
# ============================================================

class OBJECT_OT_maya_add_constraint(bpy.types.Operator):
    """
    Maya流にコンストレイントを追加する。

    Maya: 先にターゲット（駆動側）を選び、
          最後に拘束される側（アクティブ）を選ぶ。
    → アクティブオブジェクトにコンストレイントを追加し、
       他に選択されているオブジェクトをターゲットに設定する。
    """

    bl_idname = "object.maya_add_constraint"
    bl_label = "コンストレイント追加 (Maya)"
    bl_options = {'REGISTER', 'UNDO'}

    constraint_type: bpy.props.StringProperty(default='COPY_LOCATION')

    def execute(self, context):
        active = context.active_object

        if active is None:
            self.report(
                {'WARNING'},
                "アクティブオブジェクトがありません。",
            )
            return {'CANCELLED'}

        # アクティブ以外の選択オブジェクト = ターゲット候補。
        targets = [
            obj for obj in (context.selected_objects or [])
            if obj != active
        ]

        try:
            constraint = active.constraints.new(type=self.constraint_type)
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
    """Maya風コンストレイントメニュー。"""

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


MAYA_SPACE_CLASSES = (
    VIEW3D_OT_maya_set_view,
    VIEW3D_OT_maya_look_through_camera,
    VIEW3D_MT_maya_view_menu,
    VIEW3D_MT_maya_spawn_menu,
    OBJECT_OT_maya_add_constraint,
    VIEW3D_MT_maya_constraint_menu,
    VIEW3D_MT_maya_hotbox_pie,
    VIEW3D_OT_maya_space,
    VIEW3D_OT_maya_toggle_controllers,
    SCREEN_OT_maya_keyframe_jump,
    OBJECT_OT_maya_reset_transforms,
    GRAPH_OT_maya_slide_keys,
)


def register_maya_space_classes():
    """
    クラスを登録する。

    スクリプトを再実行しても壊れないよう、
    同名の既存クラスがあれば先に登録解除する。
    """

    for cls in MAYA_SPACE_CLASSES:
        existing = getattr(bpy.types, cls.__name__, None)

        if existing is not None:
            try:
                bpy.utils.unregister_class(existing)
            except Exception:
                pass

        bpy.utils.register_class(cls)


# ============================================================
# メイン処理
# ============================================================

def setup_maya_keymap_fixed():
    preferences = bpy.context.preferences

    # Alt+左クリックとの衝突を防ぐため、先にOFFにする。
    preferences.inputs.use_mouse_emulate_3_button = False

    # Alt+右ドラッグのズーム方向をMayaに揃える。
    setup_maya_style_zoom_direction(preferences)

    # グラフエディタの表示をMaya風にする。
    #   1) キーフレーム点を大きく描画
    #   2) 選択したキーのハンドルだけ表示
    #   3) 別ファイルを開いても 2) が維持されるようハンドラー登録
    setup_maya_style_graph_theme(preferences)
    setup_graph_editor_handle_display()
    register_graph_display_load_handler()

    # スペースキー用のオペレーターとパイメニューを登録。
    register_maya_space_classes()

    # 以前のスクリプトで壊れた状態を一度復旧する。
    if RESET_TO_CLEAN_INDUSTRY_BASE:
        activate_clean_industry_keymap()

        preferences.inputs.use_mouse_emulate_3_button = False
        setup_maya_style_zoom_direction(preferences)

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.user

    if not kc:
        raise RuntimeError(
            "ユーザーキーマップを取得できませんでした。"
        )

    # --------------------------------------------------------
    # スペース=再生をグローバルに無効化
    # --------------------------------------------------------

    disable_space_play_bindings(kc)

    if KEEP_SPACE_PLAY_IN_ANIM_EDITORS:
        restore_space_play_in_anim_editors(kc)

    # --------------------------------------------------------
    # グローバルキーポリシーの適用
    # --------------------------------------------------------

    # Z / Alt+Q / Alt+A / Alt+D / Alt+W / Alt+S / Alt+1 / Alt+*
    # について、全エディターの競合割り当てを一括で無効化する。
    # これにより「ビューポートでは効くのに
    # グラフエディタでは別の機能が動く」問題がなくなる。
    apply_global_key_policies(kc)

    # Alt+Sでキーフレーム挿入が誤発動する問題への個別対策。
    disable_alt_s_keyinsert_conflicts(kc)

    # --------------------------------------------------------
    # 対象キーマップ
    # --------------------------------------------------------

    km_3d = get_keymap(
        kc,
        "3D View",
        space_type='VIEW_3D',
    )

    km_screen = get_keymap(
        kc,
        "Screen",
    )

    # 「Window」キーマップは全エディター共通で常に効く。
    # グローバルキーの受け皿として使う。
    km_window = get_keymap(
        kc,
        "Window",
    )

    km_object = get_keymap(
        kc,
        "Object Mode",
    )

    km_pose = get_keymap(
        kc,
        "Pose Mode",
    )

    km_mesh = get_keymap(
        kc,
        "Mesh",
    )

    # アニメーションエディター
    km_dopesheet = get_keymap(
        kc,
        "Dopesheet",
        space_type='DOPESHEET_EDITOR',
    )

    km_graph = get_keymap(
        kc,
        "Graph Editor",
        space_type='GRAPH_EDITOR',
    )

    km_nla = get_keymap(
        kc,
        "NLA Editor",
        space_type='NLA_EDITOR',
    )

    # 2Dエディター共通ナビゲーション
    km_view2d = get_keymap(
        kc,
        "View2D",
    )

    mode_keymaps = (
        km_3d,
        km_object,
        km_pose,
        km_mesh,
    )

    # --------------------------------------------------------
    # グローバルキー（Windowキーマップ = どこでも有効）
    # --------------------------------------------------------

    # エディター固有の競合はapply_global_key_policiesで
    # 無効化済みなので、ここに登録すれば
    # カーソルがどこにあっても確実に効く。

    # Z = Undo（グラフエディタ/アウトライナー等でも必ずUndo）
    add_binding(
        km_window,
        'ed.undo',
        'Z',
    )

    # Alt+Q = 再生 / 停止
    add_binding(
        km_window,
        'screen.animation_play',
        'Q',
        alt=True,
        repeat=False,
    )

    # Alt+W / Alt+S = キーフレームジャンプ
    # Alt+A / Alt+D = 1フレーム移動
    global_anim_defs = (
        ('W', 'screen.maya_keyframe_jump', {'next': False}),
        ('S', 'screen.maya_keyframe_jump', {'next': True}),
        ('A', 'screen.frame_offset', {'delta': -1}),
        ('D', 'screen.frame_offset', {'delta': 1}),
    )

    for key, operator, properties in global_anim_defs:
        add_binding(
            km_window,
            operator,
            key,
            alt=True,
            properties=properties,
        )

    # Alt+1 = コントローラー表示切替
    # （3D View以外の上で押した場合は最大の3D Viewに効く）
    add_binding(
        km_window,
        'view3d.maya_toggle_controllers',
        'ONE',
        alt=True,
        repeat=False,
    )

    # Alt+* = トランスフォーム初期化
    #   1) Alt + テンキーの*
    #   2) Alt + Shift + 8（US配列の*。テンキーなしキーボード用）
    # ※ JIS配列フルキーの「*」(Shift+:)はBlenderのキーイベントに
    #    確実に対応していないため、テンキーの*を推奨。
    add_binding(
        km_window,
        'object.maya_reset_transforms',
        'NUMPAD_ASTERIX',
        alt=True,
        repeat=False,
    )

    add_binding(
        km_window,
        'object.maya_reset_transforms',
        'EIGHT',
        alt=True,
        shift=True,
        repeat=False,
    )

    # --------------------------------------------------------
    # Q / W / E / R（3D View系）
    # --------------------------------------------------------

    qwer_defs = (
        ('Q', 'builtin.select_box'),
        ('W', 'builtin.move'),
        ('E', 'builtin.rotate'),
        ('R', 'builtin.scale'),
    )

    for km_target in mode_keymaps:
        for key, tool_name in qwer_defs:
            add_binding(
                km_target,
                'wm.tool_set_by_id',
                key,
                properties={
                    'name': tool_name,
                },
            )

    # --------------------------------------------------------
    # W / E / R / F（アニメーションエディター系）
    # --------------------------------------------------------

    # アニメーションエディターにはツールバーがないため、
    # ツール切替ではなくトランスフォームオペレーターを直接呼ぶ。
    # これでビューポートと同じ指癖のまま
    # キーフレーム/ストリップを操作できる。

    # Graph Editor: W/E/R = 移動 / 回転 / スケール
    add_binding(km_graph, 'transform.translate', 'W')
    add_binding(km_graph, 'transform.rotate', 'E')
    add_binding(km_graph, 'transform.resize', 'R')

    # Dopesheet: W = 時間移動 / R = 時間スケール
    add_binding(
        km_dopesheet,
        'transform.transform',
        'W',
        properties={'mode': 'TIME_TRANSLATE'},
    )
    add_binding(
        km_dopesheet,
        'transform.transform',
        'R',
        properties={'mode': 'TIME_SCALE'},
    )

    # NLA: W = ストリップ移動 / R = 時間スケール
    add_binding(
        km_nla,
        'transform.transform',
        'W',
        properties={'mode': 'TRANSLATION'},
    )
    add_binding(
        km_nla,
        'transform.transform',
        'R',
        properties={'mode': 'TIME_SCALE'},
    )

    # F = 選択にフォーカス（各アニメーションエディター）
    add_binding(km_graph, 'graph.view_selected', 'F')
    add_binding(km_dopesheet, 'action.view_selected', 'F')
    add_binding(km_nla, 'nla.view_selected', 'F')

    # --------------------------------------------------------
    # グラフエディタ: Maya風キーフレーム選択と編集
    # --------------------------------------------------------

    # 重複するクリック選択（any=True）の整理。
    disable_graph_lmb_press_select(km_graph)

    # クリック = キーフレーム点を選択。
    # 空クリックで全選択解除（Maya風）。
    # PRESS選択とCLICK_DRAGボックス選択は共存できるため、
    # 「押した瞬間に選択 → そのままドラッグでボックス選択」が成立する。
    add_binding(
        km_graph,
        'graph.clickselect',
        'LEFTMOUSE',
        properties={
            'extend': False,
            'deselect_all': True,
        },
    )

    # Shift+クリック = 追加選択
    add_binding(
        km_graph,
        'graph.clickselect',
        'LEFTMOUSE',
        shift=True,
        properties={
            'extend': True,
        },
    )

    # 左ドラッグ = ボックス選択（複数キーを一気に選択）
    add_binding(
        km_graph,
        'graph.select_box',
        'LEFTMOUSE',
        value='CLICK_DRAG',
        properties={
            'mode': 'SET',
            'include_handles': False,
            'tweak': False,
            'wait_for_input': False,
        },
    )

    # Shift+左ドラッグ = ボックス追加選択
    add_binding(
        km_graph,
        'graph.select_box',
        'LEFTMOUSE',
        value='CLICK_DRAG',
        shift=True,
        properties={
            'mode': 'ADD',
            'include_handles': False,
            'tweak': False,
            'wait_for_input': False,
        },
    )

    # Ctrl+左ドラッグ = ボックス選択解除
    add_binding(
        km_graph,
        'graph.select_box',
        'LEFTMOUSE',
        value='CLICK_DRAG',
        ctrl=True,
        properties={
            'mode': 'SUB',
            'include_handles': False,
            'tweak': False,
            'wait_for_input': False,
        },
    )

    # Shift+中ドラッグ = 軸ロックキー移動
    #   最初に左右へ動かす → フレームのみ移動（整数スナップ）
    #   最初に上下へ動かす → 値のみ移動
    add_binding(
        km_graph,
        'graph.maya_slide_keys',
        'MIDDLEMOUSE',
        shift=True,
    )

    # --------------------------------------------------------
    # 2Dエディター共通: Alt+中/右ドラッグでパン/ズーム
    # --------------------------------------------------------

    # Mayaのグラフエディタ操作の再現。
    # View2Dキーマップはグラフ/ドープシート/NLA等で共通に効く。
    add_binding(
        km_view2d,
        'view2d.pan',
        'MIDDLEMOUSE',
        alt=True,
    )

    add_binding(
        km_view2d,
        'view2d.zoom',
        'RIGHTMOUSE',
        alt=True,
    )

    # --------------------------------------------------------
    # アニメーション操作（エディター固有側にも登録して確実化）
    # --------------------------------------------------------

    # Windowキーマップより先に評価されるエディター固有側にも
    # 同じ割り当てを置いておくことで、将来アドオン等が
    # 競合キーを追加しても意図した動作が優先される。
    anim_defs = (
        ('Z', 'ed.undo', {}, False),
        ('Q', 'screen.animation_play', {}, True),
        ('A', 'screen.frame_offset', {'delta': -1}, True),
        ('D', 'screen.frame_offset', {'delta': 1}, True),
        ('W', 'screen.maya_keyframe_jump', {'next': False}, True),
        ('S', 'screen.maya_keyframe_jump', {'next': True}, True),
    )

    animation_keymaps = (
        km_screen,
        km_3d,
        km_object,
        km_pose,
        km_mesh,
        km_dopesheet,
        km_graph,
        km_nla,
    )

    for km_target in animation_keymaps:
        for key, operator, properties, use_alt in anim_defs:
            add_binding(
                km_target,
                operator,
                key,
                alt=use_alt,
                properties=properties,
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
        add_binding(
            km_3d,
            operator,
            mouse_button,
            alt=True,
        )

    # --------------------------------------------------------
    # スペースキー = Maya式（単押し/長押し）
    # --------------------------------------------------------

    add_binding(
        km_3d,
        'view3d.maya_space',
        'SPACE',
        repeat=False,
    )

    # --------------------------------------------------------
    # Alt+1 / Alt+*（3D View系にも登録して優先度を確保）
    # --------------------------------------------------------

    for km_target in mode_keymaps:
        add_binding(
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
    ):
        add_binding(
            km_target,
            'object.maya_reset_transforms',
            'NUMPAD_ASTERIX',
            alt=True,
            repeat=False,
        )

        add_binding(
            km_target,
            'object.maya_reset_transforms',
            'EIGHT',
            alt=True,
            shift=True,
            repeat=False,
        )

    # --------------------------------------------------------
    # F = 選択対象にフォーカス（3D View系）
    # --------------------------------------------------------

    # Meshキーマップには登録しない。
    # Edit ModeのF＝面作成を残すため。
    for km_target in (
        km_3d,
        km_object,
        km_pose,
    ):
        add_binding(
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
            add_binding(
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
            add_binding(
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

    add_binding(
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
        add_binding(
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

    add_binding(
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

    # --------------------------------------------------------
    # プリセット保存（バックアップのみ）
    # --------------------------------------------------------

    if SAVE_AS_PRESET:
        preset_directory = bpy.utils.user_resource(
            'SCRIPTS',
            path="presets/keyconfig",
            create=True,
        )

        if not preset_directory:
            raise RuntimeError(
                "キーマッププリセットの保存先を作成できませんでした。"
            )

        target_file = os.path.join(
            preset_directory,
            PRESET_FILENAME,
        )

        result = bpy.ops.preferences.keyconfig_export(
            filepath=target_file,
            all=True,
        )

        if 'FINISHED' not in result:
            raise RuntimeError(
                "キーマッププリセットを書き出せませんでした。"
            )

        print(f"✅ キーマッププリセット保存（バックアップ）: {target_file}")

    # --------------------------------------------------------
    # 環境設定の保存
    # --------------------------------------------------------

    try:
        bpy.ops.wm.save_userpref()
        print("✅ 環境設定とキーマップを保存しました。")
    except Exception as error:
        print(f"⚠️ 環境設定を保存できませんでした: {error}")

    print("🎉 Maya風キーマップの設定が完了しました。")
    print("   Alt+左: 回転 / Alt+中: パン / Alt+右: ズーム")
    print("   （グラフ/ドープシート/NLAでも Alt+中=パン, Alt+右=ズーム）")
    print("   F: 選択対象へフォーカス（アニメーションエディター内でも有効）")
    print("   Space単押し: 1画面 / 4分割 トグル")
    print("   Space長押し: Hotbox風パイメニュー")
    print("     ・中央の枠 = ビュー切替（Persp/Front/Back/Left/Right/")
    print("       Top/Bottom/シーン内の全カメラ/New Camera）")
    print("       → シーンに存在するすべてのカメラが一覧表示され、")
    print("         選択するとそのカメラの視点に切り替わる")
    print("     ・北西 = オブジェクト作成（スポーン）")
    print("     ・北東 = コンストレイント（Parent/Point/Orient/Scale/Aim）")
    print("")
    print("   ▼ 以下はカーソルがどのエディター上にあっても有効:")
    print("   Z: Undo（グラフエディタ内でも必ずUndo）")
    print("   Alt+Q: 再生 / 停止")
    print("   Alt+W / Alt+S: 前後のキーフレームへジャンプ")
    print("   Alt+A / Alt+D: 1フレーム移動")
    print("   Alt+1: コントローラー（ボーン）表示 / 非表示")
    print("   Alt+テンキー* (または Alt+Shift+8):")
    print("      選択対象のトランスフォームを初期化")
    print("      ※ 移動/回転は0、スケールは1（デフォルト値）に戻る")
    print("      ※ Pose Modeでは選択ボーンがレストポーズに戻る")
    print("      ※ Auto Keying が ON のとき: リセット値が現在フレームに")
    print("         自動でキー挿入され、保存される")
    print("      ※ Auto Keying が OFF のとき: キーは挿入されず、")
    print("         既存アニメーションがあればフレーム移動で破棄される")
    print("")
    print("   ▼ アニメーションエディター内:")
    print("   W / E / R: キーフレームの移動 / 回転 / スケール")
    print("      （回転はグラフエディタのみ）")
    print("")
    print("   ▼ グラフエディタ（Maya風キーフレーム編集）:")
    print("   ・キーフレーム点は大きく描画（クリックしやすい）")
    print("   ・クリック: キーを選択（空クリックで全解除）")
    print("   ・Shift+クリック: 追加選択")
    print("   ・左ドラッグ: ボックス選択で複数キーを一気に選択")
    print("     （Shift+ドラッグ: 追加 / Ctrl+ドラッグ: 解除）")
    print("   ・Shift+中ドラッグ: 最初に動かした方向で軸ロック")
    print("       左右 → フレームのみ移動（整数スナップ、Ctrlで解除）")
    print("       上下 → 値のみ移動")
    print("       中ボタンを離すと確定 / ESCでキャンセル")
    print("   ・ハンドルは選択したキーフレームにだけ表示される")
    print("")
    print("ℹ️ 競合していた割り当ては削除ではなく無効化のみ。")
    print("   Preferences > Keymap > Restore でいつでも復元できます。")
    print("")
    print("⚠️ 重要: カスタムオペレーターをBlender再起動後も使うには、")
    print("   1) このスクリプトをテキストエディターに保存し、")
    print("      「Register」にチェック → スタートアップファイルを保存")
    print("   2) またはアドオン化してインストール、のいずれかが必要です。")


# 実行
setup_maya_keymap_fixed()