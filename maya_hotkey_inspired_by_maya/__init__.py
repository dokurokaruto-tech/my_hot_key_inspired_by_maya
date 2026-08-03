bl_info = {
    "name": "Maya Hotkey Inspired Keymap",
    "author": "Custom",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "Preferences > Add-ons",
    "description": (
        "Maya風の操作、Hotbox、Micro Manipulator、"
        "アニメーション操作を追加します"
    ),
    "category": "Interface",
}


import bpy
import os
import importlib


if "core" in locals():
    importlib.reload(core)
    importlib.reload(features)
else:
    from . import core
    from . import features


ADDON_ID = (
    __package__
    if __package__
    else __name__
)


# ============================================================
# キーマップセットアップ
# ============================================================

def setup_maya_keymap_fixed(
    *,
    reset_base=None,
    save_preset=None,
):
    if reset_base is None:
        reset_base = (
            core.RESET_TO_CLEAN_INDUSTRY_BASE
        )

    if save_preset is None:
        save_preset = core.SAVE_AS_PRESET

    preferences = bpy.context.preferences

    features.restore_maya_micro_space_visibility()

    preferences.inputs.use_mouse_emulate_3_button = False

    core.setup_maya_style_zoom_direction(
        preferences
    )
    core.setup_maya_style_graph_theme(
        preferences
    )
    core.setup_graph_editor_handle_display()
    core.register_graph_display_load_handler()

    if reset_base:
        core.activate_clean_industry_keymap()

        preferences.inputs.use_mouse_emulate_3_button = False

        core.setup_maya_style_zoom_direction(
            preferences
        )

    wm = bpy.context.window_manager
    keyconfig = wm.keyconfigs.user

    if not keyconfig:
        raise RuntimeError(
            "ユーザーキーマップを取得できませんでした。"
        )

    add = core.add_binding
    get = core.get_keymap

    # --------------------------------------------------------
    # Space再生
    # --------------------------------------------------------

    core.disable_space_play_bindings(
        keyconfig
    )

    if core.KEEP_SPACE_PLAY_IN_ANIM_EDITORS:
        core.restore_space_play_in_anim_editors(
            keyconfig
        )

    # --------------------------------------------------------
    # グローバル競合
    # --------------------------------------------------------

    core.apply_global_key_policies(
        keyconfig
    )
    core.disable_alt_s_keyinsert_conflicts(
        keyconfig
    )

    # --------------------------------------------------------
    # Keymap取得
    # --------------------------------------------------------

    km_3d = get(
        keyconfig,
        "3D View",
        space_type='VIEW_3D',
    )
    km_screen = get(
        keyconfig,
        "Screen",
    )
    km_window = get(
        keyconfig,
        "Window",
    )
    km_object = get(
        keyconfig,
        "Object Mode",
    )
    km_pose = get(
        keyconfig,
        "Pose Mode",
    )
    km_mesh = get(
        keyconfig,
        "Mesh",
    )
    km_dopesheet = get(
        keyconfig,
        "Dopesheet",
        space_type='DOPESHEET_EDITOR',
    )
    km_graph = get(
        keyconfig,
        "Graph Editor",
        space_type='GRAPH_EDITOR',
    )
    km_nla = get(
        keyconfig,
        "NLA Editor",
        space_type='NLA_EDITOR',
    )
    km_view2d = get(
        keyconfig,
        "View2D",
    )

    mode_keymaps = (
        km_3d,
        km_object,
        km_pose,
        km_mesh,
    )

    # --------------------------------------------------------
    # グローバルキー
    # --------------------------------------------------------

    add(
        km_window,
        'ed.undo',
        'Z',
    )

    add(
        km_window,
        'screen.animation_play',
        'Q',
        alt=True,
        repeat=False,
    )

    global_animation_definitions = (
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

    for (
        key,
        operator,
        properties,
    ) in global_animation_definitions:
        add(
            km_window,
            operator,
            key,
            alt=True,
            properties=properties,
        )

    add(
        km_window,
        'view3d.maya_toggle_controllers',
        'ONE',
        alt=True,
        repeat=False,
    )

    add(
        km_window,
        'object.maya_reset_transforms',
        'NUMPAD_ASTERIX',
        alt=True,
        repeat=False,
    )

    add(
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

    qwer_definitions = (
        ('Q', 'builtin.select_box'),
        ('W', 'builtin.move'),
        ('E', 'builtin.rotate'),
        ('R', 'builtin.scale'),
    )

    for keymap_target in mode_keymaps:
        for key, tool_name in qwer_definitions:
            add(
                keymap_target,
                'wm.tool_set_by_id',
                key,
                properties={
                    'name': tool_name,
                    'cycle': False,
                },
            )

    # --------------------------------------------------------
    # Animation Editor W / E / R / F
    # --------------------------------------------------------

    add(
        km_graph,
        'transform.translate',
        'W',
    )
    add(
        km_graph,
        'transform.rotate',
        'E',
    )
    add(
        km_graph,
        'transform.resize',
        'R',
    )

    add(
        km_dopesheet,
        'transform.transform',
        'W',
        properties={
            'mode': 'TIME_TRANSLATE',
        },
    )
    add(
        km_dopesheet,
        'transform.transform',
        'R',
        properties={
            'mode': 'TIME_SCALE',
        },
    )

    add(
        km_nla,
        'transform.transform',
        'W',
        properties={
            'mode': 'TRANSLATION',
        },
    )
    add(
        km_nla,
        'transform.transform',
        'R',
        properties={
            'mode': 'TIME_SCALE',
        },
    )

    add(
        km_graph,
        'graph.view_selected',
        'F',
    )
    add(
        km_dopesheet,
        'action.view_selected',
        'F',
    )
    add(
        km_nla,
        'nla.view_selected',
        'F',
    )

    # --------------------------------------------------------
    # Graph Editor
    # --------------------------------------------------------

    add(
        km_graph,
        'graph.maya_slide_keys',
        'MIDDLEMOUSE',
        shift=True,
    )

    # --------------------------------------------------------
    # 2D Navigation
    # --------------------------------------------------------

    add(
        km_view2d,
        'view2d.pan',
        'MIDDLEMOUSE',
        alt=True,
    )

    add(
        km_view2d,
        'view2d.zoom',
        'RIGHTMOUSE',
        alt=True,
    )

    # --------------------------------------------------------
    # Animation共通
    # --------------------------------------------------------

    animation_definitions = (
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
        km_mesh,
        km_dopesheet,
        km_graph,
        km_nla,
    )

    for keymap_target in animation_keymaps:
        for (
            key,
            operator,
            properties,
            use_alt,
        ) in animation_definitions:
            add(
                keymap_target,
                operator,
                key,
                alt=use_alt,
                properties=properties,
            )

    # --------------------------------------------------------
    # Maya View Navigation
    # --------------------------------------------------------

    navigation_definitions = (
        ('LEFTMOUSE', 'view3d.rotate'),
        ('MIDDLEMOUSE', 'view3d.move'),
        ('RIGHTMOUSE', 'view3d.zoom'),
    )

    for (
        mouse_button,
        operator,
    ) in navigation_definitions:
        add(
            km_3d,
            operator,
            mouse_button,
            alt=True,
        )

    # --------------------------------------------------------
    # Manipulator Menu
    # --------------------------------------------------------

    for keymap_target in mode_keymaps:
        add(
            keymap_target,
            'wm.call_menu',
            'RIGHTMOUSE',
            ctrl=True,
            shift=True,
            repeat=False,
            properties={
                'name': (
                    features
                    .VIEW3D_MT_maya_manipulator_menu
                    .bl_idname
                ),
            },
        )

    # --------------------------------------------------------
    # Space
    # --------------------------------------------------------

    add(
        km_3d,
        'view3d.maya_space',
        'SPACE',
        repeat=False,
    )

    # --------------------------------------------------------
    # Alt+1
    # --------------------------------------------------------

    for keymap_target in mode_keymaps:
        add(
            keymap_target,
            'view3d.maya_toggle_controllers',
            'ONE',
            alt=True,
            repeat=False,
        )

    # --------------------------------------------------------
    # Alt+*
    # --------------------------------------------------------

    for keymap_target in (
        km_3d,
        km_object,
        km_pose,
    ):
        add(
            keymap_target,
            'object.maya_reset_transforms',
            'NUMPAD_ASTERIX',
            alt=True,
            repeat=False,
        )

        add(
            keymap_target,
            'object.maya_reset_transforms',
            'EIGHT',
            alt=True,
            shift=True,
            repeat=False,
        )

    for keymap_target in (
        km_graph,
        km_dopesheet,
    ):
        add(
            keymap_target,
            'object.maya_reset_transforms',
            'NUMPAD_ASTERIX',
            alt=True,
            repeat=False,
        )

        add(
            keymap_target,
            'object.maya_reset_transforms',
            'EIGHT',
            alt=True,
            shift=True,
            repeat=False,
        )

    # --------------------------------------------------------
    # F Focus
    # --------------------------------------------------------

    for keymap_target in (
        km_3d,
        km_object,
        km_pose,
    ):
        add(
            keymap_target,
            'view3d.view_selected',
            'F',
            properties={
                'use_all_regions': False,
            },
        )

    # --------------------------------------------------------
    # 4 / 5 / 6 / 7 Shading
    # --------------------------------------------------------

    shading_definitions = (
        ('FOUR', 'WIREFRAME'),
        ('FIVE', 'SOLID'),
        ('SIX', 'MATERIAL'),
        ('SEVEN', 'RENDERED'),
    )

    for keymap_target in mode_keymaps:
        for (
            key,
            shading_type,
        ) in shading_definitions:
            add(
                keymap_target,
                'wm.context_set_enum',
                key,
                properties={
                    'data_path': (
                        'space_data.shading.type'
                    ),
                    'value': shading_type,
                },
            )

    # --------------------------------------------------------
    # 1 / 2 / 3 Subdivision
    # --------------------------------------------------------

    subdivision_definitions = (
        ('ONE', 0),
        ('TWO', 1),
        ('THREE', 2),
    )

    for keymap_target in (
        km_object,
        km_mesh,
    ):
        for (
            key,
            level,
        ) in subdivision_definitions:
            add(
                keymap_target,
                'object.subdivision_set',
                key,
                properties={
                    'level': level,
                    'relative': False,
                    'ensure_modifier': (
                        level > 0
                    ),
                },
            )

    # --------------------------------------------------------
    # F8 / F9 / F10 / F11
    # --------------------------------------------------------

    add(
        km_3d,
        'object.editmode_toggle',
        'F8',
    )

    component_definitions = (
        ('F9', 'VERT'),
        ('F10', 'EDGE'),
        ('F11', 'FACE'),
    )

    for (
        key,
        select_type,
    ) in component_definitions:
        add(
            km_mesh,
            'mesh.select_mode',
            key,
            properties={
                'type': select_type,
            },
        )

    # --------------------------------------------------------
    # Double Click Edge Loop
    # --------------------------------------------------------

    add(
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
    # Q固定
    # --------------------------------------------------------

    core.force_q_select_box_no_cycle(
        keyconfig
    )

    # --------------------------------------------------------
    # Preset保存
    # --------------------------------------------------------

    if save_preset:
        preset_directory = (
            bpy.utils.user_resource(
                'SCRIPTS',
                path="presets/keyconfig",
                create=True,
            )
        )

        if not preset_directory:
            raise RuntimeError(
                "キーマッププリセットの"
                "保存先を作成できませんでした。"
            )

        target_file = os.path.join(
            preset_directory,
            core.PRESET_FILENAME,
        )

        result = (
            bpy.ops.preferences.keyconfig_export(
                filepath=target_file,
                all=True,
            )
        )

        if 'FINISHED' not in result:
            raise RuntimeError(
                "キーマッププリセットを"
                "書き出せませんでした。"
            )

        print(
            f"✅ キーマッププリセット保存: "
            f"{target_file}"
        )

    # --------------------------------------------------------
    # Preferences保存
    # --------------------------------------------------------

    try:
        bpy.ops.wm.save_userpref()
        print(
            "✅ 環境設定とキーマップを保存しました。"
        )
    except Exception as error:
        print(
            f"⚠️ 環境設定を保存できませんでした: "
            f"{error}"
        )

    print_setup_summary()


def print_setup_summary():
    print("🎉 Maya風キーマップの設定が完了しました。")
    print("   Alt+左: 回転 / Alt+中: パン / Alt+右: ズーム")
    print("   F: 選択対象へフォーカス")
    print("   Space単押し: 1画面 / 4分割 トグル")
    print("   Space長押し: Hotbox風パイメニュー")
    print("   Q: 矩形選択に固定")
    print("")
    print("   Ctrl+Shift+右クリック:")
    print("      ・Global / Local / Gimbal")
    print("      ・Micro Manipulator ON / OFF")
    print("      ・Object / Edit / Pose")
    print("")
    print("   Z: Undo")
    print("   Alt+Q: 再生 / 停止")
    print("   Alt+W / Alt+S: 前後のキーフレーム")
    print("   Alt+A / Alt+D: 1フレーム移動")
    print("   Alt+1: コントローラー表示切替")
    print("   Alt+テンキー* / Alt+Shift+8: 初期化")
    print("")
    print("   Graph Editor:")
    print("   Shift+中ドラッグ: 軸ロックキー移動")


# ============================================================
# Installer UI
# ============================================================

class MAYAKEYMAP_OT_install(
    bpy.types.Operator
):
    bl_idname = (
        "preferences.maya_hotkey_install"
    )
    bl_label = (
        "Maya風キーマップをセットアップ"
    )
    bl_description = (
        "Maya風キーマップをユーザーキーマップへ"
        "構築します"
    )
    bl_options = {'REGISTER'}

    reset_base: bpy.props.BoolProperty(
        name="Industry Compatibleから再構築",
        description=(
            "現在のユーザーキーマップをリセットして、"
            "Industry Compatibleから構築します"
        ),
        default=(
            core.RESET_TO_CLEAN_INDUSTRY_BASE
        ),
    )

    save_preset: bpy.props.BoolProperty(
        name="プリセットとして保存",
        default=core.SAVE_AS_PRESET,
    )

    def execute(self, context):
        try:
            setup_maya_keymap_fixed(
                reset_base=self.reset_base,
                save_preset=self.save_preset,
            )
        except Exception as error:
            self.report(
                {'ERROR'},
                f"セットアップに失敗しました: "
                f"{error}",
            )
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            "Maya風キーマップをセットアップしました。",
        )
        return {'FINISHED'}


class MAYAKEYMAP_Preferences(
    bpy.types.AddonPreferences
):
    bl_idname = ADDON_ID

    reset_base: bpy.props.BoolProperty(
        name="Industry Compatibleから再構築",
        description=(
            "既存のユーザーキーマップをリセットしてから"
            "Maya風キーマップを構築します"
        ),
        default=(
            core.RESET_TO_CLEAN_INDUSTRY_BASE
        ),
    )

    save_preset: bpy.props.BoolProperty(
        name="キーマッププリセットを書き出す",
        default=core.SAVE_AS_PRESET,
    )

    def draw(self, context):
        layout = self.layout

        layout.label(
            text="Maya風キーマップのセットアップ",
            icon='PREFERENCES',
        )

        layout.separator()

        layout.prop(
            self,
            "reset_base",
        )
        layout.prop(
            self,
            "save_preset",
        )

        if self.reset_base:
            warning_box = layout.box()
            warning_box.label(
                text=(
                    "現在のユーザーキーマップが"
                    "Industry Compatibleへリセットされます。"
                ),
                icon='ERROR',
            )
            warning_box.label(
                text=(
                    "必要であれば、実行前に既存の"
                    "キーマップをバックアップしてください。"
                ),
            )

        layout.separator()

        operator = layout.operator(
            MAYAKEYMAP_OT_install.bl_idname,
            text="Maya風キーマップをセットアップ / 再構築",
            icon='FILE_REFRESH',
        )
        operator.reset_base = self.reset_base
        operator.save_preset = self.save_preset

        layout.separator()

        info_box = layout.box()
        info_box.label(
            text=(
                "アドオンを有効化しただけでは"
                "キーマップを書き換えません。"
            ),
            icon='INFO',
        )
        info_box.label(
            text=(
                "上のボタンを押したときだけ"
                "キーマップを構築します。"
            ),
        )


ADDON_CLASSES = (
    MAYAKEYMAP_OT_install,
    MAYAKEYMAP_Preferences,
)


# ============================================================
# Registration
# ============================================================

def register_addon_classes():
    for cls in reversed(ADDON_CLASSES):
        existing = getattr(
            bpy.types,
            cls.__name__,
            None,
        )

        if existing is not None:
            try:
                bpy.utils.unregister_class(
                    existing
                )
            except Exception:
                pass

    for cls in ADDON_CLASSES:
        bpy.utils.register_class(cls)


def unregister_addon_classes():
    for cls in reversed(ADDON_CLASSES):
        existing = getattr(
            bpy.types,
            cls.__name__,
            None,
        )

        if existing is not None:
            try:
                bpy.utils.unregister_class(
                    existing
                )
            except Exception:
                pass


def register():
    register_addon_classes()

    try:
        features.register_classes()
        features.register_runtime_properties()

        core.setup_graph_editor_handle_display()
        core.register_graph_display_load_handler()

    except Exception:
        core.unregister_graph_display_load_handler()
        features.unregister_runtime_properties()
        features.unregister_classes()
        unregister_addon_classes()
        raise


def unregister():
    core.unregister_graph_display_load_handler()

    features.unregister_runtime_properties()
    features.unregister_classes()

    unregister_addon_classes()
