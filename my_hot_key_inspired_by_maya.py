import bpy
import os
import time


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
#
# エンプティをIKターゲット等のコントローラーとして使う
# リグを扱う場合は True にする。
# （エンプティを配置用の目印などに使っている場合は
#   Falseのままを推奨）
ALT1_ALSO_TOGGLE_EMPTIES = False


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

    # BlenderのバージョンによってはNoneが返る場合もあるため、
    # 明示的にFalseの場合だけ失敗扱いにする。
    if result is False:
        raise RuntimeError(
            "Industry Compatibleキーマップを有効化できませんでした。"
        )

    # userキーマップを現在のベース設定に戻す。
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

    # head=Trueに対応するBlenderでは、
    # 既存項目より優先される位置に追加する。
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

    # キーリピートの制御（対応バージョンのみ）
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
# スペース=再生の無効化
# ============================================================

def disable_space_play_bindings(keyconfig):
    """
    修飾キーなしの「スペース = screen.animation_play」を
    すべてのキーマップで無効化する。

    なぜ必要か:
    スペース=再生は「Frames」などのグローバルキーマップに
    登録されている。3D View側のview3d.maya_spaceが
    何らかの理由（オペレーター未登録・キーマップ再読込など）で
    効かない場合、イベントがグローバル側に素通りして
    再生が発動してしまう。

    ここでは削除ではなく active=False にするだけなので、
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

    「Frames」キーマップはすべてのエディターで共有されて
    いるため、上のdisable_space_play_bindingsで無効化すると
    タイムライン等でもスペース再生が消えてしまう。
    そこでエディター固有のキーマップに再登録する。
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

    view3d.zoomオペレーター自体には方向の設定がなく、
    Preferencesの入力設定で挙動が決まるため、ここで設定する。
    """

    inputs = preferences.inputs

    # ドラッグ量に比例してズームする方式。
    # Mayaのドリーと同じ操作感になる。
    # （'CONTINUE'はドラッグ中ズームし続ける方式なので使わない）
    inputs.view_zoom_method = 'DOLLY'

    # 水平方向のドラッグでズームする。
    # 右 = 拡大 / 左 = 縮小 となり、Mayaと同じ方向になる。
    inputs.view_zoom_axis = 'HORIZONTAL'

    # 方向を反転しない。
    # これで「左上に動かすと縮小」というMayaの挙動と一致する。
    # もし逆に感じる場合はここを True にする。
    inputs.invert_mouse_zoom = False


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
    """
    SpaceView3DがQuad View状態かどうか。

    region_quadviews は通常ビューでは空、
    Quad Viewでは複数のRegionView3Dを持つ。
    """

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
    """
    context.temp_override用のキーワードを作る。

    window / screen / area / region の整合性が重要なので、
    context.window.screen を優先する。
    """

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

    Quad Viewでは各小ビューごとにRegionView3Dが違う。
    ここが取得できると、
    「マウス下の小ビューを最大化」がより確実になる。
    """

    if area is None or region is None or space is None:
        return None

    # BlenderのバージョンによってはRegion.dataにRegionView3Dが入る。
    try:
        region_data = getattr(region, "data", None)

        if _is_region_view3d(region_data):
            return region_data
    except Exception:
        pass

    # 現在のcontextがすでにそのRegionなら context.region_data を使える。
    try:
        if context.area == area and context.region == region:
            region_data = context.region_data

            if _is_region_view3d(region_data):
                return region_data
    except Exception:
        pass

    # context overrideして context.region_data を取りに行く。
    # これでQuad View内の「マウス下の小ビュー」に対応する
    # RegionView3Dを拾えることが多い。
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

    # 通常ビューなら space.region_3d でよい。
    # Quad View中にここへ落ちた場合、space.region_3dを返すと
    # 「元のビュー固定」問題を再発させる可能性があるため返さない。
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

    重要:
    Quad Viewでは、3D View Areaの中に複数のWINDOW Regionがある。
    そのためcontext.region任せにせず、event.mouse_x / mouse_yから
    実際にマウスが乗っている小ビューを探す。
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

    # フォールバック: 現在のcontext areaが3D Viewなら使う。
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

    # まずはマウス座標が完全に含まれるWINDOW Regionを探す。
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

    # セパレーター線上などで見つからない場合は、最も近いWINDOW Regionを使う。
    if region is None and window_regions and mouse_x is not None and mouse_y is not None:
        region = min(
            window_regions,
            key=lambda r: _region_center_distance_sq(r, mouse_x, mouse_y),
        )

    # それでもダメなら現在のcontext.regionを使う。
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

    # 最後のフォールバック。
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


def copy_region_view3d_state(src, dst):
    """
    RegionView3Dの視点状態をコピーする。

    Quad View解除時に、マウス下の小ビューの状態を
    space.region_3d側へコピーしておくことで、
    Blenderが元のビューへ戻してしまう状況を防ぐ。
    """

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

            # Vector / Quaternionなどはcopyしてから代入する。
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

    これが今回の核心:
    context任せにせず、マウス下の小ビューRegionをoverrideして実行する。
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
        # Blenderのバージョンや状態によって region_data / space_data の
        # overrideが厳しく判定される場合があるため、段階的に試す。
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

    # 古いBlender、またはoverride失敗時のフォールバック。
    return bpy.ops.screen.region_quadview()


def call_menu_pie_for_region(
    context,
    menu_name,
    area,
    region,
    space,
    region_data,
):
    """
    指定した3D View Region上でパイメニューを呼ぶ。

    Hotboxをマウス下のビューに出すための補助。
    """

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
    """
    Maya Hotboxの代用パイメニュー。

    キャラクターアニメーション作業に絞った構成。
    下方向の「すべてのツール」からは wm.toolbar
    （ツール一覧ポップアップ）が開くため、
    そこから全ツールへアクセスできる。
    """

    bl_idname = "VIEW3D_MT_maya_hotbox_pie"
    bl_label = "Hotbox (Maya風)"

    def draw(self, context):
        pie = self.layout.menu_pie()
        is_pose = (context.mode == 'POSE')

        # --- 西（左）: キー挿入 ---
        # Blender 4.1以降ではkeyframe_insert_menuが存在しない
        # 場合があるため、存在チェックしてフォールバックする。
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

        # --- 北西: ブレイクダウナー or 開始フレームへ ---
        if is_pose:
            # MayaのTween Machineに近い機能
            pie.operator(
                "pose.breakdown",
                text="ブレイクダウナー",
                icon='IPO_EASE_IN_OUT',
            )
        else:
            pie.operator(
                "screen.frame_jump",
                text="開始フレームへ",
                icon='REW',
            ).end = False

        # --- 北東: ポーズリセット or 終了フレームへ ---
        if is_pose:
            pie.operator(
                "pose.transforms_clear",
                text="ポーズをリセット",
                icon='LOOP_BACK',
            )
        else:
            pie.operator(
                "screen.frame_jump",
                text="終了フレームへ",
                icon='FF',
            ).end = True

        # --- 南西: モーションパス or Object/Pose切替 ---
        if is_pose:
            pie.operator(
                "pose.paths_calculate",
                text="モーションパス計算",
                icon='TRACKING',
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


class VIEW3D_OT_maya_space(bpy.types.Operator):
    """
    Mayaのスペースキーを再現するモーダルオペレーター。

    単押し:
        マウス下のビューポートを 1画面 / 4分割 でトグル。
        4分割から戻るときは、
        スペースを押した瞬間にマウスが乗っていた小ビューが
        1画面になる。

    長押し:
        Hotbox風パイメニューを表示。
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

        # 重要:
        # スペースを押した瞬間のマウス位置を保存する。
        # Quad View内で「次に大きくしたいビュー」の判定に使う。
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
        """
        イベントからマウス座標を更新する。

        キーボードイベントでもmouse_x/mouse_yを持っていることが多い。
        TIMERでは不確かなため更新しない。
        """

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

        # 単押し / 長押し後リリース:
        # 以前の版では、長押し判定前にRELEASEが来ると常にQuad切替に
        # なっていた。ここでは経過時間も見る。
        if event.type == 'SPACE' and event.value == 'RELEASE':
            self._remove_timer(context)

            elapsed = time.monotonic() - self._start_time

            if elapsed >= SPACE_HOLD_TIME:
                self._open_hotbox(context)
            else:
                self._toggle_quad_view(context)

            return {'FINISHED'}

        # 長押し中のキーリピート（SPACEのPRESS再送）は無視して
        # イベントを消費する。素通りさせると他の機能が発動する。
        if event.type == 'SPACE' and event.value == 'PRESS':
            return {'RUNNING_MODAL'}

        # 長押し: 閾値を超えた
        if event.type == 'TIMER':
            elapsed = time.monotonic() - self._start_time

            if elapsed >= SPACE_HOLD_TIME:
                self._remove_timer(context)
                self._open_hotbox(context)
                return {'FINISHED'}

        # 中断
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
            # Quad Viewから1画面へ戻る時、
            # マウス下の小ビューのRegionView3Dをspace.region_3dへ
            # 先にコピーしておく。
            #
            # これにより、Blenderが元のビューを優先してしまうケースでも、
            # Mayaのように「マウスを置いていたビュー」が1画面になる。
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
    Mayaの「パネルのShow設定でNURBSカーブ（コントローラー）を
    表示/非表示する」ワークフローの移植。

    Blenderのリグコントローラーは基本的にボーン
    （カスタムシェイプ含む）として描画されるため、
    ビューポートごとのオーバーレイ設定 overlay.show_bones を
    トグルする。

    ポイント:
    - ビューポート単位で切り替わる（Mayaのパネル単位と同じ感覚）。
      Quad Viewでも、そのAreaのビュー全体に対して効く。
    - オブジェクト自体を隠すわけではないので、
      再生中でもアニメーションはそのまま動き続ける。
    - マウスが乗っているビューポートに対して効くため、
      複数ビューポートを並べていても直感的に使える。
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

        return space

    def _toggle(self, context, space):
        if space is None:
            self.report(
                {'WARNING'},
                "3D View上で実行してください。",
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

        # 現在の状態を反転する。
        show = not overlay.show_bones
        overlay.show_bones = show

        # エンプティをコントローラーに使うリグ向けのオプション。
        # ビューポートのオブジェクトタイプ可視性を連動させる。
        if ALT1_ALSO_TOGGLE_EMPTIES:
            try:
                space.show_object_viewport_empty = show
            except Exception:
                pass

        # 再描画を促す。
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


MAYA_SPACE_CLASSES = (
    VIEW3D_MT_maya_hotbox_pie,
    VIEW3D_OT_maya_space,
    VIEW3D_OT_maya_toggle_controllers,
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
    # Industry Compatible読み込み前に設定することが重要。
    preferences.inputs.use_mouse_emulate_3_button = False

    # Alt+右ドラッグのズーム方向をMayaに揃える。
    # （キーマップではなくPreferencesの設定）
    setup_maya_style_zoom_direction(preferences)

    # スペースキー用のオペレーターとパイメニューを登録。
    # キーマップに割り当てる前に登録しておく必要がある。
    register_maya_space_classes()

    # 以前のスクリプトで壊れた状態を一度復旧する。
    if RESET_TO_CLEAN_INDUSTRY_BASE:
        activate_clean_industry_keymap()

        # 念のため、キーマップ復旧後にも入力設定を再適用する。
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

    # これをやらないと、view3d.maya_spaceが効かない状況
    # （再起動直後でオペレーター未登録など）で
    # スペースが「Frames」キーマップに素通りして
    # 再生が発動してしまう。
    disable_space_play_bindings(kc)

    if KEEP_SPACE_PLAY_IN_ANIM_EDITORS:
        # ドープシート/グラフ/NLAではスペース再生を復活させる。
        restore_space_play_in_anim_editors(kc)

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

    mode_keymaps = (
        km_3d,
        km_object,
        km_pose,
        km_mesh,
    )

    # --------------------------------------------------------
    # Q / W / E / R
    # --------------------------------------------------------

    # Qはクリック選択とドラッグ範囲選択ができるSelect Boxにする。
    # builtin.selectを使いたい場合はbuiltin.select_boxを変更する。
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
    # アニメーション操作
    # --------------------------------------------------------

    anim_defs = (
        # Z = Undo
        ('Z', 'ed.undo', {}, False),

        # Alt+Q = 再生
        ('Q', 'screen.animation_play', {}, True),

        # Alt+A / Alt+D = 1フレーム移動
        ('A', 'screen.frame_offset', {'delta': -1}, True),
        ('D', 'screen.frame_offset', {'delta': 1}, True),

        # Alt+W / Alt+S = 前後のキーフレーム
        ('W', 'screen.keyframe_jump', {'next': False}, True),
        ('S', 'screen.keyframe_jump', {'next': True}, True),
    )

    animation_keymaps = (
        km_screen,
        km_3d,
        km_object,
        km_pose,
        km_mesh,
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

    # グローバルのスペース=再生はすでに無効化済みなので、
    # ビューポート内では必ずこのオペレーターが受け取る。
    add_binding(
        km_3d,
        'view3d.maya_space',
        'SPACE',
        repeat=False,
    )

    # --------------------------------------------------------
    # Alt+1 = コントローラー表示切替（Maya風）
    # --------------------------------------------------------

    # マウスが乗っているビューポートの
    # ボーン（＝リグコントローラー）表示をトグルする。
    #
    # モード固有キーマップ（Object/Pose/Mesh）が
    # Alt+1を先に奪う可能性があるため、
    # 3D Viewだけでなく各モードにも登録して確実に効かせる。
    for km_target in mode_keymaps:
        add_binding(
            km_target,
            'view3d.maya_toggle_controllers',
            'ONE',
            alt=True,
            repeat=False,
        )

    # --------------------------------------------------------
    # F = 選択対象にフォーカス
    # --------------------------------------------------------

    # Object Modeでは選択オブジェクト、
    # Pose Modeでは選択ボーンなどにフォーカスする。
    #
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

    # モード固有キーマップで数字キーが奪われないよう、
    # 関連モードにだけ登録する。
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

                    # 2または3を押したときだけ、
                    # 必要ならSubdivision Modifierを追加する。
                    'ensure_modifier': level > 0,
                },
            )

    # --------------------------------------------------------
    # F8 / F9 / F10 / F11
    # --------------------------------------------------------

    # F8 = Object/Edit Mode切り替え
    add_binding(
        km_3d,
        'object.editmode_toggle',
        'F8',
    )

    # F9/F10/F11 = 頂点/辺/面
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

    # 以前はここで書き出したプリセットをkeyconfig_setで
    # 再読込していたが、その再読込によって直前に加えた
    # ユーザーキーマップの変更が失われ、スペースが
    # 素の状態（=再生）に戻ってしまうことがあった。
    #
    # 現在の設定はユーザーキーマップ（keyconfigs.user）に
    # 直接適用済みで、save_userpref()で永続化されるため、
    # 再読込は不要。プリセットはバックアップとしてのみ
    # 書き出す（all=Trueで全キーマップを含める）。
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

    # ズーム方向などのPreferences設定と、
    # ユーザーキーマップの変更をまとめて保存する。
    # 自動保存がOFFの環境でも確実に残るよう明示的に保存する。
    try:
        bpy.ops.wm.save_userpref()
        print("✅ 環境設定とキーマップを保存しました。")
    except Exception as error:
        print(f"⚠️ 環境設定を保存できませんでした: {error}")

    print("🎉 Maya風キーマップの設定が完了しました。")
    print("   Alt+左: 回転")
    print("   Alt+中: パン")
    print("   Alt+右: ズーム（右=拡大 / 左=縮小）")
    print("   F: 選択対象へフォーカス")
    print("   Space単押し: 1画面 / 4分割 トグル")
    print("      ※ 4分割から戻る時は、マウス下の小ビューを1画面化")
    print("   Space長押し: Hotbox風パイメニュー")
    print("   Alt+Q: 再生 / 停止")
    print("   Alt+1: コントローラー（ボーン）表示 / 非表示")
    print("      ※ マウス下のビューポート単位で切り替え")
    print("      ※ 再生中でもアニメーションは動き続ける")
    print("")
    print("ℹ️ スペース=再生はグローバルでは無効化しました。")
    print("   （ドープシート/グラフ/NLA内でのみスペース再生が有効）")
    print("")
    print("⚠️ 重要: view3d.maya_space と view3d.maya_toggle_controllers は")
    print("   カスタムオペレーターのため、Blender再起動後も使うには")
    print("   以下のいずれかが必要です。")
    print("   1) このスクリプトをテキストエディターに保存し、")
    print("      「Register」にチェック → スタートアップファイルを保存")
    print("   2) このスクリプトをアドオン化してインストール")
    print("   ※ 未登録のままでもスペースで再生が誤発動することは")
    print("      なくなりました（何も起きないだけ）。")


# 実行
setup_maya_keymap_fixed()